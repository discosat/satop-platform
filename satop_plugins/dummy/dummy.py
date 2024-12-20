import os
import logging
from satop_platform.plugin_engine.plugin import Plugin, register_function
from fastapi import APIRouter

logger = logging.getLogger('plugin.dummy')

class Dummy(Plugin):
    def __init__(self, *args, **kwargs):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir, *args, **kwargs)

        if not self.check_required_capabilities(['http.add_routes']):
            raise RuntimeError


        self.api_router = APIRouter()
        @self.api_router.get('/hello')
        async def __hello():
            return self.return_hello()
    
    def startup(self):
        super().startup()
        logger.info("Running Dummy statup protocol")

    @register_function
    def run(self):
        logger.debug("Dummy plugin running")
    
    @register_function
    def return_hello(self):
        return "Hello from Dummy plugin"
    
    def shutdown(self):
        super().shutdown()
        logger.info(f"'{self.name}' Shutting down gracefully")