import yaml
import os
import logging

from collections.abc import Mapping

logger = logging.getLogger(__name__)

def load_config(file:str = None):
    file_path = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(file_path, '..', 'config', file)

    if not os.path.exists(config_path):
        return dict()

    with open(config_path) as f:
        return yaml.safe_load(f) or dict()

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