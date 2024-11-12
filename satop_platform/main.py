import logging
import argparse

from components import restapi as api
from components import sample
from plugin_engine.plugin_engine import run_engine


logger = logging.getLogger(__name__)


if __name__ == '__main__':

    parser = argparse.ArgumentParser('SatOP Platform')

    parser.add_argument('-v', '--verbose', action='count', default=0)

    args = parser.parse_args()

    if args.verbose == 1:
        logging.basicConfig(level=logging.INFO)
    elif args.verbose > 1: 
        logging.basicConfig(level=logging.DEBUG)


    logger.info('Starting platform')

    # sample.init()

    run_engine()

    # insert delay to allow for plugin loading
    # import time
    # time.sleep(1)


    logger.info('Running server')
    api.load_routes()
    # time.sleep(1)
    api.run_server()