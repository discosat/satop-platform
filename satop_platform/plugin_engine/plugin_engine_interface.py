from collections.abc import Callable
from typing import Optional, Dict
import logging

class PluginEngineInterface:
    def __init__(self):
        '''
        Initializes the PluginEngineInterface with a registry for functions.
        The registry is a nested dictionary:
            {
                'PluginName': {
                    'function_name': callable_function,
                    ...
                },
                ...
            }
        '''
        self.functions: Dict[str, Dict[str, Callable]] = {}
        self.logger = logging.getLogger(__name__)
        # self.routes = {}  # Uncomment if you have route management

    def _register_function(self, plugin_name: str, func_name: str, func: Callable):
        """
        Register a callable function that can be accessed by other plugins.

        Args:
            plugin_name (str): Name of the plugin registering the function.
            func_name (str): Name of the function to register.
            func (Callable): The function object to register.

        Raises:
            ValueError: If the function is already registered by the same plugin.
        """
        if plugin_name not in self.functions:
            self.functions[plugin_name] = {}

        if func_name in self.functions[plugin_name]:
            raise ValueError(f"Function '{func_name}' is already registered by plugin '{plugin_name}'.")

        self.functions[plugin_name][func_name] = func
        self.logger.info(f"Registered function '{func_name}' from plugin '{plugin_name}'.")

    def get_function(self, plugin_name: Optional[str] = None, func_name: Optional[str] = None) -> Optional[Callable]:
        """
        Retrieve a registered function.

        Args:
            plugin_name (str, optional): Name of the plugin that registered the function.
            func_name (str, optional): Name of the function to retrieve.

        Returns:
            Callable or None: The requested function, or None if not found.

        Usage:
            - To get a specific function: get_function(plugin_name='PluginA', func_name='func1')
            - To search for a function across all plugins: get_function(func_name='func1')
        """
        if plugin_name and func_name:
            return self.functions.get(plugin_name, {}).get(func_name)
        elif func_name:
            # Search across all plugins for the function name
            for p_name, funcs in self.functions.items():
                if func_name in funcs:
                    return funcs[func_name]
            self.logger.warning(f"Function '{func_name}' not found in any plugin.")
            return None
        else:
            raise ValueError("At least func_name must be provided to retrieve a function.")

    def list_functions(self) -> Dict[str, Dict[str, Callable]]:
        """
        List all registered functions.

        Returns:
            Dict[str, Dict[str, Callable]]: The entire function registry.
        """
        return self.functions

    # def register_route(self, route, handler):
    #     """Register an API route with its corresponding handler."""
    #     if route in self.routes:
    #         raise ValueError(f"Route '{route}' is already registered.")
    #     self.routes[route] = handler
