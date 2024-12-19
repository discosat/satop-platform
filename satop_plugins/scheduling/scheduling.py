import os
from fastapi import APIRouter, Depends, Request
import logging

from satop_platform.plugin_engine.plugin import Plugin

logger = logging.getLogger('plugin.scheduling')

class Scheduling(Plugin):
    def __init__(self, *args, **kwargs):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir, *args, **kwargs)

        if not self.check_required_capabilities(['http.add_routes']):
            raise RuntimeError

        self.api_router = APIRouter()

        @self.api_router.post('/scheduling', status_code=201, dependencies=[Depends(self.platform_auth.require_login)])
        async def new_flihtplan_schedule(flight_plan:dict, request: Request):
            compiled_plan = await self.call_function("Compiler","compile", flight_plan, request)

            logger.debug(f"seding compiled plan to GS: \n{compiled_plan}")

    
    def startup(self):
        super().startup()
        logger.info(f"Running '{self.name}' statup protocol")
    
    def shutdown(self):
        super().shutdown()
        logger.info(f"'{self.name}' Shutting down gracefully")