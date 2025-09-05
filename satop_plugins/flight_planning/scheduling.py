import io
import logging
import os
from uuid import UUID

import sqlalchemy
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from satop_platform.components.groundstation.connector import (
    FramedContent,
)
from satop_platform.components.syslog import models
from satop_platform.plugin_engine.plugin import Plugin

from .flightPlan import FlightPlan, FlightPlanStatus
from .storageDatabase import StorageDatabase

logger = logging.getLogger("plugin.scheduling")


class Scheduling(Plugin):
    def __init__(self, plugin_dir=None, app=None, data_dir=None, *args, **kwargs):
        if plugin_dir is None:
            plugin_dir = os.path.dirname(os.path.realpath(__file__))

        super().__init__(plugin_dir, app, data_dir)

        if not self.check_required_capabilities(["http.add_routes"]):
            raise RuntimeError

        self.api_router = APIRouter()
        self.data_dir = os.path.join(plugin_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.data_base: StorageDatabase | None = None

        # ##############################
        # Save a flight plan
        # ##############################
        @self.api_router.post(
            "/save",
            summary="Takes a flight plan and saves it for approval.",
            response_model=FlightPlan,
            status_code=201,
            dependencies=[Depends(self.platform_auth.require_login)],
        )
        async def new_flightplan_schedule(
            flight_plan: FlightPlan, req: Request
        ) -> FlightPlan:
            user_id = req.state.userid

            # Serialize the Pydantic model to JSON for logging
            flight_plan_as_bytes = io.BytesIO(
                flight_plan.model_dump_json().encode("utf-8")
            )
            try:
                artifact_in_id = self.sys_log.create_artifact(
                    flight_plan_as_bytes, filename="detailed_flight_plan.json"
                ).sha1
            except sqlalchemy.exc.IntegrityError as e:
                artifact_in_id = e.params[0]

            flight_plan_uuid = artifact_in_id

            # Save to the database
            save_fp_message = await self.__save_flight_plan(
                flight_plan=flight_plan,
                flight_plan_uuid=flight_plan_uuid,
                user_id=user_id,
            )
            save_ap_message: str | None = await self.__save_approval(
                flight_plan_uuid, str(user_id)
            )

            if save_fp_message or save_ap_message:
                message = f"Flight plan not saved: {save_fp_message}, {save_ap_message}"
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail=message
                )

            # Fetch the full plan to return it to the frontend.
            newly_created_plan = await self.__get_flight_plan(
                flight_plan_uuid, user_id=user_id
            )

            if not newly_created_plan:
                raise HTTPException(
                    status_code=500,
                    detail="Could not retrieve flight plan after saving.",
                )

            # Add the ID and status the frontend expects before returning
            newly_created_plan.id = flight_plan_uuid
            newly_created_plan.status = "pending"  # Hardcode initial status

            self.sys_log.log_event(
                models.Event(
                    descriptor="FlightplanSaveEvent",
                    relationships=[
                        models.EventObjectRelationship(
                            predicate=models.Predicate(descriptor="startedBy"),
                            object=models.Entity(
                                type=models.EntityType.user, id=str(req.state.userid)
                            ),
                        ),
                        models.EventObjectRelationship(
                            predicate=models.Predicate(descriptor="created"),
                            object=models.Artifact(sha1=flight_plan_uuid),
                        ),
                    ],
                )
            )

            logger.warning(
                f"Flight plan {flight_plan_uuid} created and scheduled for approval."
            )

            return newly_created_plan

        # ##############################
        # Get a flight plan based on its ID
        # ##############################

        @self.api_router.get(
            "/get/{uuid}",
            summary="Get a flight plan",
            description="Get a stored flight plan based on its ID.",
            response_model=FlightPlan,
            status_code=200,
            dependencies=[Depends(self.platform_auth.require_login)],
        )
        async def get_flight_plan(uuid: str, req: Request) -> FlightPlan:
            user_id = req.state.userid

            flight_plan = await self.__get_flight_plan(
                flight_plan_uuid=uuid, user_id=user_id
            )
            if flight_plan is None:
                raise HTTPException(status_code=404, detail="Flight plan not found")

            approval_status = await run_in_threadpool(
                self.data_base.get_approval_index, flight_plan_uuid=uuid
            )

            flight_plan.id = uuid
            if approval_status:
                if approval_status.approval_status is True:
                    flight_plan.status = "approved"
                elif approval_status.approval_status is False:
                    flight_plan.status = "rejected"
                else:
                    flight_plan.status = "pending"
            else:
                flight_plan.status = "unknown"

            return flight_plan

        # ##############################
        # Get all flight plans
        # ##############################
        @self.api_router.get(
            "/get_all",
            summary="Get all flight plans",
            description="Get all stored flight plans.",
            response_description="A list of flight plans with their IDs",
            status_code=200,
            dependencies=[Depends(self.platform_auth.require_login)],
        )
        async def get_all_flight_plans(req: Request) -> list[dict[str, str | dict]]:
            user_id = req.state.userid
            flight_plans_with_ids = await run_in_threadpool(
                self.data_base.get_all_flight_plans_with_ids
            )
            if not flight_plans_with_ids:
                logger.debug(
                    f"User '{user_id}' requested all flight plans but none were found"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No flight plans found",
                )

            logger.debug(
                f"User '{user_id}' requested all flight plans; Retrieved {len(flight_plans_with_ids)} flight plans"
            )
            return flight_plans_with_ids

        # ##############################
        # Update a flight plan
        # ##############################
        # TODO: Go over this again as it may be implemented incorrectly (in relation to logging)
        @self.api_router.put(
            "/update/{uuid}",
            summary="Update a flight plan",
            description="Update a flight plan that has already been scheduled for approval.",
            response_description="A message indicating the result of the update",
            status_code=200,
            dependencies=[Depends(self.platform_auth.require_login)],
        )
        async def update_flight_plan(
            uuid: str, flight_plan: FlightPlan, req: Request
        ) -> dict[str, str]:
            user_id = req.state.userid

            # Check if the flight plan exist in the database
            flight_plan_with_datetime = await self.__get_flight_plan(
                flight_plan_uuid=uuid, user_id=user_id
            )
            if not flight_plan_with_datetime:
                logger.debug(
                    f"Flight plan with uuid '{uuid}' was requested by user '{user_id}' but was not found"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Flight plan not found",
                )

            # LOGGING: User updates flight plan - user action and flight plan artifact
            flight_plan_as_bytes = io.BytesIO(str(flight_plan).encode("utf-8"))
            try:
                artifact_in_id = self.sys_log.create_artifact(
                    flight_plan_as_bytes, filename="detailed_flight_plan.json"
                ).sha1
                logger.info(
                    f"Received updated detailed flight plan with artifact ID: {artifact_in_id}, scheduled for approval"
                )
            except sqlalchemy.exc.IntegrityError as e:
                # Artifact already exists
                artifact_in_id = e.params[0]
                logger.info(
                    f"Received existing detailed flight plan with artifact ID: {artifact_in_id}"
                )

            # -- actual update --

            await self.__update_flight_plan(
                flight_plan=flight_plan, flight_plan_uuid=uuid
            )

            # -- end of update --

            self.sys_log.log_event(
                models.Event(
                    descriptor="FlightplanUpdateEvent",
                    relationships=[
                        models.EventObjectRelationship(
                            predicate=models.Predicate(descriptor="updatedBy"),
                            object=models.Entity(
                                type=models.EntityType.user, id=user_id
                            ),
                        ),
                        models.EventObjectRelationship(
                            predicate=models.Predicate(descriptor="created"),
                            object=models.Artifact(sha1=artifact_in_id),
                        ),
                    ],
                )
            )

            logger.info(f"Flight plan updated; flight plan id: {uuid}")

            return {"message": "Flight plan updated"}

        # ##############################
        # Approve a flight plan
        # ##############################
        @self.api_router.post(
            "/approve/{uuid}",
            summary="Approve a flight plan for transmission to a ground station",
            description="""
            Approve or reject a flight plan for transmission to a ground station.
            The flight plan is identified by the UUID provided in the URL.

            If the flight plan is rejected, it will not be sent to the ground station and will be removed from the local list of flight plans missing approval.

            If the flight plan is approved, a message will first return to the sender acknowledging that the request was received, and then the approved flight plan will be compiled and sent to the ground station.
            """,
            response_description="A message indicating the result of the approval",
            # responses={**exceptions.NotFound("Flight plan not found").response},
            status_code=202,
            dependencies=[Depends(self.platform_auth.require_login)],
        )
        async def approve_flight_plan(
            uuid: str,
            approved: bool,
            request: Request,
            background_tasks: BackgroundTasks,
        ) -> dict[str, str]:  # TODO: maybe require the GS id here instead.
            user_id = request.state.userid

            _flightplan_with_datetime: FlightPlan = await self.__get_flight_plan(
                flight_plan_uuid=uuid, user_id=user_id
            )
            _approved_flight_plan: FlightPlanStatus | None = await run_in_threadpool(
                self.data_base.get_approval_index, flight_plan_uuid=uuid
            )

            if not _flightplan_with_datetime:
                logger.debug(
                    f"Flight plan with uuid '{uuid}' was requested by user '{user_id}' but was not found"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Flight plan not found or not scheduled for approval",
                )

            if not _approved_flight_plan:
                logger.debug(
                    f"Flight plan with uuid '{uuid}' was requested by user '{user_id}' but was not found in the approval index"
                )
                pass
            elif _approved_flight_plan.approval_status:
                logger.debug(
                    f"""Flight plan with uuid '{uuid}' was approved by user: '{user_id}', 
                             but has already been approved by user: '{_approved_flight_plan.approver}' at datetime: '{_approved_flight_plan.approval_date}'"""
                )
                return {"message": "Flight plan already approved"}

            await self.__update_approval(uuid, str(user_id), approved)
            if not approved:
                logger.debug(
                    f"Flight plan with uuid '{uuid}' was not approved by user: {user_id}"
                )
                self.sys_log.log_event(
                    models.Event(
                        descriptor="FlightplanApprovalEvent",
                        relationships=[
                            models.EventObjectRelationship(
                                predicate=models.Predicate(descriptor="rejectedBy"),
                                object=models.Entity(
                                    type=models.EntityType.user, id=user_id
                                ),
                            ),
                            models.EventObjectRelationship(
                                predicate=models.Predicate(descriptor="rejected"),
                                object=models.Artifact(sha1=uuid),
                            ),
                        ],
                    )
                )
                return {"message": "Flight plan not approved by user"}
            logger.debug(
                f"Flight plan with uuid '{uuid}' was approved by user: {user_id}"
            )

            logger.debug(f"found flight plan: {_flightplan_with_datetime}")

            # Compile the flight plan
            compiled_plan, artifact_id = await self.call_function(
                "Compiler", "compile", _flightplan_with_datetime.flight_plan, user_id
            )

            background_tasks.add_task(
                self._do_send_to_gs, uuid, compiled_plan, artifact_id, user_id
            )

            return {
                "message": "Flight plan approved and scheduled for transmission to ground station."
            }

    async def _do_send_to_gs(
        self, flight_plan_uuid, compiled_plan, artifact_id, user_id
    ):
        """Send the compiled plan to the GS client

        Args:
            flight_plan_uuid (UUID): Identifier of the flight plan to approve
            compiled_plan (dict): The compiled flight plan
            artifact_id (str): Identifier of the compiled flight plan
            user_id (str): Identifier of the user who performed this action
        """
        # Send the compiled plan to the GS client
        logger.debug(f"\nsending compiled plan to GS: \n{compiled_plan}\n")

        flight_plan_with_datetime = await self.__get_flight_plan(
            flight_plan_uuid, user_id
        )
        if not flight_plan_with_datetime:
            logger.error(f"Flight plan with ID: '{flight_plan_uuid}' not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Flight plan not found"
            )

        flight_plan_gs_id = UUID(flight_plan_with_datetime.gs_id)

        gs_rtn_msg = await self.send_to_gs(
            artifact_id,
            compiled_plan,
            flight_plan_gs_id,
            flight_plan_with_datetime.datetime,
            flight_plan_with_datetime.sat_name,
        )
        logger.debug(f"GS response: {gs_rtn_msg}")

        self.sys_log.log_event(
            models.Event(
                descriptor="ApprovedForSendOffEvent",
                relationships=[
                    models.EventObjectRelationship(
                        predicate=models.Predicate(descriptor="sentBy"),
                        object=models.Entity(type=models.EntityType.user, id=user_id),
                    ),
                    models.EventObjectRelationship(
                        predicate=models.Predicate(descriptor="used"),
                        object=models.Artifact(sha1=artifact_id),
                    ),
                    models.EventObjectRelationship(
                        predicate=models.Predicate(descriptor="sentTo"),
                        object=models.Entity(type="system", id=str(flight_plan_gs_id)),
                    ),
                ],
            )
        )

    # TODO: If artifact_id is not used, remove it from the function signature
    async def send_to_gs(
        self,
        artifact_id: str,
        compiled_plan: dict,
        gs_id: UUID,
        datetime: str,
        satellite: str,
    ):
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
                "type": "schedule_transmission",
                "data": {"time": datetime, "satellite": satellite},
            },
            frames=[compiled_plan],
        )

        return await self.gs_connector.send_control(gs_id, frame)

    async def __save_flight_plan(
        self, flight_plan: FlightPlan, flight_plan_uuid: str, user_id: str
    ) -> str | None:
        _existing_flight_plan = await self.__get_flight_plan(flight_plan_uuid, user_id)
        if _existing_flight_plan:
            logger.debug(f"Flight plan with ID: '{flight_plan_uuid}' already exists")
            return "Flight plan already exists"

        try:
            await run_in_threadpool(
                self.data_base.save_flight_plan, flight_plan, flight_plan_uuid
            )
            logger.debug(f"Saved flight plan with ID: '{flight_plan_uuid}'")
            return None
        except Exception as e:
            logger.error(
                f"Failed to save flight plan with ID: '{flight_plan_uuid}': {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save flight plan",
            )

    async def __save_approval(self, flight_plan_uuid: str, user_id: str) -> str | None:
        approval_exists = await run_in_threadpool(
            self.data_base.get_approval_index, flight_plan_uuid
        )
        if approval_exists:
            logger.debug(
                f"Approval index for flight plan '{flight_plan_uuid}' already exists"
            )
            return "Approval index already exists"

        try:
            await run_in_threadpool(
                self.data_base.save_approval, flight_plan_uuid, user_id
            )
            logger.debug(f"Saved approval for flight plan '{flight_plan_uuid}'")
            return None
        except Exception as e:
            logger.error(
                f"Failed to save approval for flight plan '{flight_plan_uuid}': {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save approval",
            )

    async def __update_flight_plan(
        self, flight_plan: FlightPlan, flight_plan_uuid: str
    ) -> None:
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
        logger.error("Update flight plan not implemented yet")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Update flight plan not implemented yet",
        )

    async def __update_approval(
        self, flight_plan_uuid: str, user_id: str, approved: bool
    ) -> None:
        try:
            _existing_approval = await run_in_threadpool(
                self.data_base.get_approval_index, flight_plan_uuid
            )
            if _existing_approval and _existing_approval.approval_status is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Flight plan already handled by user {_existing_approval.approver}",
                )

            await run_in_threadpool(
                self.data_base.update_approval, flight_plan_uuid, approved, user_id
            )
            logger.debug(
                f"Updated approval of flight plan with ID: '{flight_plan_uuid}'"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update approval of flight plan with ID '{flight_plan_uuid}': {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update approval",
            )

    async def __get_flight_plan(
        self, flight_plan_uuid: str, user_id: str
    ) -> FlightPlan | None:
        try:
            # Use run_in_threadpool to call the synchronous DB method
            flight_plan = await run_in_threadpool(
                self.data_base.get_flight_plan, flight_plan_uuid
            )
            return flight_plan
        except Exception as e:
            logger.error(
                f"Unexpected database error getting flight plan with ID '{flight_plan_uuid}': {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error",
            )

    def startup(self):
        super().startup()
        logger.info(f"Running '{self.name}' startup protocol")
        self.data_base = StorageDatabase(self.data_dir)

    def shutdown(self):
        super().shutdown()
        logger.info(f"'{self.name}' Shutting down gracefully")
