from collections.abc import Callable
from pathlib import Path
from typing import Dict, Iterable
import logging
from fastapi import APIRouter
import yaml
from satop_platform.components.authorization.auth import PlatformAuthorization
from satop_platform.components.groundstation.connector import GroundstationConnector
from satop_platform.components.syslog.syslog import Syslog
_functions = dict()


class Plugin:
    name: str
    config: dict
    data_dir: Path
    logger: logging.Logger
    api_router: APIRouter = None
    sys_log: Syslog = None

    @classmethod
    def register_function(cls, func):
        """
        Decorator that marks a method for registration when a Plugin
        subclass is instantiated.
        """
        # custom attribute to flag that this method should be registered.
        func._register_as_plugin_function = True
        return func


    def __init__(self, plugin_dir: str, data_dir: Path = None, platform_auth: PlatformAuthorization = None, gs_connector: GroundstationConnector = None): # TODO: this might be too exposed!
        """Initializes the plugin with its configuration.

        Args:
            plugin_dir (str): Path to the plugin directory.
            data_dir (Path, optional): Path to the data directory. Defaults to None.
            platform_auth (PlatformAuthorization, optional): Authorization provider. Defaults to None.
        """
        with open(plugin_dir + '/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        self.data_dir = data_dir

        self.config = config
        self.name = config['name']
        self.platform_auth = platform_auth
        self.gs_connector = gs_connector


        self.logger = logging.getLogger(__name__ + '.' + self.name)
        
        # Discover all methods that have _register_as_plugin_function=True
        # and register them in the global _functions dict
        self._discover_and_register()

    def _discover_and_register(self):
        """
        Inspects 'self' to find methods flagged by @Plugin.register_function
        and registers them in the global _functions dict.
        """
        # Initialize a dict for this plugin if not present
        if self.name not in _functions:
            _functions[self.name] = {}

        for attr_name in dir(self):
            method = getattr(self, attr_name)
            if callable(method) and getattr(method, '_register_as_plugin_function', False):
                func_name = method.__name__
                if func_name in _functions[self.name]:
                    raise ValueError(f"Function '{func_name}' already registered by plugin '{self.name}'.")
                
                # Register the method in the global registry
                _functions[self.name][func_name] = method
                self.logger.debug(f"Registered function '{func_name}' from plugin '{self.name}'.")
        

    # def _register_funciton(self):
    #     def decorator(func):
    #         self.register_function(func.__name__, func)
    #         return func

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


class AuthenticationProviderPlugin(Plugin):
    def create_auth_token(self, user_id: str):
        self.logger.warning('create_auth_token has not been initialized.')