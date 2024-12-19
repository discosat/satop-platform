import argparse
from satop_platform.core.satop_application import SatOPApplication

def load_args():
    parser = argparse.ArgumentParser('SatOP Platform')
    parser.add_argument('-v', '--verbose', action='count', default=0)
    return parser.parse_args()

def main():
    args = load_args()

    application = SatOPApplication(log_level=args.verbose)
    application.run()

if __name__ == '__main__':
    main()