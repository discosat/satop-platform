import importlib
import logging
import os
import subprocess

from satop_platform.components.restapi import routes
from satop_platform.plugin_engine.plugin_engine import run_engine
from satop_platform.core import config

from .component_initializer import SatOPComponents

class SatOPApplication:
    logger: logging.Logger
    components: SatOPComponents

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

        data_dir = config.get_root_data_folder()
        if not data_dir.exists():
            logging.info(f'Creating data directory {data_dir}')
            data_dir.mkdir(parents=True)
        
        git_hash = self.get_git_head()
        version_suffix = '-' + git_hash if git_hash else ''

        application_title = 'SatOP Platform'
        version = importlib.metadata.version('satop_platform') + version_suffix

        self.components = SatOPComponents(
            api = {
                'title': application_title,
                'version': version
                }
        )
        self.logger.info(f'Initialized platform application {application_title} v{version}')
        routes.load_routes(self.components)
    
    def run(self):
        run_engine(self.components)

        self.components.api.run_server()

        self.logger.info('Shutting down')

    def get_git_head(self):
        this_dir = os.path.dirname(os.path.realpath(__file__)) 

        try:
            return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=this_dir).decode('utf-8').strip()
        except subprocess.CalledProcessError:
            logging.warning(f'Cannot get git HEAD id; Not in a git repository: {this_dir}')
            return None