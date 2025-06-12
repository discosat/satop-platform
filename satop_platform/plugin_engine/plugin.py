from collections.abc import Callable
from pathlib import Path
from typing import Any, Dict, Iterable, Union
import logging
from fastapi import APIRouter
import yaml
import typer

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from satop_platform.core.satop_application import SatOPApplication

app_type=Union["SatOPApplication"]

class Plugin:
    name: str
    config: dict
    data_dir: Path
    logger: logging.Logger
    app: app_type
    api_router: APIRouter|None = None
    cli: typer.Typer|None = None


    @classmethod
    def register_function(cls, func):
        """
        Decorator that marks a method for registration when a Plugin
        subclass is instantiated.
        """
        # custom attribute to flag that this method should be registered.
        func._register_as_plugin_function = True
        return func

    def __init__(self, plugin_dir: str, app:app_type, data_dir: Path):
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
        self.app = app
        
        self.platform_auth = app.auth
        self.gs_connector = app.gs
        self.sys_log = app.syslog

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

        return self.app.plugin_engine.call_plugin_method(plugin_name, func_name, *args, **kwargs)

    def list_functions(self) -> Dict[str, Dict[str, Callable]]:
        """
        List all registered functions.

        Returns:
            Dict[str, Dict[str, Callable]]: The entire function registry.
        """
        return self.app.plugin_engine.get_registered_plugin_methods()
    
    def check_required_capabilities(self, required: Iterable[str]):
        caps = set(self.config.get('capabilities', []))
        reqs = set(required)
        check = reqs.issubset(caps)
        
        if not check:
            self.logger.error(f'Plugin "{self.name}" does not have the required capabilities: {reqs - caps}')
        return check


class AuthenticationProviderPlugin(Plugin):
    def create_auth_token(self, user_id: str = "", uuid: str = "") -> str: 
        self.logger.warning('create_auth_token has not been initialized.')
        return ""

    def create_refresh_token(self, user_id: str = "", uuid: str = "") -> str:
        self.logger.warning('create_refresh_token has not been initialized')
        return ""

    def validate_token(self, token: str) -> dict[str, Any]:
        self.logger.warning('validate_token has not been initialized')
        return dict()