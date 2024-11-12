import logging
import argparse

from components import restapi as api
from components import sample
from plugin_engine.plugin_engine import run_engine

# Parse command-line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', action='count', default=0, help="Increase verbosity level (use -v or -vv)")
args = parser.parse_args()

# Set the logging level based on the verbosity flag
if args.v == 1:
    logging.basicConfig(level=logging.INFO)  # -v (less verbose)
elif args.v >= 2:
    logging.basicConfig(level=logging.DEBUG)  # -vv (more verbose)
else:
    logging.basicConfig(level=logging.WARNING)  # default logging level

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

    run_engine()

    logger.info('Running server')
    api.load_routes()
    api.run_server()