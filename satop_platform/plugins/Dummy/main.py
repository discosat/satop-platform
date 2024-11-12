import os
from plugin_engine.plugin import Plugin

class Dummy(Plugin):
    def __init__(self):
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        super().__init__(plugin_dir)
    

    def pre_init(self):
        pass

    def init(self):
        super().register_function('run', self.run)
        super().register_function('return_hello', self.return_hello)
        pass

    def post_init(self):
        super().call_function('Dummy', 'run')

    def run(self):
        print("Dummy plugin running")
    
    def return_hello(self):
        return "Hello from Dummy plugin"