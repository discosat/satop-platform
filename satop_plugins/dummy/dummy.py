import os
import logging
from satop_platform.plugin_engine.plugin import Plugin
from fastapi import APIRouter

logger = logging.getLogger('plugin.dummy')

class Dummy(Plugin):
    def __init__(self):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir)

        if not self.check_required_capabilities(['http.add_routes']):
            raise RuntimeError

        super().register_function('run', self.run)
        super().register_function('return_hello', self.return_hello)
    
    

    def run(self):
        logger.debug("Dummy plugin running")
    
    def return_hello(self):
        return "Hello from Dummy plugin"
    