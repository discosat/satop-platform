import io
import os
from fastapi import APIRouter, Depends, Request, HTTPException, status, BackgroundTasks
import logging

import sqlalchemy
import sqlite3

from satop_platform.components.syslog import models
from satop_platform.plugin_engine.plugin import Plugin
from satop_platform.components.groundstation.connector import GroundstationConnector, GroundstationRegistrationItem, FramedContent
from satop_platform.components.restapi import exceptions
from .storageDatabase import StorageDatabase
from .flightPlan import FlightPlan, FlightPlanStatus

import uuid
from uuid import UUID

logger = logging.getLogger('plugin.scheduling')


class Scheduling(Plugin):
    def __init__(self, *args, **kwargs):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir, *args, **kwargs)

        if not self.check_required_capabilities(['http.add_routes']):
            raise RuntimeError

        self.api_router = APIRouter()

        self.data_dir = os.path.join(plugin_dir, 'data')
        os.makedirs(self.data_dir, exist_ok=True)

        self.data_base = None

        # ##############################
        # Save a flight plan
        # ##############################
        @self.api_router.post(
                '/save', 
                summary="Takes a flight plan and saves it for approval.",
                description="Takes a flight plan and saves it locally for later approval.",
                response_description="A message indicating the result of the scheduling or a dictionary with the message and the flight plan ID.",
                status_code=201, 
                dependencies=[Depends(self.platform_auth.require_login)]
                )
        async def new_flihtplan_schedule(flight_plan:FlightPlan, req: Request) -> dict[str, str] | str:
            user_id = req.state.userid

            if flight_plan.sat_name is None or flight_plan.sat_name == "":
                logger.info(f"User '{user_id}' sent flightplan for approval but was rejected due to: FLIGHTPLAN - MISSING REFERENCE TO SATELLITE")
                return "Rejected: Missing Satellite reference"
            
            if flight_plan.datetime is None or flight_plan.datetime == "":
                logger.info(f"User '{user_id}' sent flightplan for approval but was rejected due to: FLIGHTPLAN - MISSING DATETIME")
                return "Rejected: Missing datetime"
            # Check datetime format
            try:
                flight_plan.validate_datetime_format()
            except ValueError as e:
                logger.info(f"User '{user_id}' sent flightplan for approval but was rejected due to: FLIGHTPLAN - INVALID DATETIME FORMAT")
                return f"Rejected: {e}"
            
            if flight_plan.gs_id is None or flight_plan.gs_id == "":
                logger.info(f"User '{user_id}' sent flightplan for approval but was rejected due to: FLIGHTPLAN - MISSING REFERENCE TO GS ID")
                return "Rejected: Missing GS ID"

            # LOGGING: User saves flight plan - user action and flight plan artifact

            flight_plan_as_bytes = io.BytesIO(str(flight_plan).encode('utf-8'))
            try:
                # UUID based on the content of flight_plan_as_bytes
                artifact_in_id = self.sys_log.create_artifact(flight_plan_as_bytes, filename='detailed_flight_plan.json').sha1
                logger.info(f"Received new detailed flight plan with artifact ID: {artifact_in_id}, scheduled for approval")
            except sqlalchemy.exc.IntegrityError as e: 
                # Artifact already exists
                artifact_in_id = e.params[0]
                logger.info(f"Received existing detailed flight plan with artifact ID: {artifact_in_id}")

            # -- actual scheduling --
            
            flight_plan_uuid = artifact_in_id # TODO: For now I will keep it as is, but I am still not settled on the choice of UUID.
    
            # Save flight plan in the database
            save_fp_message: str | None = await self.__save_flight_plan(flight_plan=flight_plan, flight_plan_uuid=flight_plan_uuid, user_id=user_id)
            save_ap_message: str | None = await self.__save_approval(flight_plan_uuid, user_id)
            if save_fp_message or save_ap_message:
                save_message = f"Flight plan not saved due to '{save_fp_message}' and '{save_ap_message}'"
                return {
                "message": save_message
            }

            # -- end of scheduling --

            self.sys_log.log_event(models.Event(
                descriptor='FlightplanSaveEvent',
                relationships=[
                    models.EventObjectRelationship(
                        predicate=models.Predicate(descriptor='startedBy'),
                        object=models.Entity(type=models.EntityType.user, id=req.state.userid)
                        ),
                    models.EventObjectRelationship(
                        predicate=models.Predicate(descriptor='created'),
                        object=models.Artifact(sha1=artifact_in_id)
                        )
                    ]
                )
            )

            logger.warning(f"Flight plan scheduled for approval; flight plan id: {flight_plan_uuid}")

            return {
                "message": f"Flight plan scheduled for approval", 
                "fp_id": f"{flight_plan_uuid}"
            }
          
        # ##############################
        # Get a flight plan based on its ID
        # ##############################
        @self.api_router.get(
                '/get/{uuid}',
                summary="Get a flight plan",
                description="Get a stored flight plan based on its ID.",
                response_description="The flight plan",
                status_code=200,
                dependencies=[Depends(self.platform_auth.require_login)]
                )
        async def get_flight_plan(flight_plan_uuid:str, req: Request) -> FlightPlan:
            return await self.__get_flight_plan(flight_plan_uuid=flight_plan_uuid, user_id=req.state.userid)
        
        # ##############################
        # Get all flight plans
        # ##############################
        @self.api_router.get(
                '/get_all',
                summary="Get all flight plans",
                description="Get all stored flight plans.",
                response_description="A list of flight plans",
                status_code=200,
                dependencies=[Depends(self.platform_auth.require_login)]
                )
        async def get_all_flight_plans(req: Request) -> list[FlightPlan]:
            user_id = req.state.userid
            flight_plans = await self.data_base.get_all_flight_plans()
            if not flight_plans:
                logger.debug(f"User '{user_id}' requested all flight plans but none were found")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No flight plans found')
            
            logger.debug(f"User '{user_id}' requested all flight plans; Retrieved {len(flight_plans)} flight plans")
            return flight_plans

        
        # ##############################
        # Update a flight plan
        # ##############################
        # TODO: Go over this again as it may be implemented incorrectly (in relation to logging)
        @self.api_router.put(
                '/update/{uuid}',
                summary="Update a flight plan",
                description="Update a flight plan that has already been scheduled for approval.",
                response_description="A message indicating the result of the update",
                status_code=200,
                dependencies=[Depends(self.platform_auth.require_login)]
                )
        async def update_flight_plan(flight_plan_uuid:str, flight_plan:FlightPlan, req: Request) -> dict[str, str]:
            user_id = req.state.userid

            # Check if the flight plan exist in the database
            flight_plan_with_datetime = await self.__get_flight_plan(flight_plan_uuid=flight_plan_uuid, user_id=user_id)
            if not flight_plan_with_datetime:
                logger.debug(f"Flight plan with uuid '{flight_plan_uuid}' was requested by user '{user_id}' but was not found")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Flight plan not found')

            # LOGGING: User updates flight plan - user action and flight plan artifact
            flight_plan_as_bytes = io.BytesIO(str(flight_plan).encode('utf-8'))
            try:
                artifact_in_id = self.sys_log.create_artifact(flight_plan_as_bytes, filename='detailed_flight_plan.json').sha1
                logger.info(f"Received updated detailed flight plan with artifact ID: {artifact_in_id}, scheduled for approval")
            except sqlalchemy.exc.IntegrityError as e: 
                # Artifact already exists
                artifact_in_id = e.params[0]
                logger.info(f"Received existing detailed flight plan with artifact ID: {artifact_in_id}")

            # -- actual update --

            await self.__update_flight_plan(flight_plan=flight_plan, flight_plan_uuid=flight_plan_uuid)

            # -- end of update --

            self.sys_log.log_event(models.Event(
                descriptor='FlightplanUpdateEvent',
                relationships=[
                    models.EventObjectRelationship(
                        predicate=models.Predicate(descriptor='updatedBy'),
                        object=models.Entity(type=models.EntityType.user, id=user_id)
                        ),
                    models.EventObjectRelationship(
                        predicate=models.Predicate(descriptor='created'),
                        object=models.Artifact(sha1=artifact_in_id)
                        )
                    ]
                )
            )

            logger.info(f"Flight plan updated; flight plan id: {flight_plan_uuid}")

            return {"message": "Flight plan updated"}
            
        # ##############################
        # Approve a flight plan
        # ##############################
        @self.api_router.post(
                '/approve/{uuid}', 
                summary="Approve a flight plan for transmission to a ground station",
                description=
"""
Approve or reject a flight plan for transmission to a ground station.
The flight plan is identified by the UUID provided in the URL.

If the flight plan is rejected, it will not be sent to the ground station and will be removed from the local list of flight plans missing approval.

If the flight plan is approved, a message will first return to the sender acknowledging that the request was received, and then the approved flight plan will be compiled and sent to the ground station.
""",
                response_description="A message indicating the result of the approval",
                # responses={**exceptions.NotFound("Flight plan not found").response},
                status_code=202, 
                dependencies=[Depends(self.platform_auth.require_login)]
                )
        async def approve_flight_plan(flight_plan_uuid:str, approved:bool, request: Request, background_tasks: BackgroundTasks) -> dict[str, str]: # TODO: maybe require the GS id here instead.
            user_id = request.state.userid

            _flightplan_with_datetime: FlightPlan = await self.__get_flight_plan(flight_plan_uuid=flight_plan_uuid, user_id=user_id)
            _approved_flight_plan: FlightPlanStatus | None = await self.data_base.get_approval_index(flight_plan_uuid=flight_plan_uuid) 

            if not _flightplan_with_datetime:
                logger.debug(f"Flight plan with uuid '{flight_plan_uuid}' was requested by user '{user_id}' but was not found")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Flight plan not found or not scheduled for approval')

            if not _approved_flight_plan:
                logger.debug(f"Flight plan with uuid '{flight_plan_uuid}' was requested by user '{user_id}' but was not found in the approval index")
                pass
            elif _approved_flight_plan.approval_status:
                logger.debug(f"""Flight plan with uuid '{flight_plan_uuid}' was approved by user: '{user_id}', 
                             but has already been approved by user: '{_approved_flight_plan.approver}' at datetime: '{_approved_flight_plan.approval_date}'""")
                return {"message": "Flight plan already approved"}
                
            
            await self.__update_approval(flight_plan_uuid, user_id, approved)
            if not approved:
                logger.debug(f"Flight plan with uuid '{flight_plan_uuid}' was not approved by user: {user_id}")
                self.sys_log.log_event(models.Event(
                    descriptor='FlightplanApprovalEvent',
                    relationships=[
                        models.EventObjectRelationship(
                            predicate=models.Predicate(descriptor='rejectedBy'),
                            object=models.Entity(type=models.EntityType.user, id=user_id)
                            ),
                        models.EventObjectRelationship(
                            predicate=models.Predicate(descriptor='rejected'),
                            object=models.Artifact(sha1=flight_plan_uuid)
                            )
                        ]
                    )
                )
                return {"message": "Flight plan not approved by user"}
            logger.debug(f"Flight plan with uuid '{flight_plan_uuid}' was approved by user: {user_id}")

            
            logger.debug(f"found flight plan: {_flightplan_with_datetime}")

            # Compile the flight plan
            compiled_plan, artifact_id = await self.call_function("Compiler","compile", _flightplan_with_datetime.flight_plan, user_id)
            
            background_tasks.add_task(self._do_send_to_gs, flight_plan_uuid, compiled_plan, artifact_id, user_id)

            return {"message": "Flight plan approved and scheduled for transmission to ground station."}

    async def _do_send_to_gs(self, flight_plan_uuid, compiled_plan, artifact_id, user_id):
        """Send the compiled plan to the GS client

        Args:
            flight_plan_uuid (UUID): Identifier of the flight plan to approve
            compiled_plan (dict): The compiled flight plan
            artifact_id (str): Identifier of the compiled flight plan
            user_id (str): Identifier of the user who performed this action
        """
        # Send the compiled plan to the GS client
        logger.debug(f"\nsending compiled plan to GS: \n{compiled_plan}\n")

        flight_plan_with_datetime = await self.__get_flight_plan(flight_plan_uuid, user_id)
        if not flight_plan_with_datetime:
            logger.error(f"Flight plan with ID: '{flight_plan_uuid}' not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Flight plan not found')

        flight_plan_gs_id = UUID(flight_plan_with_datetime.gs_id)

        gs_rtn_msg = await self.send_to_gs(
                        artifact_id, 
                        compiled_plan, 
                        flight_plan_gs_id, 
                        flight_plan_with_datetime.datetime,
                        flight_plan_with_datetime.sat_name
                    )           
        logger.debug(f"GS response: {gs_rtn_msg}")


        self.sys_log.log_event(models.Event(
            descriptor='ApprovedForSendOffEvent',
            relationships=[
                models.EventObjectRelationship(
                    predicate=models.Predicate(descriptor='sentBy'),
                    object=models.Entity(type=models.EntityType.user, id=user_id)
                    ),
                models.EventObjectRelationship(
                    predicate=models.Predicate(descriptor='used'),
                    object=models.Artifact(sha1=artifact_id)
                    ),
                models.EventObjectRelationship(
                    predicate=models.Predicate(descriptor='sentTo'),
                    object=models.Entity(type='system',id=str(flight_plan_gs_id))
                    )
                ]
            )
        )
    
    # TODO: If artifact_id is not used, remove it from the function signature
    async def send_to_gs(self, artifact_id:str, compiled_plan:dict, gs_id:UUID, datetime:str, satellite:str):
        """Send the compiled plan to the GS client

        Args:
            artifact_id (str): Identifier of the compiled flight plan
            compiled_plan (dict): The compiled flight plan
            gs_id (UUID): Identifier of the ground station
            datetime (str): The datetime of the transmission
            satellite (str): The satellite to which the transmission is scheduled

        Returns:
            (str): The response from the GS client
        """
        gs = self.gs_connector.registered_groundstations.get(gs_id)
        if gs is None:
            logger.error(f"GS with id '{gs_id}' not found")
            return "GS not found"
        
        # Send the compiled plan to the GS client
        frame = FramedContent(
            header_data={
                'type' : 'schedule_transmission',
                'data' : {
                    'time' : datetime,
                    'satellite': satellite
                }
            },
            frames = [
                compiled_plan
            ]
        )

        return await self.gs_connector.send_control(gs_id, frame)


    async def __save_flight_plan(self, flight_plan:FlightPlan, flight_plan_uuid:str, user_id:str) -> str | None:
        """Save a flight plan in the database

        Args:
            flight_plan (FlightPlan): The flight plan to save
        """
        _existing_flight_plan: FlightPlan | None = None
        try:
            _existing_flight_plan = await self.__get_flight_plan(flight_plan_uuid, user_id=user_id)
        except HTTPException as e:
            if not e.status_code == status.HTTP_404_NOT_FOUND:
                # If the flight plan is not found, it is not an error
                # This is to ensure no problems with __get_flight_plan()
                raise e
        
        try:
            if _existing_flight_plan:
                logger.debug(f"Flight plan with ID: '{flight_plan_uuid}' already exists")
                return f"Flight plan already exists"
                # raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Flight plan already exists')
            
            await self.data_base.save_flight_plan(flight_plan, flight_plan_uuid)
            logger.debug(f"Saved flight plan with ID: '{flight_plan_uuid}': \n{flight_plan}")
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to save flight plan with ID: '{flight_plan_uuid}': \n{flight_plan}")
            logger.error(f"Error: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Failed to save flight plan')
        
    async def __save_approval(self, flight_plan_uuid:str, user_id:str) -> str | None:
        """Save the approval of a flight plan

        Args:
            flight_plan_uuid (str): The ID of the flight plan
            user_id (str): The ID of the user
        """
        
        try:
            if await self.data_base.get_approval_index(flight_plan_uuid):
                logger.debug(f"Approval index of flight plan with ID: '{flight_plan_uuid}' already exists")
                return "Approval index already exists"
                # raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Approval already exists')

            await self.data_base.save_approval(flight_plan_uuid, user_id)
            logger.debug(f"Saved approval of flight plan with ID: '{flight_plan_uuid}', approved by user: '{user_id}'")
        except Exception as e:
            logger.error(f"Failed to save approval of flight plan with ID: '{flight_plan_uuid}', approval attempted by user: '{user_id}'")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Failed to save approval')


    async def __update_flight_plan(self, flight_plan:FlightPlan, flight_plan_uuid:str) -> None:
        # """Update a flight plan based on its ID

        # Args:
        #     flight_plan (FlightPlan): The flight plan to update
        #     flight_plan_uuid (str): The ID of the flight plan
        # """
        # try:
        #     await self.data_base.update_flight_plan(flight_plan, flight_plan_uuid)
        #     logger.debug(f"Updated flight plan with ID: '{flight_plan_uuid}': \n{flight_plan}")
        # except Exception as e:
        #     logger.error(f"Failed to update flight plan with ID: '{flight_plan_uuid}': \n{flight_plan}")
        #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Failed to update flight plan')
        
        # TODO: Rethink how updates should occur (if a flight_plan is updated, a new one should be created and the old one should be marked as outdated or deleted instead... "Updating" is misleading as a new ID should be created every time a flight plan changes) 
        logger.error(f"Update flight plan not implemented yet")
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail='Update flight plan not implemented yet')
    

    async def __update_approval(self, flight_plan_uuid:str, user_id:str, approved:bool) -> None:
        """Update the approval of a flight plan

        Args:
            flight_plan_uuid (str): The ID of the flight plan
            user_id (str): The ID of the user
        """
        try:
            
            _existing_approval: FlightPlanStatus | None = await self.data_base.get_approval_index(flight_plan_uuid)
            # TODO: Either make it possible to update the approval when it has already been handled or make a DELETE method and API endpoint to remove the approval
            if not _existing_approval.approval_status == None:
                logger.debug(f"Flight plan with ID: '{flight_plan_uuid}' has already been handled by user: '{_existing_approval.approver}'")
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f'Flight plan already handled by user {_existing_approval.approver}; it was {"" if _existing_approval.approval_status else "not "}approved')



            await self.data_base.update_approval(flight_plan_uuid, approved, user_id)
            logger.debug(f"Updated approval of flight plan with ID: '{flight_plan_uuid}', approved by user: '{user_id}'")
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to update approval of flight plan with ID: '{flight_plan_uuid}', approval attempted by user: '{user_id}'")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Failed to update approval')

    async def __get_flight_plan(self, flight_plan_uuid:str, user_id:str) -> FlightPlan | None:
        """Get a flight plan based on its ID

        Args:
            flight_plan_uuid (str): The ID of the flight plan

        Returns:
            FlightPlan: The flight plan
        """
        try:
            _existing_flight_plan: FlightPlan | None = await self.data_base.get_flight_plan(flight_plan_uuid)
            if not _existing_flight_plan:
                logger.debug(f"Flight plan with ID: '{flight_plan_uuid}' not found")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Flight plan not found')
            
            logger.debug(f"User '{user_id}' requested flightplan with uuid: '{flight_plan_uuid}'; Retrieved flightplan with uuid: '{flight_plan_uuid}'")
            return _existing_flight_plan
        except HTTPException as e:
            logger.error(f"Failed to get flight plan with ID: '{flight_plan_uuid}'")
            raise e
        except Exception as e:
            logger.error(f"Failed to get flight plan with ID: '{flight_plan_uuid}'")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Failed to get flight plan')
        
    
    def startup(self):
        """Startup protocol for the plugin
        """
        super().startup()
        logger.info(f"Running '{self.name}' statup protocol")

        # TODO: Implement database connection test without using the plugin engine OR add await everywhere (This needs more thought) ... Maybe a seperate process or thread can be used.
        # logger.debug(f"Testing database connection")
        # database_tester = StorageDatabase(self.data_dir)
        # database_tester.__test_database(logger=logger)
        # logger.debug(f"Database connection test passed")
        
        self.data_base = StorageDatabase(self.data_dir)
    
    def shutdown(self):
        """Shutdown protocol for the plugin
        """
        super().shutdown()
        logger.info(f"'{self.name}' Shutting down gracefully")
        try:
            self.data_base.close_connection()
        except Exception as e:
            logger.error(f"Failed to close database connection: {e}")
            raise e