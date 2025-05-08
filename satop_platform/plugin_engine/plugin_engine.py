from __future__ import annotations

import importlib.util
import logging
import os
import re
import subprocess
import sys
import traceback
from collections import defaultdict
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import networkx as nx
import yaml

import satop_platform.core.config
from satop_platform.components.restapi import exceptions
from satop_platform.core.config import merge_dicts
from satop_platform.plugin_engine.plugin import AuthenticationProviderPlugin, Plugin

if TYPE_CHECKING:
    from satop_platform.core.satop_application import SatOPApplication

# Define terminal logging module
logger = logging.getLogger(__name__)


@dataclass
class PluginDictItem:
    config: dict[str, any]
    path: str
    package_name: str
    instance: Optional[Plugin] = None


class SatopPluginEngine:
    _plugins: dict[str, PluginDictItem]
    _load_order: list
    _registered_plugin_methods: dict[str, dict[str, callable]]
    app: SatOPApplication

    def __init__(self, app: SatOPApplication):
        self._plugins = dict()
        self._load_order = dict()
        self._registered_plugin_methods = dict()
        self.app = app

        logger.debug(self.app.event_manager.subscriptions)

    def __del__(self):
        for name, p in self._plugins.items():
            if p.instance:
                del p.instance
                p.instance = None

    def _get_capabilities(self, plugin_name):
        return (
            self._plugins.get(plugin_name, {}).get("config", {}).get("capabilities", [])
        )

    def _discover_plugins(self, force_rediscover=False):
        """
        Expects plugins to be located in the plugins directory

        Expects plugin structure as follows
            Package:
            - config.yaml
            - python main-plugin
        """
        file_path = os.path.dirname(os.path.realpath(__file__))
        default_plugins = Path(os.path.join(file_path, "../..", "satop_plugins"))
        user_plugins = satop_platform.core.config.get_root_data_folder() / "plugins"

        if self._plugins and not force_rediscover:
            return

        self._plugins = dict()

        if default_plugins.as_posix() not in sys.path:
            sys.path.append(default_plugins.as_posix())
        if user_plugins.as_posix() not in sys.path:
            sys.path.append(user_plugins.as_posix())

        disabled_plugins = []
        if (user_plugins / "disabled.txt").exists():
            logger.debug('Loading disabled plugins')
            with open(user_plugins / "disabled.txt", 'r') as f:
                lines = f.readlines()
                for l in lines:
                    ls = l.strip()
                    if len(ls) == 0 or ls[0] == '#':
                        continue
                    disabled_plugins.append(ls)
        else:
            logger.debug('No disabled.txt file found')
        if disabled_plugins:
            logger.debug(f'Disabled plugins: {disabled_plugins}')

        plugin_paths: list[Path] = []
        for plugin_path in chain(default_plugins.glob("*/"), user_plugins.glob("*/")):
            plugin_paths.append(plugin_path.absolute())

        for plugin_path in plugin_paths:
            if os.path.isdir(plugin_path):
                config_path = os.path.join(plugin_path, "config.yaml")
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        config = yaml.safe_load(f)
                    assert "name" in config
                    plugin_name = config.get("name")

                    if plugin_path.parts[-1] in disabled_plugins or plugin_name in disabled_plugins:
                        logger.info(f'Plugin {plugin_name} found but has been disabled and will not be loaded')
                        continue

                    self._plugins[plugin_name] = PluginDictItem(
                        config, plugin_path.as_posix(), plugin_path.name
                    )
        logger.info(f"Discovered plugins: {list(self._plugins.keys())}")

    def _resolve_dependencies(self):
        """
        Check for dependencies defined in each plugin's config.yaml
        """
        dependency_graph = defaultdict(list)

        # Build dependency graph
        for plugin_name, plugin_info in self._plugins.items():
            dependencies = plugin_info.config.get("dependencies", [])
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
                if neighbor not in self._plugins:
                    raise Exception(f"Missing dependency: {neighbor} for plugin {node}")
                visit(neighbor)
            visited[node] = True
            stack.append(node)

        for plugin in self._plugins:
            visit(plugin)

        self._load_order = stack
        logger.info(f"Plugin load order resolved: {self._load_order}")

    def _install_requirements(self):
        """
        Check for requirements defined in each plugin's config.yaml and install
        """
        all_requirements = set()
        for plugin_info in self._plugins.values():
            reqs = set(plugin_info.config.get("requirements", []))
            all_requirements = all_requirements | reqs

        for req in all_requirements:
            try:
                logger.info(f"Installing requirements: {all_requirements}")
                if req.startswith("git+"):
                    logger.warning(
                        f"Git requirement '{req}' will be upgraded to latest version"
                    )
                    subprocess.check_call(["pip", "install", "--user", "--upgrade", req])
                else:
                    subprocess.check_call(["pip", "install", "--user", req])
                logger.info("Successfully installed all requirements.")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install requirements: {e}")
                raise

    def _load_plugins(self):
        """Load plugins found during discovery and dependency resolution"""

        failed_plugins = []
        for plugin_name in self._load_order:
            logger.debug(f"Trying to load {plugin_name}")
            try:
                plugin_info = self._plugins[plugin_name]
                package_name = plugin_info.package_name
                config = plugin_info.config

                # Dynamically load the plugin module
                logger.debug(f'Importing plugin package "{package_name}"')
                module = importlib.import_module(f"{package_name}")

                # Create an instance of the plugin
                plugin_data_dir = (
                    satop_platform.core.config.get_root_data_folder()
                    / "plugin_data"
                    / plugin_name
                )
                plugin_instance = module.PluginClass(
                    data_dir=plugin_data_dir, app=self.app
                )

                # Register flagged methods
                for attr_name in dir(plugin_instance):
                    method = getattr(plugin_instance, attr_name)
                    if callable(method) and getattr(
                        method, "_register_as_plugin_function", False
                    ):
                        method_name = method.__name__
                        self._register_plugin_method(plugin_name, method_name, method)

                # Store the plugin instance before initialization
                plugin_info.instance = plugin_instance

                # Set the API router, if any
                caps = config.get("capabilities", [])
                # print(caps)
                if plugin_instance.api_router:
                    if "http.add_routes" in caps:
                        self._mount_plugin_router(plugin_instance)
                    else:
                        logger.warning(
                            f"{plugin_name} has created a route but does not have the required capabilities to mount it. Ensure it has 'http.add_routes' in the plugin's 'config.yaml'"
                        )
                        raise RuntimeWarning(
                            f"{plugin_name} has created a route but does not have the required capabilities to mount it. Ensure it has 'http.add_routes' in the plugin's 'config.yaml'"
                        )
                if "security.authentication_provider" in caps:
                    self._register_authentication_plugins(plugin_instance)

                logger.info(f"Loaded plugin: {plugin_name}")

            except Exception as e:
                logger.error(f"Failed to load plugin '{plugin_name}': {e}")
                print(traceback.format_exc())
                failed_plugins.append(plugin_name)

        for plugin_name in failed_plugins:
            logger.debug(f'Will not initialize "{plugin_name}" due to error in loading')
            self._load_order.remove(plugin_name)
            del self._plugins[plugin_name]

    def _mount_plugin_router(self, plugin_instance: Plugin):
        """
        Mount the router for a plugin
        """
        router = plugin_instance.api_router
        if router is None:
            return

        plugin_name = plugin_instance.name
        url_friendly_name = plugin_name.lower().replace(" ", "_")
        url_friendly_name = re.sub(r"[^a-z0-9_]", "", url_friendly_name)

        if plugin_name != url_friendly_name:
            logger.warning(
                f'Path for plugin name "{plugin_name}" has been modified to "{url_friendly_name}" for URL safety and consistency'
            )

        num_routes = len(router.routes)
        if num_routes > 0:
            logger.info(f"Plugin '{plugin_name}' has {num_routes} routes. Mounting...")
            self.app.api.mount_plugin_router(url_friendly_name, router)

    def _register_authentication_plugins(
        self, plugin_instance: AuthenticationProviderPlugin
    ):
        plugin_name = plugin_instance.name

        config = self._plugins.get(plugin_name).config
        provider_config = config.get("authentication_provider")

        provider_key = plugin_name
        identifier_hint = None

        if provider_config:
            provider_key = provider_config.get("provider_key", provider_key)
            identifier_hint = provider_config.get("identifier_hint", identifier_hint)

        # Register provider
        self.app.auth.register_provider(provider_key, identifier_hint)

        def _get_auth_token(user_id: str = "", uuid: str = ""):
            if user_id != "":
                # Login
                # Get uuid
                uuid = self.app.api.authorization.get_uuid(provider_key, user_id)
                if not uuid:
                    raise exceptions.InvalidCredentials
                # TODO: Make it possible for plugin to specify expiry, e.g. for long-lived application keys
                token = self.app.api.authorization.create_token(uuid)
                return token
            else:
                # Refresh
                token = self.app.api.authorization.create_token(uuid)
                return token
    
        def _get_refresh_token(user_id: str = "", uuid: str = ""):
            if user_id != "":
                # Login
                uuid = self.app.api.authorization.get_uuid(provider_key, user_id)
                if not uuid:
                    raise exceptions.InvalidCredentials
                # TODO: Make it possible for plugin to specify expiry, e.g. for long-lived application keys
                token = self.app.api.authorization.create_refresh_token(uuid)
                return token
            else:
                # Refresh
                token = self.app.api.authorization.create_refresh_token(uuid)
                return token
        
        def _validate_token(token: str):
            payload = self.app.api.authorization.validate_tokens(token)
            return payload

        self._plugins.get(plugin_name).instance.create_auth_token = _get_auth_token
        self._plugins.get(plugin_name).instance.create_refresh_token = _get_refresh_token
        self._plugins.get(plugin_name).instance.validate_token = _validate_token

    def _graph_targets(self) -> dict[str, list[callable]]:
        G = nx.DiGraph()
        edges = set()

        G.add_node(
            "satop.startup", function=lambda: logger.info("Running plugin start target")
        )
        G.add_node(
            "satop.shutdown",
            function=lambda: logger.info("Running plugin shutdown target"),
        )

        target_configs = {
            p.config.get("name", ""): p.config.get("targets", dict())
            for p in self._plugins.values()
            if p
        }

        # Go through all plugins to find targets and dependencies (directed edges)
        for name, targets in target_configs.items():
            if not name:
                logger.error(
                    "Plugin config does not have a name. Cannot create targets"
                )
                raise RuntimeError(
                    "Plugin config does not have a name. Cannot create targets"
                )

            # Makes a root for startup and shutdown from which all startup
            #  and shutdown methods, respectfully, must be executed after
            # TODO: protect against malicious shutdown plugins (casuing shutdown to happen pematurely, by linking startup and shutdown)
            target_defaults = {
                "startup": {"function": "startup", "after": ["satop.startup"]},
                "shutdown": {"function": "shutdown", "after": ["satop.shutdown"]},
            }

            targets = merge_dicts(target_defaults, targets)

            for target_name, details in targets.items():
                target_id = f"{name}.{target_name}"
                function = None
                function_name = details.get("function", None)
                if not function_name and target_name not in ["startup", "shutdown"]:
                    logger.warning(
                        f'No function specified for target "{target_name}" in plugin "{name}"'
                    )
                    raise RuntimeError(
                        f'No function specified for target "{target_name}" in plugin "{name}"'
                    )
                if function_name:
                    inst = self._plugins.get(name).instance
                    if inst is None:
                        logger.error(
                            f'Plugin instance not initialized for plugin "{name}"'
                        )
                        raise RuntimeError("Plugin instance not initialized")
                    function = getattr(inst, function_name)

                G.add_node(target_id, function=function)

                for t in details.get("before", []):
                    edges.add((target_id, t))
                for t in details.get("after", []):
                    edges.add((t, target_id))

        # Check all edges are valid (targets exist)
        for p, q in edges:
            if not G.has_node(p):
                logger.error(f'Target graph is missing node "{p}" ({p} -> {q})')
                raise RuntimeWarning(f'Target graph is missing node "{p}" ({p} -> {q})')
            if not G.has_node(q):
                logger.error(f'Target graph is missing node "{q}" ({p} -> {q})')
                raise RuntimeWarning(f'Target graph is missing node "{q}" ({p} -> {q})')

            G.add_edge(p, q)

        # Ensure no cycles
        # find all independent graphs
        # iterate through each and mark visited
        try:
            c = nx.find_cycle(G, orientation="original")
            logger.error(f"Found cycle in graph during target discovery: {c}")
            raise RuntimeError(f"Found cycle in graph during target discovery: {c}")
        except nx.NetworkXNoCycle:
            # No cycle found
            pass

        # Create shutdown and startup call lists
        trees = dict()
        for component in nx.weakly_connected_components(G):
            G_sub = G.subgraph(component)
            root = [n for n, d in G_sub.in_degree() if d == 0]
            if len(root) > 1:
                logger.error(f"Multiple roots in target graph: {root}")
            trees[root[0]] = [
                (node, G.nodes[node]) for node in nx.topological_sort(G_sub)
            ]

        logger.debug(f"Target graph root nodes: {trees.keys()}")

        return trees

    def _register_plugin_method(
        self, plugin_name: str, method_name: str, func: callable
    ):
        if plugin_name not in self._registered_plugin_methods:
            self._registered_plugin_methods[plugin_name] = dict()

        if method_name in self._registered_plugin_methods[plugin_name]:
            raise ValueError(
                f"Function '{method_name}' already registered by plugin '{plugin_name}'."
            )

        self._registered_plugin_methods[plugin_name][method_name] = func
        logger.debug(
            f"Registered function '{method_name}' from plugin '{plugin_name}'."
        )

    def get_plugin_method(self, plugin: str, method: str):
        return self._registered_plugin_methods.get(plugin, {}).get(method)

    def call_plugin_method(self, plugin: str, method: str, *args, **kwargs):
        func = self.get_plugin_method(plugin, method)
        if func is None:
            raise RuntimeError(f"Method {plugin}/{method} not found")
        return func(*args, **kwargs)

    def get_registered_plugin_methods(self):
        return self._registered_plugin_methods

    def install_requirements(self):
        self._discover_plugins()
        self._install_requirements()

    def load_plugins(self):
        self._discover_plugins()
        self._resolve_dependencies()
        self._load_plugins()
        target_graphs = self._graph_targets()

        for root, targets in target_graphs.items():
            self.app.event_manager.subscribe(root, execute_target_callback(targets))


def execute_target(graph, target_root):
    logger.debug(f"Executing graph {target_root}")
    targets = graph.get(target_root, [])
    for target_name, target_attrs in targets:
        fun = target_attrs.get("function")
        if fun:
            logger.info(f"Running target {target_name}")
            fun()


def execute_target2(targets):
    for target_name, target_attrs in targets:
        fun = target_attrs.get("function")
        if fun:
            logger.info(f"Running target {target_name}")
            fun()


def execute_target_callback(targets):
    return lambda _: execute_target2(targets)
