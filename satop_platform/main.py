import logging
import argparse

from components import restapi as api
from components import sample

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

    sample.init()

    logger.info('Running server')
    api.load_routes()
    api.run_server()