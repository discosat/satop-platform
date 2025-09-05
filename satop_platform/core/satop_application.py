import asyncio
import importlib
import logging
import os
import subprocess

import typer

from satop_platform.components.authorization.auth import PlatformAuthorization
from satop_platform.components.authorization.cli import auth_cli
from satop_platform.components.groundstation.connector import GroundstationConnector
from satop_platform.components.restapi import routes
from satop_platform.components.restapi.restapi import APIApplication
from satop_platform.components.syslog.syslog import Syslog
from satop_platform.core import config
from satop_platform.core.events import SatOPEventManager
from satop_platform.plugin_engine.plugin_engine import SatopPluginEngine


class SatOPApplication:
    cli: typer.Typer
    logger: logging.Logger
    event_manager: SatOPEventManager
    api: APIApplication
    auth: PlatformAuthorization
    syslog: Syslog
    gs: GroundstationConnector
    plugin_engine: SatopPluginEngine

    # read-only properties
    @property
    def data_root(self):
        return self.__data_root

    @property
    def version(self):
        return self.__version

    def __init__(self, log_level=0, cli: typer.Typer | None = None):
        git_hash = self.get_git_head()
        version_suffix = "-" + git_hash if git_hash else ""

        application_title = "SatOP Platform"
        version = importlib.metadata.version("satop_platform") + version_suffix

        self.__version = version
        self.logger = logging.getLogger()

        self.logger.setLevel(logging.DEBUG)

        console_log_handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)7s] -- %(filename)20s:%(lineno)-4s -- %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
        console_log_handler.setFormatter(formatter)

        if cli:
            self.cli = cli

        self._ch = console_log_handler
        self.set_log_level(log_level)

        self.event_manager = SatOPEventManager()

        self.__data_root = config.get_root_data_folder()
        if not self.data_root.exists():
            logging.info(f"Creating data directory {self.data_root}")
            self.data_root.mkdir(parents=True)

        self.auth = PlatformAuthorization()
        self.api = APIApplication(self, title=application_title, version=version)
        self.syslog = Syslog(self)
        self.gs = GroundstationConnector(self)

        self.logger.info(
            f"Initialized platform application {application_title} v{version}"
        )
        routes.load_routes(self)

        self.plugin_engine = SatopPluginEngine(self)

    def load_cli(self):
        self.cli.add_typer(auth_cli(self.auth))
        self.cli.add_typer(self.plugin_engine.cli)

    def set_log_level(self, log_level: int):
        self.logger.removeHandler(self._ch)
        if 1 == log_level:
            self._ch.setLevel(logging.INFO)
        elif 1 < log_level:
            self._ch.setLevel(logging.DEBUG)
        else:
            self._ch.setLevel(logging.WARNING)
        self.logger.addHandler(self._ch)

    def run(self):
        self.event_manager.publish("satop.startup", None)

        try:
            asyncio.run(self.api.run_server())
        except KeyboardInterrupt:
            self.logger.warning("Keyboard interrupt")
        finally:
            self.logger.info("Shutting down")
            self.event_manager.publish("satop.shutdown", None)

    def get_git_head(self):
        this_dir = os.path.dirname(os.path.realpath(__file__))

        try:
            return (
                subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"], cwd=this_dir
                )
                .decode("utf-8")
                .strip()
            )
        except subprocess.CalledProcessError:
            logging.warning(
                f"Cannot get git HEAD id; Not in a git repository: {this_dir}"
            )
            return None
        except FileNotFoundError:
            logging.debug("Git is not installed. Can't get project HEAD")
            return None
