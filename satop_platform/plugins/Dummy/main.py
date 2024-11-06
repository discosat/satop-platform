
class Dummy:
    def __init__(self, engine):
        self.engine = engine


    def pre_init(self):
        # print("Dummy plugin pre_init")
        pass

    def init(self):
        # print("Dummy plugin init")
        self.engine.register_function('dummy_run', self.run)

    def post_init(self):
        # print("Dummy plugin post_init")
        self.engine.get_function('dummy_run')()

    def run(self):
        print("Dummy plugin running")