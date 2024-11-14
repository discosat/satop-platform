from fastapi import FastAPI, APIRouter
import logging
import uvicorn

from core import config

logger = logging.getLogger(__name__)

class APIApplication:
    api_app: FastAPI

    _api_config: dict[str, any]
    _root_path: str

    def __init__(self, *args, **kwargs):
        self._api_config = config.load_config('api.yml')
        self._root_path = self._api_config.get('root_path', '/api')

        self.api_app = FastAPI(*args, **kwargs)

    def mount_plugin_router(self, plugin_name:str, plugin_router: APIRouter, tags: list[str] = None, plugin_path: str=None):
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
        plugin_path = self._root_path + plugin_path

        if plugin_router.prefix == '':
            plugin_path += '/' + plugin_name
        
        full_prefix = plugin_path + plugin_router.prefix

        logger.debug(f'Mounting route {full_prefix} for plugin API {plugin_name}')
        
        self.include_router(plugin_router, prefix=plugin_path, tags=tags)

    def include_router(self, *args, **kwargs):
        # TODO: DOCSTRING
        self.api_app.include_router(*args, **kwargs)
    
    def list_routes(self):
        """List all non-generic routes registered in the API
        """
        routes = []
        for route in self.api_app.routes[4:]:
            routes.append({
                'path': route.path,
                'methods': route.methods,
                'name': route.name
            })
        return routes
    
    def run_server(self, host="127.0.0.1", port=7889):
        host = self._api_config.get('host', host)
        port = self._api_config.get('port', port)

        logger.debug(f"API app: {self.api_app}")
        logger.debug(f"Listing routes custom: {self.list_routes()}")
        logger.info(f'Starting server on {host}:{port}')
        uvicorn.run(self.api_app, host=host, port=port)