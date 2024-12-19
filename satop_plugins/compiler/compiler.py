import os
import logging
import io
from fastapi import APIRouter, Request, Depends
import sqlalchemy

from satop_platform.plugin_engine.plugin import Plugin
from satop_platform.components.syslog import models
from proc_comp.parser import parser
from proc_comp.codegen.codegen import CodeGen


logger = logging.getLogger('plugin.compilor')

class Compiler(Plugin):
    def __init__(self, *args, **kwargs):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir, *args, **kwargs)

        if not self.check_required_capabilities(['http.add_routes']):
            raise RuntimeError

        self.api_router = APIRouter()

        # Send in JSON and return compiled code
        @self.api_router.post('/compile', status_code=201, dependencies=[Depends(self.platform_auth.require_login)])
        async def new_compile(flight_plan:dict, request: Request):
            
            logger.info(f"Received new flight plan: {flight_plan}")

            flight_plan_as_bytes = io.BytesIO(await request.body())
            try:
                artifact_in_id = self.sys_log.create_artifact(flight_plan_as_bytes, filename='flight_plan.json').sha1
            except sqlalchemy.exc.IntegrityError as e: 
                # Artifact already exists
                artifact_in_id = e.params[0]
            
            ## --- Do the actual compilation here ---
            p = parser.parse(await request.json())
            if p is None:
                return {"message": "Error parsing flight plan"}
            
            G = CodeGen()
            compiled = G.code_gen(p)
            ## --- End of compilation ---

            compiled_as_bytes = "\n".join(compiled).encode('utf-8')
            try:
                artifact_out_id = self.sys_log.create_artifact(io.BytesIO(compiled_as_bytes), filename='flight_plan.csh').sha1
            except sqlalchemy.exc.IntegrityError as e: 
                # Artifact already exists
                artifact_out_id = e.params[0]

            self.sys_log.log_event(models.Event(
                descriptor='CSHCompileEvent',
                relationships=[
                    models.EventObjectRelationship(
                        predicate=models.Predicate(descriptor='startedBy'),
                        object=models.Entity(type=models.EntityType.user, id=request.state.userid)
                        ),
                    models.EventObjectRelationship(
                        predicate=models.Predicate(descriptor='used'),
                        object=models.Artifact(sha1=artifact_in_id)
                        ),
                    models.EventObjectRelationship(
                        predicate=models.Predicate(descriptor='created'),
                        object=models.Artifact(sha1=artifact_out_id)
                        ),
                    models.Triple(
                        subject=models.Artifact(sha1=artifact_out_id),
                        predicate=models.Predicate(descriptor='generatedFrom'),
                        object=models.Artifact(sha1=artifact_in_id)
                    )
                ]
            ))

            logger.info(f"\nCompiled flight_plan: \n{flight_plan} \nto \n{compiled}")

            return compiled
            

    def startup(self):
        super().startup()
        logger.info("Running Compilor statup protocol")

    def shutdown(self):
        super().shutdown()
        logger.info(f"'{self.name}' Shutting down gracefully")