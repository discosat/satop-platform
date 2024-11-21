import logging
from collections import defaultdict
import os
import sys
from fastapi import APIRouter
import yaml
import subprocess
import importlib.util
import re

from components.restapi import APIApplication


# Define terminal logging module
logger = logging.getLogger(__name__)

# TODO: Refactor the globals into the main engine method

# Global dictionaries to store plugins and their load order
_plugins = {}
_load_order = []


def _get_capabilities(plugin_name):
    return _plugins.get(plugin_name, {}).get('config', {}).get('capabilities', [])


def _discover_plugins():
    '''
    Expects plugins to be located in the plugins directory

    Expects plugin structure as follows
        Package:
        - config.yaml
        - python main-plugin
    '''
    file_path = os.path.dirname(os.path.realpath(__file__))
    plugins_path = os.path.join(file_path, '../..', 'satop_plugins')

    sys.path.append(plugins_path)

    for plugin_package in os.listdir(plugins_path):
        plugin_path = os.path.join(plugins_path, plugin_package)
        if os.path.isdir(plugin_path):
            config_path = os.path.join(plugin_path, 'config.yaml')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                assert "name" in config
                plugin_name = config.get('name')

                _plugins[plugin_name] = {
                    'config': config,
                    'path': plugin_path,
                    'package_name': plugin_package
                }
    logger.info(f"Discovered plugins: {list(_plugins.keys())}")

def _resolve_dependencies():
    '''
    Check for dependencies defined in each plugin's config.yaml
    '''
    dependency_graph = defaultdict(list)

    # Build dependency graph
    for plugin_name, plugin_info in _plugins.items():
        dependencies = plugin_info['config'].get('dependencies', [])
        for dep in dependencies:
            dependency_graph[plugin_name].append(dep)
    
    # Topological sort
    visited = {}
    stack = []

    def visit(node):
        if node in visited:
            if not visited[node]:
                raise Exception(f"Circular dependency detected at {node}")
            return
        visited[node] = False
        for neighbor in dependency_graph.get(node, []):
            if neighbor not in _plugins:
                raise Exception(f"Missing dependency: {neighbor} for plugin {node}")
            visit(neighbor)
        visited[node] = True
        stack.append(node)

    for plugin in _plugins:
        visit(plugin)

    global _load_order
    _load_order = stack
    logger.info(f"Plugin load order resolved: {_load_order}")

def _install_requirements():
    '''
    Check for requirements defined in each plugin's config.yaml and install
    '''
    all_requirements = []
    for plugin_info in _plugins.values():
        reqs = plugin_info['config'].get('requirements', [])
        all_requirements.extend(reqs)
    if all_requirements:
        logger.info(f"Installing requirements: {all_requirements}")
        try:
            subprocess.check_call(['pip', 'install'] + all_requirements)
            logger.info("Successfully installed all requirements.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install requirements: {e}")
            raise

def _load_plugins():
    """Load plugins found during discovery and dependency resolution
    """
    failed_plugins = []
    for plugin_name in _load_order:
        logger.debug(f'Trying to load {plugin_name}')
        try:
            plugin_info = _plugins[plugin_name]
            package_name = plugin_info.get('package_name')

            # Dynamically load the plugin module
            logger.debug(f'Importing plugin package "{package_name}"')
            module = importlib.import_module(f'{package_name}')

            # Create an instance of the plugin
            plugin_instance = module.PluginClass()

            # Store the plugin instance before initialization
            _plugins[plugin_name]['instance'] = plugin_instance
            logger.debug(f"Loaded plugin: {plugin_name}")
        except Exception as e:
            logger.error(f"Failed to load plugin '{plugin_name}': {e}")
            failed_plugins.append(plugin_name)

    for plugin_name in failed_plugins:
        logger.debug(f'Will not initialize "{plugin_name}" due to error in loading')
        _load_order.remove(plugin_name)
        del _plugins[plugin_name]
            

def _initialize_plugins(api: APIApplication):
    '''
    Initializes plugins by executing their lifecycle methods and registering public functions.
    '''

    # Run pre init init and post init
    for step in ['pre_init', 'init', 'post_init']:
        for plugin_name in _load_order:
            try:
                plugin = _plugins[plugin_name]['instance']
            except KeyError:
                logger.error(f'Plugin "{plugin_name}" cannot be instantiated')
                continue
            if hasattr(plugin, step) and callable(getattr(plugin, step)):
                try:
                    getattr(plugin, step)()
                    logger.debug(f"Finished executing {step} for '{plugin_name}'")
                except Exception as e:
                    logger.error(f"Error in {step} of '{plugin_name}': {e}")

    for plugin_name in _load_order:
        capabilities = _get_capabilities(plugin_name)
        if 'http.add_routes' in capabilities:
            router: APIRouter | None
            router = getattr(_plugins[plugin_name]['instance'], 'api_router')
            if router is None:
                continue

            plugin_name: str
            url_friendly_name = re.sub(r'(?<!^)(?=[A-Z])', '_', plugin_name).lower()
            url_friendly_name = re.sub(r'[^a-z0-9_]', '', url_friendly_name)

            if plugin_name != url_friendly_name:
                logger.warning(f'Path for plugin name "{plugin_name}" has been modified to "{url_friendly_name}" for URL safety and consistency')

            num_routes = len(router.routes)
            if num_routes > 0:
                logger.info(f"Plugin '{plugin_name}' has {num_routes} routes. Mounting...")
                api.mount_plugin_router(url_friendly_name, router)
        
        if 'security.authentication_provider' in capabilities:
            _plugins[plugin_name]['instance'].create_auth_token = lambda k, v: f'{k}: {v}'
            pass



def run_engine(api: APIApplication):
    '''
    Discover all plugins in the "plugins" directory (expected to be located in root satop_platform directory)

    Install all plugin requirements and check for dependencies

    Load and initialize all plugins in "plugins" directory
    '''
    _discover_plugins()
    _install_requirements()
    _resolve_dependencies()
    _load_plugins()
    _initialize_plugins(api)
