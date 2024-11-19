from collections.abc import Callable
from typing import Dict, Iterable
import logging
from fastapi import APIRouter
import yaml

_functions = dict()

class Plugin:
    name: str
    config: dict
    logger: logging.Logger
    api_router: APIRouter = None

    def __init__(self, plugin_dir: str):
        """Initializes the plugin with its configuration.

        Args:
            plugin_dir (str): Path to the plugin directory.
        """
        with open(plugin_dir + '/config.yaml', 'r') as f:
            config = yaml.safe_load(f)

        self.config = config
        self.name = config['name']

        self.logger = logging.getLogger(__name__ + '.' + self.name)

    def startup(self):
        """
        Runs on server Startup as plugins are loaded
        """
        pass

    def shutdown(self):
        """
        Runs on server shutdown
        TODO: shutdown dependency order???
        """
        pass

    def register_function(self, func_name: str, func: Callable):
        """
        Register a callable function that can be accessed by other plugins.

        Args:
            plugin_name (str): Name of the plugin registering the function.
            func_name (str): Name of the function to register.
            func (Callable): The function object to register.

        Raises:
            ValueError: If the function is already registered by the same plugin.
        """
        if self.name not in _functions:
            _functions[self.name] = dict()

        if func_name in _functions[self.name]:
            raise ValueError(f"Function '{func_name}' is already registered by plugin '{self.name}'.")

        _functions[self.name][func_name] = func


        self.logger.info(f"Registered function '{func_name}' from plugin '{self.name}'.")

    def call_function(self, plugin_name: str, func_name: str, *args, **kwargs):
        """Retreive and call a registered function.

        Args:
            plugin_name (str): Name of the plugin to call the function from.
            func_name (str): function name to call.
            *args: Arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Raises:
            ValueError: Raised if the plugin or function is not found.

        Returns:
            any: Return value of the called function.
        """

        p = _functions.get(plugin_name, None)
        if p is None:
            raise ValueError(f"Plugin '{plugin_name}' is not found or has not registered any functions.")
        
        f = p.get(func_name, None)
        if f is None:
            raise ValueError(f"Function '{func_name}' not found in plugin '{plugin_name}'.")


        return f(*args, **kwargs)

    def list_functions(self) -> Dict[str, Dict[str, Callable]]:
        """
        List all registered functions.

        Returns:
            Dict[str, Dict[str, Callable]]: The entire function registry.
        """
        return _functions
    
    def check_required_capabilities(self, required: Iterable[str]):
        caps = set(self.config.get('capabilities', []))
        reqs = set(required)
        check = reqs.issubset(caps)
        
        if not check:
            self.logger.error(f'Plugin "{self.name}" does not have the required capabilities: {reqs - caps}')
        return check