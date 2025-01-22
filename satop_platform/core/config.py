import logging
import pathlib
import sys
import yaml

from collections.abc import Mapping

logger = logging.getLogger(__name__)

def load_config(file:str = None):
    config_path = get_root_data_folder()/'config'/file
    # logger.info(f'Loa config from {config_path}')
    config = dict()

    if not config_path.exists():
        logger.warning(f'Config file not found at {config_path} -- Using default values')
        # return dict()
    else:
        with open(config_path) as f:
            logger.info(f'Loaded config from {config_path}')
            config = yaml.safe_load(f) or dict()
            logger.debug(f'Loaded config: {config}')
    return config

# Function to recursively merge dictionaries
def merge_dicts(dict1, dict2):
    logger.debug(f"Merging dicts: dict 1: {dict1}, dict2: {dict2}")

    merged = dict(dict1)  # Start with a copy of dict1
    for key, value in dict2.items():
        if key in merged:
            # If the value is a dict, merge recursively
            if isinstance(merged[key], Mapping) and isinstance(value, Mapping):
                merged[key] = merge_dicts(merged[key], value)
            # If the value is a list, concatenate lists
            elif isinstance(merged[key], list) and isinstance(value, list):
                merged[key] = merged[key] + value
            elif value is None:
                pass
            # Otherwise, overwrite the value
            else:
                merged[key] = value
        else:
            merged[key] = value
    return merged

def get_root_data_folder():
    home = pathlib.Path.home()

    if sys.platform == "win32":
        return home / "AppData/Roaming/SatOP"
    elif sys.platform == "linux":
        return home / ".local/share/SatOP"
    elif sys.platform == "darwin":
        return home / "Library/Application Support/SatOP"
