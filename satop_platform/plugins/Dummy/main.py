
class Dummy:
    def __init__(self, engine):
        self.engine = engine


    def pre_init(self):
        # print("Dummy plugin pre_init")
        pass

    def init(self):
        # print("Dummy plugin init")
        self.engine.register_function('Dummy', 'run', self.run)
        self.engine.register_function('Dummy', 'hello', self.return_hello)


    def post_init(self):
        # print("Dummy plugin post_init")
        self.engine.get_function('Dummy', 'run')()

    def run(self):
        print("Dummy plugin running")
    
    def return_hello(self):
        return "Hello from Dummy plugin"