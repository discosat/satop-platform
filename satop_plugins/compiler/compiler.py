import os
import logging
import io
from fastapi import APIRouter, Request

from satop_platform.plugin_engine.plugin import Plugin
from satop_platform.components.syslog import models
from .parser import parser
from .codegen.codegen import CodeGen

logger = logging.getLogger('plugin.compilor')

class Compiler(Plugin):
    def __init__(self):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir)

        if not self.check_required_capabilities(['http.add_routes']):
            raise RuntimeError

        self.api_router = APIRouter()

        # Send in JSON and return compiled code
        @self.api_router.post('/compile', status_code=201)
        async def new_compile(flight_plan:dict, request: Request):
            logger.info(f"Received new flight plan: {flight_plan}")

            flight_plan_as_bytes = io.BytesIO(await request.body())
            artifact_in_id = self.sys_log.create_artifact(flight_plan_as_bytes, filename='flight_plan.json')

            self.sys_log.log_event(models.Event(
                subject = models.Entity(type='user', id="compilerTest"),
                predicate = models.Predicate(descriptor="Uploaded flight plan"),
                object = models.Entity(type='artifact', id=artifact_in_id)
            ))
            
            ## --- Do the actual compilation here ---
            p = parser.parse(await request.json())
            if p is None:
                return {"message": "Error parsing flight plan"}
            
            G = CodeGen()
            compiled = G.code_gen(p)
            ## --- End of compilation ---

            compiled_as_bytes = "\n".join(compiled).encode('utf-8')
            artifact_out_id = self.sys_log.create_artifact(io.BytesIO(compiled_as_bytes), filename='flight_plan.csh')
            
            self.sys_log.log_event(models.Event(
                subject = models.Entity(type='artifact', id=artifact_in_id),
                predicate = models.Predicate(descriptor="Compiled to"),
                object = models.Entity(type='artifact', id=artifact_out_id)
            ))

            logger.info(f"\nCompiled flight_plan: \n{flight_plan} \nto \n{compiled}")

            return compiled

    def startup(self):
        super().startup()
        logger.info("Running Compilor statup protocol")

    def shutdown(self):
        super().shutdown()
        logger.info(f"'{self.name}' Shutting down gracefully")