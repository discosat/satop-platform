import os
import logging
from satop_platform.plugin_engine.plugin import Plugin
from fastapi import APIRouter

logger = logging.getLogger('plugin.dummy')

class Dummy(Plugin):
    def __init__(self):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir)
    
    def pre_init(self):
        pass

    def init(self):
        super().register_function('run', self.run)
        super().register_function('return_hello', self.return_hello)

        self.api_router = APIRouter()

        @self.api_router.get("/hello")
        async def __hello():
            return {"message": "Hello from Dummy plugin"}


    def post_init(self):
        super().call_function('Dummy', 'run')

    def run(self):
        logger.debug("Dummy plugin running")
    
    def return_hello(self):
        return "Hello from Dummy plugin"
    