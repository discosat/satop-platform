import logging
from collections import defaultdict
import os
import yaml
import subprocess
import importlib.util

# from satop_platform.plugin_engine.plugin import PluginEngineInterface

# Define terminal logging module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global dictionaries to store plugins and their load order
_plugins = {}
_load_order = []

# _plugin_engine_interface = PluginEngineInterface()

def _discover_plugins():
    '''
    Expects plugins to be located in the plugins directory

    Expects plugin structure as follows
        Package:
        - config.yaml
        - python main-plugin
    '''
    file_path = os.path.dirname(os.path.realpath(__file__))
    plugins_path = os.path.join(file_path, '..', 'plugins')

    for plugin_name in os.listdir(plugins_path):
        plugin_path = os.path.join(plugins_path, plugin_name)
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
    '''
    Load plugins based on entrypoint defined in each plugin's config.yaml

    Assumes that the name of the plugin corresponds to the name of the entrypoint (case sensitive)
    '''
    for plugin_name in _load_order:
        try:
            plugin_info = _plugins[plugin_name]
            entrypoint = plugin_info['config']['entrypoint']
            plugin_path = os.path.join(plugin_info['path'], entrypoint)

            # Dynamically load the plugin module
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get the class from the module using the plugin name
            plugin_class = getattr(module, plugin_name)

            # Create an instance of the plugin
            plugin_instance = plugin_class()

            # Store the plugin instance before initialization
            _plugins[plugin_name]['instance'] = plugin_instance
            logger.info(f"Loaded plugin: {plugin_name}")
        except Exception as e:
            logger.error(f"Failed to load plugin '{plugin_name}': {e}")

def _initialize_plugins():
    '''
    Initializes plugins by executing their lifecycle methods and registering public functions.
    '''
    # Run pre-init hooks
    for plugin_name in _load_order:
        plugin = _plugins[plugin_name]['instance']
        if hasattr(plugin, 'pre_init') and callable(getattr(plugin, 'pre_init')):
            try:
                plugin.pre_init()
                logger.info(f"Finished executing pre_init for '{plugin_name}'")
            except Exception as e:
                logger.error(f"Error in pre_init of '{plugin_name}': {e}")

    # Run init hooks and register public functions
    for plugin_name in _load_order:
        plugin = _plugins[plugin_name]['instance']
        # config = _plugins[plugin_name]['config']
        # public_functions = config.get('public_functions', [])

        # Register public functions
        # for func_name in public_functions:
        #     func = getattr(plugin, func_name, None)
        #     if callable(func):
        #         try:
        #             _plugin_engine_interface._register_function(plugin_name, func_name, func)
        #         except Exception as e:
        #             logger.error(f"Failed to register function '{func_name}' from plugin '{plugin_name}': {e}")
        #     else:
        #         logger.warning(f"Public function '{func_name}' not found in plugin '{plugin_name}'.")

        # Execute init hook if present
        if hasattr(plugin, 'init') and callable(getattr(plugin, 'init')):
            try:
                plugin.init()
                logger.info(f"Finished executing init for '{plugin_name}'")
            except Exception as e:
                logger.error(f"Error in init of '{plugin_name}': {e}")

    # Run post-init hooks
    for plugin_name in _load_order:
        plugin = _plugins[plugin_name]['instance']
        if hasattr(plugin, 'post_init') and callable(getattr(plugin, 'post_init')):
            try:
                plugin.post_init()
                logger.info(f"Finished executing post_init for '{plugin_name}'")
            except Exception as e:
                logger.error(f"Error in post_init of '{plugin_name}': {e}")

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
