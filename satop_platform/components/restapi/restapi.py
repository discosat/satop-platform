from fastapi import FastAPI, APIRouter
from urllib.parse import urljoin
import logging
import uvicorn

app = FastAPI()

logger = logging.getLogger(__name__)

def mount_plugin_router(plugin_name:str, plugin_router: APIRouter, tags: list[str] = None, plugin_path: str=None):
    """Mount a router from a plugin

    Args:
        plugin_name (str): Name of the plugin. 
        plugin_router (APIRouter): FastAPI Router configured for the plugin. If it doesn't have a prefix defined, this will be set to 
        tags (list[str], optional): _description_
        plugin_path (str, optional): _description_. Defaults to '/plugins'.
    """
    if tags is None:
        tags = [plugin_name]

    if plugin_router.prefix == '':
        plugin_router.prefix = plugin_name
    
    full_prefix = plugin_path + plugin_router.prefix

    logger.debug(f'Mounting route {full_prefix} for plugin API {plugin_name}')

    app.include_router(plugin_router, prefix=plugin_path)

def run_server(host="127.0.0.1", port=7889):
    logger.info(f'Starting server on {host}:{port}')
    uvicorn.run(app, host=host, port=port)
