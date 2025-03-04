import logging
import pathlib
import sys
import os
import yaml

from collections.abc import Mapping, Iterable
from itertools import chain

import satop_platform

logger = logging.getLogger(__name__)


def get_root_data_folder():
    home = pathlib.Path.home()

    if sys.platform == "win32":
        return home / "AppData/Roaming/SatOP"
    elif sys.platform == "linux":
        return home / ".local/share/SatOP"
    elif sys.platform == "darwin":
        return home / "Library/Application Support/SatOP"

class SatopConfig:
    __config_name: str
    __default_config: dict
    __user_config: dict

    @property
    def config_name(self):
        return self.__config_name

    def __init__(self, config_name: str = None):
        self.__config_name = config_name
        self.reload()

    def _get_config_file_name(self, parent_dir:pathlib.Path, config_name:str) -> pathlib.Path | None:
        paths = list(chain(
            parent_dir.glob(f'{config_name}.yaml'), 
            parent_dir.glob(f'{config_name}.yml')
        ))

        if len(paths) < 1:
            return None
        else:
            return paths[0]
    
    def _load_config(self, path: pathlib.Path):
        config = dict()

        if not path.exists():
            logger.error(f'Config file not found at {path}')
            raise FileNotFoundError
        else:
            with open(path) as f:
                logger.info(f'Loaded config from {path}')
                config = yaml.safe_load(f) or dict()
                logger.debug(f'Loaded config: {config}')
        return config
    
    def _traverse_config(self, config:dict, key_path:Iterable[str]):
        if config is None:
            return None

        p = list(key_path)
        next = p.pop(0)
        item = config.get(next)

        if len(p) == 0:
            return item

        if not isinstance(item, dict):
            self.logger.error(f'Error traversing config for value "{key_path}" at "{next}" ({type(item)})')
            raise LookupError

        return self._traverse_config(item, p)
        
    def reload(self):
        default_config_dir = pathlib.Path(satop_platform.__file__).parent.resolve() / 'default/config'
        user_config_dir = get_root_data_folder() / 'config'

        default_config_path = self._get_config_file_name(default_config_dir, self.__config_name)
        user_config_path = self._get_config_file_name(user_config_dir, self.__config_name)

        self.__default_config = None
        if default_config_path:
            self.__default_config = self._load_config(default_config_path)
        self.__user_config = None
        if user_config_path:
            self.__user_config = self._load_config(user_config_path)
        
        if self.__default_config is None and self.__user_config is None:
            logger.warning(f'Config loader for "{self.__config_name}" found no config files.')
    
    def get(self, key:str, default=None):
        key_path = key.split('.')

        # Create variable name to lookup in the environment
        env_name = 'SATOP_' + '__'.join(key_path).upper()

        # The list specifies the order it tries to read the config from; ENV first, then the user-space config followed by the default config file.
        for val in [
            os.environ.get(env_name),
            self._traverse_config(self.__user_config, key_path),
            self._traverse_config(self.__default_config, key_path)
        ] :
            if val is not None:
                return val

        # Return a default value if it does not exist in any of the 
        return default

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
