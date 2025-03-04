import asyncio
import importlib
import logging
import os
import pathlib
import subprocess

from satop_platform.components.restapi import routes
from satop_platform.plugin_engine.plugin_engine import run_engine, stop_engine
from satop_platform.core import config
from satop_platform.core.events import SatOPEventManager
from satop_platform.components.authorization.auth import PlatformAuthorization
from satop_platform.components.groundstation.connector import GroundstationConnector
from satop_platform.components.restapi.restapi import APIApplication
from satop_platform.components.syslog.syslog import Syslog

from .component_initializer import SatOPComponents

class SatOPApplication:
    logger: logging.Logger
    event_manager: SatOPEventManager
    api: APIApplication
    auth: PlatformAuthorization
    syslog: Syslog
    gs: GroundstationConnector

    # read-only properties
    @property
    def data_root(self):
        return self.__data_root

    @property
    def version(self):
        return self.__version
    

    def __init__(self, log_level = 0):
        self.logger = logging.getLogger()

        self.logger.setLevel(logging.DEBUG)

        console_log_handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)7s] -- %(filename)20s:%(lineno)-4s -- %(message)s", "%Y-%m-%d %H:%M:%S")
        console_log_handler.setFormatter(formatter)

        if 1 == log_level:
            console_log_handler.setLevel(logging.INFO)
        elif 1 < log_level:
            console_log_handler.setLevel(logging.DEBUG)
        else:
            console_log_handler.setLevel(logging.WARNING)
        self.logger.addHandler(console_log_handler)

        self.event_manager = SatOPEventManager()

        self.__data_root = config.get_root_data_folder()
        if not self.data_root.exists():
            logging.info(f'Creating data directory {self.data_root}')
            self.data_root.mkdir(parents=True)
        
        git_hash = self.get_git_head()
        version_suffix = '-' + git_hash if git_hash else ''

        application_title = 'SatOP Platform'
        version = importlib.metadata.version('satop_platform') + version_suffix
        self.__version = version


        self.auth = PlatformAuthorization()
        self.api = APIApplication(self, title = application_title, version = version)
        self.syslog = Syslog(self)
        self.gs = GroundstationConnector(self)

        self.logger.info(f'Initialized platform application {application_title} v{version}')
        routes.load_routes(self)
    
    def run(self):
        run_engine(self.components, self.event_manager)

        try:
            asyncio.run(self.components.api.run_server())
        except KeyboardInterrupt:
            self.logger.warning('Keyboard interrupt')
        finally:
            self.logger.info('Shutting down')
            stop_engine(self.event_manager)

    def get_git_head(self):
        this_dir = os.path.dirname(os.path.realpath(__file__)) 

        try:
            return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=this_dir).decode('utf-8').strip()
        except subprocess.CalledProcessError:
            logging.warning(f'Cannot get git HEAD id; Not in a git repository: {this_dir}')
            return None