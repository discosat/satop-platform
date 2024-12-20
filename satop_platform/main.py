import argparse
import os
from satop_platform.core.satop_application import SatOPApplication

def load_args():
    parser = argparse.ArgumentParser('SatOP Platform')
    parser.add_argument('-v', '--verbose', action='count', default=0)
    parser.add_argument('-t', '--test-auth', action='store_true', default=False)
    return parser.parse_args()

def main():
    args = load_args()
    if args.test_auth:
        os.environ['SATOP_ENABLE_TEST_AUTH'] = 'True'

    application = SatOPApplication(log_level=args.verbose)
    application.run()

if __name__ == '__main__':
    main()