import logging
from collections import defaultdict
import os
import yaml
import subprocess
import importlib.util

from plugin_engine.plugin_engine_interface import PluginEngineInterface


# Define terminal logging module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


_plugins_dir="plugins"
_plugins = {}
_plugin_engine_interface = PluginEngineInterface()
_load_order = []
_dependency_graph = defaultdict(list)


def _discover_plugins():
    '''
    Expects plugins to be located in the plugins directory
    
    Expects plugin structure as follows
        Package:
        - config.yaml
        - python main-plugin
    '''
    for plugin_name in os.listdir(_plugins_dir):
        plugin_path = os.path.join(_plugins_dir, plugin_name)
        if os.path.isdir(plugin_path):
            config_path = os.path.join(plugin_path, 'config.yaml')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                _plugins[plugin_name] = {
                    'config': config,
                    'path': plugin_path
                }
    logger.info(f"Discovered plugins: {list(_plugins.keys())}")


def _resolve_dependencies():
    '''
    Check for dependencies defined in each plugins config.yaml
    '''
    # Build dependency graph
    for plugin_name, plugin_info in _plugins.items():
        dependencies = plugin_info['config'].get('dependencies', [])
        for dep in dependencies:
            _dependency_graph[plugin_name].append(dep)
    
    # Topological sort
    visited = {}
    stack = []

    def visit(node):
        if node in visited:
            if not visited[node]:
                raise Exception(f"Circular dependency detected at {node}")
            return
        visited[node] = False
        for neighbor in _dependency_graph.get(node, []):
            if neighbor not in _plugins:
                raise Exception(f"Missing dependency: {neighbor} for plugin {node}")
            visit(neighbor)
        visited[node] = True
        stack.append(node)

    for plugin in _plugins:
        visit(plugin)

    load_order = stack
    logger.info(f"Plugin load order resolved: {load_order}")


def _install_requirements():
    '''
    Check for requirements defined in each plugins config.yaml and install
    '''
    all_requirements = []
    for plugin_info in _plugins.values():
        reqs = plugin_info['config'].get('requirements', [])
        all_requirements.extend(reqs)
    if all_requirements:
        logger.info(f"Installing requirements: {all_requirements}")
        subprocess.check_call(['pip', 'install'] + all_requirements)


def _load_plugins():
    '''
    Load plugins based on entrypoint defined in each plugins config.yaml

    Expects a setup(engine_interface:PluginEngineInterface) method in each plugin
    '''
    for plugin_name in _load_order:
        try:
            plugin_info = _plugins[plugin_name]
            entrypoint = plugin_info['config']['entrypoint']
            plugin_path = os.path.join(plugin_info['path'], entrypoint)
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # setup_func = getattr(module, 'setup')
            # plugin_instance = setup_func(engine_interface=_plugin_engine_interface)
            _plugins[plugin_name]['instance'] = plugin_instance
            logger.info(f"Loaded plugin: {plugin_name}")
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}")

def _initialize_plugins():
    '''
    Checks the plugin entrypoint for a "pre_init()", "init()" and "post_init()" method
     in each loaded plugin and executes these in order 

    Each init method is expected to be able to handle *args
    '''
    # Run pre-init hooks
    for plugin_name in _load_order:
        plugin = _plugins[plugin_name]['instance']
        if hasattr(plugin, 'pre_init'):
            try:
                plugin.pre_init(engine_interface=_plugin_engine_interface)
                logger.info(f"Executed pre_init for {plugin_name}")
            except Exception as e:
                logger.error(f"Error in pre_init of {plugin_name}: {e}")

    # Run init hooks
    for plugin_name in _load_order:
        plugin = _plugins[plugin_name]['instance']
        if hasattr(plugin, 'init'):
            try:
                plugin.init(engine_interface=_plugin_engine_interface)
                logger.info(f"Executed init for {plugin_name}")
            except Exception as e:
                logger.error(f"Error in init of {plugin_name}: {e}")
    
    # Run post-init hooks
    for plugin_name in _load_order:
        plugin = _plugins[plugin_name]['instance']
        if hasattr(plugin, 'post_init'):
            try:
                plugin.post_init(engine_interface=_plugin_engine_interface)
                logger.info(f"Executed post_init for {plugin_name}")
            except Exception as e:
                logger.error(f"Error in post_init of {plugin_name}: {e}")

def run_engine():
    '''
    Discover all plugins in the "plugins" directory (expected to be located in root satop_platform directory)

    Install all plugin requirements and check for dependencies

    Load and initialize all plugins in "plugins" directory
    '''
    _discover_plugins()
    _install_requirements()
    _resolve_dependencies()
    _load_plugins()
    _initialize_plugins()
