class PluginEngineInterface:
    def __init__(self):
        '''Assumes that only one instance of this plugin will be initialised and then passed around'''
        self.functions = {}
        # self.routes = {}

    def register_function(self, plugin_name:str, func_name:str):
        """
        Register a callable function that can be accessed by other plugins.
        """
        if plugin_name in self.functions:
            raise ValueError(f"Function '{plugin_name}' is already registered.")
        self.functions[plugin_name] = func_name

    def get_function(self, name):
        """Retrieve a registered function by name."""
        return self.functions.get(name)

    # def register_route(self, route, handler):
    #     """Register an API route with its corresponding handler."""
    #     if route in self.routes:
    #         raise ValueError(f"Route '{route}' is already registered.")
    #     self.routes[route] = handler
