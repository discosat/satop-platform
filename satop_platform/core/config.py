import yaml
import os

def load_config(file:str = None):
    file_path = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(file_path, '..', 'config', file)

    if not os.path.exists(config_path):
        return dict()

    with open(config_path) as f:
        return yaml.safe_load(f) or dict()
