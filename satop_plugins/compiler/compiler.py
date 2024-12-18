import os
import logging
from satop_platform.plugin_engine.plugin import Plugin
from fastapi import APIRouter

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
        @self.api_router.post('/compile')
        async def __compile(flight_plan: dict):
            logger.info("Received flight plan: \n") # TODO: Change to use sysLog 

            # Parse the flight plan
            p = parser.parse(flight_plan)
            if p is None:
                return {"message": "Error parsing flight plan"}
            
            G = CodeGen()
            compiled = G.code_gen(p)

            logger.debug(f"Compiled code: {compiled}")

            return compiled
        
        

    
    def startup(self):
        super().startup()
        logger.info("Running Compilor statup protocol")

    def shutdown(self):
        super().shutdown()
        logger.info(f"'{self.name}' Shutting down gracefully")