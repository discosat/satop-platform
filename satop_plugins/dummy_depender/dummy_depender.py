import logging
import os

from satop_platform.plugin_engine.plugin import Plugin

logger = logging.getLogger(__name__)


class DummyDepender(Plugin):
    def __init__(self, *args, **kwargs):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir, *args, **kwargs)

        self.plugin_engine = None

    def startup(self):
        super().startup()
        try:
            dummy_return_func = super().call_function("Dummy", "return_hello")
            if dummy_return_func:
                logger.debug(f"called dummy and got: {dummy_return_func}")
            else:
                logger.warning("Dummy.return_hello not found")
        except ValueError as e:
            logger.error(f"Error calling Dummy.return_hello: {e}")

    def post_init(self):
        super().call_function("DummyDepender", "run")
        pass

    @Plugin.register_function
    def run(self):
        logger.debug("DummyDepender plugin running")
        pass
