
class Dummy:
    def __init__(self):
        self.plugin_engine = None


    def pre_init(self):
        pass

    def init(self):
        pass

    def post_init(self):
        self.plugin_engine.get_function('Dummy', 'run')()

    def run(self):
        print("Dummy plugin running")
    
    def return_hello(self):
        return "Hello from Dummy plugin"