import logging
import argparse
import subprocess
import os

import importlib.metadata

from components.restapi import APIApplication
from components.restapi.routes import load_routes
from components import sample
from components.syslog import syslog
from plugin_engine.plugin_engine import run_engine
from satop_platform.components.groundstation.connector import GroundstationConnector

logger = logging.getLogger()

def load_args():
    parser = argparse.ArgumentParser('SatOP Platform')
    parser.add_argument('-v', '--verbose', action='count', default=0)
    return parser.parse_args()

if __name__ == '__main__':

    this_dir = os.path.dirname(os.path.realpath(__file__)) 

    git_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=this_dir).decode('utf-8').strip()

    logger.setLevel(logging.DEBUG)
    console_log_handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)7s] -- %(filename)20s:%(lineno)-4s -- %(message)s", "%Y-%m-%d %H:%M:%S")
    console_log_handler.setFormatter(formatter)
    args = load_args()
    if args.verbose == 1:
        console_log_handler.setLevel(logging.INFO)
    elif args.verbose > 1:
        console_log_handler.setLevel(logging.DEBUG)
    else:
        console_log_handler.setLevel(logging.WARNING)
    logger.addHandler(console_log_handler)

    application_title = 'SatOP Platform'
    version = importlib.metadata.version('satop_platform') + '-' + git_hash

    api_app = APIApplication(
        title=application_title,
        version=version
    )
    gsc = GroundstationConnector(api_app)

    logger.info(f'Starting {application_title} v{version}')

    # sample.init()

    syslog.init(api_app)
    run_engine(api_app)

    logger.info('Running server')

    load_routes(api_app)
    api_app.run_server()

    logger.info('Shutting down')
