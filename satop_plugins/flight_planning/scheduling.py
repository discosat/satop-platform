import io
import logging
import os
from uuid import UUID

import sqlalchemy
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from satop_platform.components.groundstation.connector import FramedContent
from satop_platform.components.syslog import models
from satop_platform.plugin_engine.plugin import Plugin

from .flightPlan import FlightPlan, FlightPlanStatusEnum, UpdateFlightPlanStatus
from .storageDatabase import StorageDatabase

logger = logging.getLogger("plugin.scheduling")


class Scheduling(Plugin):
    def __init__(self, plugin_dir=None, app=None, data_dir=None, *args, **kwargs):
        if plugin_dir is None:
            plugin_dir = os.path.dirname(os.path.realpath(__file__))

        super().__init__(plugin_dir, app, data_dir)

        if not self.check_required_capabilities(["http.add_routes"]):
            raise RuntimeError

        self.api_router = APIRouter(prefix="/flight-plans", tags=["Flight Plans"])
        self.data_dir = os.path.join(plugin_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.data_base: StorageDatabase | None = None

        # ######################################
        # CREATE a new Flight Plan
        # METHOD: POST /flight-plans
        # ######################################
        @self.api_router.post(
            "/",
            summary="Create a new flight plan for approval",
            response_model=FlightPlan,
            status_code=status.HTTP_201_CREATED,
            dependencies=[Depends(self.platform_auth.require_scope("scheduling.flightplan.create"))],
        )
        async def create_flight_plan(
            flight_plan: FlightPlan, req: Request
        ) -> FlightPlan:
            user_id = str(req.state.userid)

            flight_plan_as_bytes = io.BytesIO(
                flight_plan.model_dump_json().encode("utf-8")
            )
            try:
                artifact_id = self.sys_log.create_artifact(
                    flight_plan_as_bytes, filename="detailed_flight_plan.json"
                ).sha1
            except sqlalchemy.exc.IntegrityError as e:
                artifact_id = e.params[0]

            if await self.__get_flight_plan(artifact_id):
                 raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Flight plan with ID '{artifact_id}' already exists."
                )

            flight_plan.id = artifact_id
            flight_plan.status = FlightPlanStatusEnum.PENDING

            await self.__save_flight_plan(flight_plan)

            self.sys_log.log_event(
                models.Event(
                    descriptor="FlightplanCreatedEvent",
                    relationships=[
                        models.EventObjectRelationship(
                            predicate=models.Predicate(descriptor="createdBy"),
                            object=models.Entity(
                                type=models.EntityType.user, id=user_id
                            ),
                        ),
                        models.EventObjectRelationship(
                            predicate=models.Predicate(descriptor="created"),
                            object=models.Artifact(sha1=artifact_id),
                        ),
                    ],
                )
            )
            logger.info(
                f"Flight plan {artifact_id} created and is pending approval."
            )
            return flight_plan


        # ######################################
        # READ all Flight Plans
        # METHOD: GET /flight-plans
        # ######################################
        @self.api_router.get(
            "/",
            summary="Get all flight plans",
            response_model=list[FlightPlan],
            dependencies=[Depends(self.platform_auth.require_scope("scheduling.flightplan.read"))],
        )
        async def list_flight_plans() -> list[FlightPlan]:
            all_flight_plans = await run_in_threadpool(
                self.data_base.get_all_flight_plans
            )
            return all_flight_plans or []

        # ######################################
        # READ a single Flight Plan
        # METHOD: GET /flight-plans/{flight_plan_id}
        # ######################################
        @self.api_router.get(
            "/{flight_plan_id}",
            summary="Get a specific flight plan by its ID",
            response_model=FlightPlan,
            dependencies=[Depends(self.platform_auth.require_scope("scheduling.flightplan.read"))],
        )
        async def get_flight_plan(flight_plan_id: str) -> FlightPlan:
            flight_plan = await self.__get_flight_plan(flight_plan_id)
            if flight_plan is None:
                raise HTTPException(status_code=404, detail="Flight plan not found")
            return flight_plan

        # ######################################
        # UPDATE (create new version of) a Flight Plan
        # METHOD: PUT /flight-plans/{flight_plan_id}
        # ######################################
        @self.api_router.put(
            "/{flight_plan_id}",
            summary="Create a new version of a flight plan",
            description="Supersedes an existing flight plan and creates a new one. The new plan will be in 'pending' state.",
            response_model=FlightPlan,
            status_code=status.HTTP_201_CREATED,
            dependencies=[Depends(self.platform_auth.require_scope("scheduling.flightplan.update"))],
        )
        async def update_flight_plan(
            flight_plan_id: str, new_flight_plan_data: FlightPlan, req: Request
        ) -> FlightPlan:
            user_id = str(req.state.userid)

            original_plan = await self.__get_flight_plan(flight_plan_id)
            if not original_plan:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Original flight plan not found",
                )

            if original_plan.status != FlightPlanStatusEnum.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot update a flight plan with status '{original_plan.status}'. Only pending plans can be updated.",
                )

            new_flight_plan_data.status = FlightPlanStatusEnum.PENDING
            new_flight_plan_data.previous_plan_id = flight_plan_id

            flight_plan_as_bytes = io.BytesIO(
                new_flight_plan_data.model_dump_json().encode("utf-8")
            )
            try:
                new_artifact_id = self.sys_log.create_artifact(
                    flight_plan_as_bytes, filename="detailed_flight_plan.json"
                ).sha1
            except sqlalchemy.exc.IntegrityError as e:
                new_artifact_id = e.params[0]

            new_flight_plan_data.id = new_artifact_id

            await run_in_threadpool(
                self.data_base.supersede_and_create_flight_plan,
                old_plan_uuid=flight_plan_id,
                new_plan=new_flight_plan_data,
                new_plan_uuid=new_artifact_id,
            )

            self.sys_log.log_event(
                models.Event(
                    descriptor="FlightplanVersionCreatedEvent",
                    relationships=[
                        models.EventObjectRelationship(
                            predicate=models.Predicate(descriptor="createdBy"),
                            object=models.Entity(
                                type=models.EntityType.user, id=str(user_id)
                            ),
                        ),
                        models.EventObjectRelationship(
                            predicate=models.Predicate(descriptor="created"),
                            object=models.Artifact(sha1=new_artifact_id),
                        ),
                        models.EventObjectRelationship(
                            predicate=models.Predicate(descriptor="supersedes"),
                            object=models.Artifact(sha1=flight_plan_id),
                        ),
                    ],
                )
            )

            logger.info(
                f"New flight plan version '{new_artifact_id}' created, superseding '{flight_plan_id}'"
            )

            return new_flight_plan_data

        # ######################################
        # PARTIALLY UPDATE (approve/reject) a Flight Plan
        # METHOD: PATCH /flight-plans/{flight_plan_id}
        # ######################################
        @self.api_router.patch(
            "/{flight_plan_id}",
            summary="Approve or reject a flight plan",
            status_code=status.HTTP_202_ACCEPTED,
            response_description="Request accepted, processing in background if approved.",
            dependencies=[Depends(self.platform_auth.require_scope("scheduling.flightplan.approve"))],
        )
        async def set_flight_plan_status(
            flight_plan_id: str,
            update_data: UpdateFlightPlanStatus,
            request: Request,
            background_tasks: BackgroundTasks,
        ) -> dict[str, str]:
            user_id = str(request.state.userid)
            new_status = update_data.status

            if new_status not in [FlightPlanStatusEnum.APPROVED, FlightPlanStatusEnum.REJECTED]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This endpoint only accepts 'approved' or 'rejected' status."
                )

            rows_updated = await self.__update_flight_plan_approval_status(
                flight_plan_id, new_status, user_id
            )

            if rows_updated == 0:
                # This handles two cases: plan not found, or plan was not pending.
                flight_plan = await self.__get_flight_plan(flight_plan_id)
                if not flight_plan:
                    raise HTTPException(status_code=404, detail="Flight plan not found")
                else:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Flight plan has already been handled (status: {flight_plan.status})."
                    )

            # Log the event
            descriptor = "FlightplanApprovedEvent" if new_status == FlightPlanStatusEnum.APPROVED else "FlightplanRejectedEvent"
            predicate = "approvedBy" if new_status == FlightPlanStatusEnum.APPROVED else "rejectedBy"
            self.sys_log.log_event(
                models.Event(descriptor=descriptor, relationships=[
                    models.EventObjectRelationship(predicate=models.Predicate(descriptor=predicate), object=models.Entity(type=models.EntityType.user, id=user_id)),
                    models.EventObjectRelationship(predicate=models.Predicate(descriptor=new_status.value), object=models.Artifact(sha1=flight_plan_id))
                ])
            )

            if new_status == FlightPlanStatusEnum.APPROVED:
                logger.info(f"Flight plan '{flight_plan_id}' approved by user {user_id}. Scheduling transmission.")
                flight_plan = await self.__get_flight_plan(flight_plan_id) # Get updated plan

                commands_to_compile = flight_plan.flight_plan.model_dump().get("body", [])
                compiled_plan, artifact_id = await self.call_function(
                    "Compiler", "compile", commands_to_compile, user_id
                )
                background_tasks.add_task(
                    self._do_send_to_gs, flight_plan, compiled_plan, artifact_id, user_id
                )
                return {"message": "Flight plan approved and scheduled for transmission."}
            else: # Rejected
                logger.info(f"Flight plan '{flight_plan_id}' rejected by user {user_id}.")
                return {"message": "Flight plan rejected."}

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

    async def __get_flight_plan(self, flight_plan_id: str) -> FlightPlan | None:
        try:
            return await run_in_threadpool(
                self.data_base.get_flight_plan, flight_plan_id
            )
        except Exception as e:
            logger.error(
                f"Database error getting flight plan '{flight_plan_id}': {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected database error occurred.",
            )

    async def __save_flight_plan(self, flight_plan: FlightPlan):
        try:
            await run_in_threadpool(
                self.data_base.save_flight_plan, flight_plan
            )
        except Exception as e:
            logger.error(f"Failed to save flight plan '{flight_plan.id}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save flight plan.",
            )

    async def __update_flight_plan_approval_status(
        self, flight_plan_id: str, status: FlightPlanStatusEnum, user_id: str
    ) -> int:
        """Updates status and approver info, returns number of rows affected."""
        try:
            return await run_in_threadpool(
                self.data_base.update_flight_plan_approval_status,
                flight_plan_id,
                status,
                user_id,
            )
        except Exception as e:
            logger.error(f"Failed to update status for '{flight_plan_id}': {e}")
            raise HTTPException(
                status_code=500, detail="Failed to update flight plan status."
            )

    def startup(self):
        super().startup()
        logger.info(f"Running '{self.name}' startup protocol")
        self.data_base = StorageDatabase(self.data_dir)

    def shutdown(self):
        super().shutdown()
        logger.info(f"'{self.name}' Shutting down gracefully")
