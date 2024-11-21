# satop-platform

## Configure
For development, start by cloning the repository
```sh
git clone git@github.com:discosat/satop-platform.git
```
or
```sh
git clone https://github.com/discosat/satop-platform.git
```


Windows (powershell or command prompt)
```ps1
# Create a virtual environment
python -m venv .venv
# Activate the virtual environment
.venv\Scripts\activate
```

Linux / macOS
```sh
# Create a virtual environment
python -m venv .venv
# Activate the virtual environment
source .venv/bin/activate
```

## Install

### For development
```sh
# Install SatOP as a development package
pip install -editable .
```

### For production
Run either

```sh
pip install git+ssh://git@github.com:discosat/satop-platform.git
```
or
```sh
pip install git+https://github.com/discosat/satop-platform.git
```

## Run
```sh
python satop_platform/main.py [-vv]
```



## Plugin development

### Minimum files

A plugin must be placed in the `satop_plugins` directory 

```
/satop_plugins
 - /[plugin_name]
   - __init__.py
   - config.yaml
   - [my_plugin_module].py
```

The `__init__.py` should export a class named `PluginClass`, that is a subclass of `Plugin` from `satop_platform.plugin_engine.plugin`.

e.g.
```python
from .my_plugin_module import my_plugin_class as PluginClass
```

The configuration 

```yaml
name: My Plugin Name
requirements: []        # pip requirements
dependencies: []        # dependencies of other plugins. Given by their configured name
capabilities:           # Additional capabilities
  - http.add_routes

# Targets are optional. Below are shown the defaults: 
targets:
  startup:
    function: startup
    after: satop.startup
  shutdown:
    function: shutdown
    after: satop.shutdown
```

### Capabilities

| Capability                       | Description                                                                                 | Risk |
| -------------------------------- | ------------------------------------------------------------------------------------------- | ---- |
| http.add_routes                  | The FastAPI APIRouter defined in the plugin will be mounted on the main FastAPI application | low  |
| security.authentication_provider | Allows the plugin access to authentication methods, such as creating JWT tokens             | high |

TODO: does the capabilities make sense to have, when the plugins run in the same 
process as the rest of the platform? It could potentially be easy to bypass 
security/directly access secrets from environment variables/disk/RAM!?