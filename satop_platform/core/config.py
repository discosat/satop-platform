import yaml



class Config:
    config_defaults = {
        'api': {
            'root_path': '/api',
            'plugin_path': '/api/apps'
        }
    }

    def load_config(file:str):
        with open(file) as f:
            cfg = None

    
    def get_value(self, value_path:str):
        pass