from __future__ import annotations
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import logging
import uvicorn

from satop_platform.core.config import SatopConfig

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from satop_platform.components.authorization.auth import PlatformAuthorization
    from satop_platform.core.satop_application import SatOPApplication

logger = logging.getLogger(__name__)

class APIApplication:
    api_app: FastAPI
    authorization: PlatformAuthorization

    _api_config: SatopConfig
    _root_path: str
    _router: APIRouter

    def __init__(self, app: SatOPApplication, *args, **kwargs):
        #self._api_config = config.load_config('api.yml')
        self._api_config = SatopConfig('api')
        self._root_path = self._api_config.get('root_path', '/api') # type: ignore

        self.api_app = FastAPI(*args, **kwargs)
        
        # Add CORS middleware
        self.api_app.add_middleware(
            CORSMiddleware,
            allow_origins=self._api_config.get('cors_origins', ["*"]),  # Configure in api config or allow all
            allow_credentials=self._api_config.get('cors_allow_credentials', True),
            allow_methods=self._api_config.get('cors_allow_methods', ["*"]),  # Allow all methods
            allow_headers=self._api_config.get('cors_allow_headers', ["*"]),  # Allow all headers
        )
        
        self.authorization = app.auth
        self._router = APIRouter(prefix=self._root_path)

    def mount_plugin_router(self, plugin_name:str, plugin_router: APIRouter, tags: list[str] | None = None, plugin_path: str | None = None):
        """Mount a router from a plugin

        Args:
            plugin_name (str): Name of the plugin. 
            plugin_router (APIRouter): FastAPI Router configured for the plugin. If it doesn't have a prefix defined, this will be set to plugin_name.
            tags (list[str], optional): Tags describing the plugin in the auto docs. Defaults to plugin_name if none are set in the router itself
            plugin_path (str, optional): Path under which the plugin routes will be mounted. Defaults to '/plugins' or value of 'plugin_path' in the api.yml file.
        """
        # logger.debug(f"from restapi.mount_plugin_router... Name: {plugin_name}, Router: {plugin_router}, Tags: {tags}, Path: {plugin_path}")
        if tags is None and len(plugin_router.tags) == 0:
            tags = [plugin_name]

        if plugin_path is None:
            plugin_path = self._api_config.get('plugin_path', '/plugins')
            assert(isinstance(plugin_path, str))

        if plugin_router.prefix == '':
            plugin_path += '/' + plugin_name
        
        full_prefix = plugin_path + plugin_router.prefix

        logger.debug(f'Mounting route {full_prefix} for plugin API {plugin_name}')
        
        self.include_router(plugin_router, prefix=plugin_path, tags=tags)

    def include_router(self, *args, **kwargs):
        # TODO: DOCSTRING
        self._router.include_router(*args, **kwargs)
    
    # def list_routes(self):
    #     """List all non-generic routes registered in the API
    #     """
    #     routes = []
    #     for route in self.api_app.routes[4:]:
    #         routes.append({
    #             'path': route.path,
    #             'methods': route.methods,
    #             'name': route.name
    #         })
    #     return routes
    
    async def run_server(self, host="127.0.0.1", port=7889):
        self.api_app.include_router(self._router)
        
        host = self._api_config.get('host', host)
        port = self._api_config.get_int('port', port)

        # logger.debug(f"API app: {self.api_app}")
        # logger.debug(f"Listing routes custom: {self.list_routes()}")
        logger.info(f'Starting server on {host}:{port}')

        config = uvicorn.Config(self.api_app, host=host, port=port, log_level="info") # type: ignore
        server = uvicorn.Server(config)
        await server.serve()