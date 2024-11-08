import logging

class DummyDepender:
    def __init__(self):
        self.plugin_engine = None
        self.logger = logging.getLogger(__name__)

    def pre_init(self):
        pass

    def init(self):
        dummy_return_func = self.plugin_engine.get_function('Dummy', 'return_hello')
        if dummy_return_func:
            print(f"called dummy and got: {dummy_return_func()}")
        else:
            self.logger.warning("Dummy.return_hello not found")

    def post_init(self):
        self.plugin_engine.get_function('DummyDepender', 'run')()
        pass

    def run(self):
        print("DummyDepender plugin running")
        pass