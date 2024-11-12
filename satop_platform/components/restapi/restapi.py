from fastapi import FastAPI, APIRouter
from urllib.parse import urljoin
import logging
import uvicorn

from core import config

app = FastAPI(
    title="SatOP Platform API",
    description="Software platform for operations and control of satellite systems.",
    version='0.1.0-dev'
)

logger = logging.getLogger(__name__)

_api_config = config.load_config('api.yml')
_root_path = _api_config.get('root_path', '/api')

def mount_plugin_router(plugin_name:str, plugin_router: APIRouter, tags: list[str] = None, plugin_path: str=None):
    """Mount a router from a plugin

    Args:
        plugin_name (str): Name of the plugin. 
        plugin_router (APIRouter): FastAPI Router configured for the plugin. If it doesn't have a prefix defined, this will be set to plugin_name.
        tags (list[str], optional): Tags describing the plugin in the auto docs. Defaults to plugin_name if none are set in the router itself
        plugin_path (str, optional): Path under which the plugin routes will be mounted. Defaults to '/plugins' or value of 'plugin_path' in the api.yml file.
    """
    logger.debug(f"from restapi.mount_plugin_router... Name: {plugin_name}, Router: {plugin_router}, Tags: {tags}, Path: {plugin_path}")
    if tags is None and len(plugin_router.tags) == 0:
        tags = [plugin_name]

    if plugin_path is None:
        plugin_path = _api_config.get('plugin_path', '/plugins')
    plugin_path = _root_path + plugin_path

    if plugin_router.prefix == '':
        plugin_path += '/' + plugin_name
    
    full_prefix = plugin_path + plugin_router.prefix

    logger.debug(f'Mounting route {full_prefix} for plugin API {plugin_name}')
    try:
        # app.include_router(plugin_router, prefix=plugin_path, tags=tags)
        app.include_router(plugin_router)
        logger.debug(f"Successfully mounted plugin router {plugin_name}")
    except Exception as e:
        logger.error(f"Error mounting plugin router {plugin_name}: {e}")

def list_routes():
    """List all non-generic routes registered in the API
    """
    routes = []
    for route in app.routes[4:]:
        routes.append({
            'path': route.path,
            'methods': route.methods,
            'name': route.name
        })
    return routes

def run_server(host="127.0.0.1", port=7889):
    host = _api_config.get('host', host)
    port = _api_config.get('port', port)

    logger.debug(f"Listing routes custom: {list_routes()}")
    logger.info(f'Starting server on {host}:{port}')
    # uvicorn.run(app, host=host, port=port)
