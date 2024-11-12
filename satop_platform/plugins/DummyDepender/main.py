import logging
import os

from plugin_engine.plugin import Plugin

class DummyDepender(Plugin):
    def __init__(self):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir)

        self.plugin_engine = None
        self.logger = logging.getLogger(__name__)

    def pre_init(self):
        pass

    def init(self):
        super().register_function('run', self.run)

        dummy_return_func = super().call_function('Dummy', 'return_hello')
        if dummy_return_func:
            print(f"called dummy and got: {dummy_return_func}")
        else:
            self.logger.warning("Dummy.return_hello not found")

    def post_init(self):
        super().call_function('DummyDepender', 'run')
        pass

    def run(self):
        print("DummyDepender plugin running")
        pass