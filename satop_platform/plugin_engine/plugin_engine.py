import importlib.util
import logging
import os
import re
import subprocess
import sys
from collections import defaultdict

import yaml
import networkx as nx
from fastapi import APIRouter

from satop_platform.core.config import merge_dicts
from components.restapi import APIApplication
from satop_platform.plugin_engine.plugin import Plugin


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

def _load_plugins(api: APIApplication):
    """Load plugins found during discovery and dependency resolution
    """
    failed_plugins = []
    for plugin_name in _load_order:
        logger.debug(f'Trying to load {plugin_name}')
        try:
            plugin_info = _plugins[plugin_name]
            package_name = plugin_info.get('package_name')
            config: dict = plugin_info.get('config', {})

            # Dynamically load the plugin module
            logger.debug(f'Importing plugin package "{package_name}"')
            module = importlib.import_module(f'{package_name}')

            # Create an instance of the plugin
            plugin_instance = module.PluginClass()

            # Store the plugin instance before initialization
            _plugins[plugin_name]['instance'] = plugin_instance
            logger.debug(f"Loaded plugin: {plugin_name}")

            caps = config.get('capabilities', [])
            print(caps)
            if plugin_instance.api_router:
                if 'http.add_routes' in caps:
                    _mount_plugin_router(plugin_instance, api)
                else:
                    raise RuntimeWarning(f"{plugin_name} has created a route but does not have the required capabilities to mount it. Ensure it has 'http.add_routes' in the plugin's 'config.yaml'")

            logger.info(f"Loaded plugin: {plugin_name}")
        except Exception as e:
            logger.error(f"Failed to load plugin '{plugin_name}': {e}")
            failed_plugins.append(plugin_name)

    for plugin_name in failed_plugins:
        logger.debug(f'Will not initialize "{plugin_name}" due to error in loading')
        _load_order.remove(plugin_name)
        del _plugins[plugin_name]
            

def _mount_plugin_router(plugin_instance: Plugin, api: APIApplication):
    '''
    Mount the router for a plugin
    '''
    router = plugin_instance.api_router
    if router is None:
        return

    plugin_name = plugin_instance.name
    url_friendly_name = plugin_name.lower().replace(' ', '_')
    url_friendly_name = re.sub(r'[^a-z0-9_]', '', url_friendly_name)

    if plugin_name != url_friendly_name:
        logger.warning(f'Path for plugin name "{plugin_name}" has been modified to "{url_friendly_name}" for URL safety and consistency')

    num_routes = len(router.routes)
    if num_routes > 0:
        logger.info(f"Plugin '{plugin_name}' has {num_routes} routes. Mounting...")
        api.mount_plugin_router(url_friendly_name, router)

def _graph_targets() -> dict[str, list[callable]]:
    G = nx.DiGraph()
    edges = set()

    G.add_node('satop.startup', function=lambda: logger.info('Running plugin start target'))
    G.add_node('satop.shutdown', function=lambda: logger.info('Running plugin shutdown target'))

    target_configs = {
        p.get('config',{}).get('name',''): p.get('config',{}).get('targets', [])
        for p in _plugins.values() if p
    }

    # Go through all plugins to find targets and dependencies (directed edges)
    for name, targets in target_configs.items():
        if not name:
            raise RuntimeError('Plugin config does not have a name. Cannot create targets')
        
        # Makes a root for startup and shutdown from which all startup
        #  and shutdown methods, respectfully, must be executed after
        # TODO: protect against malicious shutdown plugins (casuing shutdown to happen pematurely, by linking startup and shutdown)
        target_defaults = {
            'startup': {
                'function': 'startup',
                'after': [
                    'satop.startup'
                ]
            }, 
            'shutdown': {
                'function': 'shutdown',
                'after': [
                    'satop.shutdown'
                ]
            }
        }

        targets = merge_dicts(target_defaults, targets)

        for target_name, details in targets.items():
            target_id = f'{name}.{target_name}'
            function = None
            function_name = details.get('function', None)
            if function_name:
                function = getattr(_plugins.get(name,{}).get('instance'), function_name)

            G.add_node(target_id, function=function)

            for t in details.get('before', []):
                edges.add((target_id, t))
            for t in details.get('after', []):
                edges.add((t, target_id))

    # Check all edges are valid (targets exist)
    for p, q in edges:
        if not G.has_node(p):
            raise RuntimeWarning(f'Target graph is missing node "{p}" ({p} -> {q})')
        if not G.has_node(q):
            raise RuntimeWarning(f'Target graph is missing node "{q}" ({p} -> {q})')

        G.add_edge(p, q)


    # Ensure no cycles 
    # find all independent graphs
    # iterate through each and mark visited 
    try:
        c = nx.find_cycle(G, orientation="original")
        raise RuntimeError(f"Found cycle in graph during target discovery: {c}")
    except nx.NetworkXNoCycle:
        # No cycle found
        pass

    # Create shutdown and startup call lists
    trees = dict()
    for component in nx.weakly_connected_components(G):
        G_sub = G.subgraph(component)
        root = [n for n,d in G_sub.in_degree() if d == 0]
        if len(root) > 1:
            logger.error(f'Multiple roots in target graph: {root}')
        trees[root[0]] = [(node, G.nodes[node]) for node in nx.topological_sort(G_sub)]

    logger.debug(f'Target graph root nodes: {trees.keys()}')

    return trees

def execute_target(graph, target_root):
    targets = graph.get(target_root, [])
    for target_name, target_attrs in targets:
        fun = target_attrs.get('function')
        if fun:
            logger.info(f'Running target {target_name}')
            fun()
        

def run_engine(api: APIApplication):
    '''
    Discover all plugins in the "plugins" directory (expected to be located in root satop_platform directory)

    Install all plugin requirements and check for dependencies

    Load and initialize all plugins in "plugins" directory
    '''
    _discover_plugins()
    _install_requirements()
    _resolve_dependencies()
    _load_plugins(api)
    target_graphs = _graph_targets()
    execute_target(target_graphs, 'satop.startup')
