import logging

class DummyDepender:
    def __init__(self, engine):
        self.engine = engine
        self.logger = logging.getLogger(__name__)

    def pre_init(self):
        self.engine.register_function('DummyDepender','run', self.run)
        pass

    def init(self):
        dummy_return_func = self.engine.get_function('Dummy', 'hello')
        if dummy_return_func:
            print(f"called dummy and got: {dummy_return_func()}")
        else:
            self.logger.warning("Dummy.hello not found")

    def post_init(self):
        self.engine.get_function('DummyDepender', 'run')()
        pass

    def run(self):
        print("DummyDepender plugin running")
        pass