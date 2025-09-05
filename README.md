# SatOP - a general interoperability platform for satellite command and control and other operations systems for small satellite missions

The SatOP platform is a framework written in Python with core components for logging, a ground station interface, an easily extendable API
with [FastAPI](https://fastapi.tiangolo.com/), an authorisation framework, and a modular plugin interface.

The plugin interface enables easy integration with existing systems and creation of new tools to support the operation in a satellite mission. The ground station interface makes it possible to connect the platform with one or more ground stations, without restricting which commands and functionality the ground station can support.

It has initially been developed as a research and development project at Aarhus University in fall of 2024 by [Aleksander Nicklas Nikolajsen](https://github.com/Nikolasjen) and [Tobias Frejo Rasmussen](https://github.com/tobiasfrejo) in collaboration with DISCO, with the intention of being used for the operations of DISCO-2.

## Docker

To start a development environment with live-reloading and all plugins enabled:

```sh
docker compose up dev
```

TODO: Create devcontainer for platform/plugin development.

## Requirements

The platform requires Python 3.10 or later to run. Install from [python.org](https://www.python.org/downloads/) or if using Linux, your distribution's package repository.

On Ubuntu, you should install the `python3-full` to ensure you have PIP and virtual environment support. (Optional) You can also install `python-is-python3` to be able to use `python` from the terminal instead of `python3`:

```
sudo apt install python3-full python-is-python3
```

## Run

We suggest creating and activate a Python virtual environment. Navigate to a suitable location in your terminal and run:

Windows

```ps1
python -m venv .venv
.venv\Scripts\activate
```

Linux / macOS

```sh
python -m venv .venv
source .venv/bin/activate
```

Now, install the satop-platform package directly from the git repository:

```sh
pip install git+https://github.com/discosat/satop-platform.git
```

## Run

With the platform package installed, it can be run with:

```sh
python -m satop_platform [-vv]
```

Access the automatically generated API documentation from a browser:

- [Swagger UI (http://localhost:7889/docs)](http://localhost:7889/docs)
- [ReDoc (http://localhost:7889/docs)](http://localhost:7889/redoc)

## Platform data

The platform will save data to the following locations depending on your OS:

```
Windows: %userprofile%\AppData\Roaming\SatOP
Linux:   ~/.local/share/SatOP
macOS:   ~/Library/Application Support/SatOP
```

(**Note on Windows:** If you have the Windows Store version of Python installed, it might instead be placed in a virtualised folder under `%userprofile%\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\Roaming\SatOP`. If you manually delete this folder and create the one in `AppData\Roaming`, this can be circumvented.)

### Config

SatOP can be configured to listen to a different IP and port by editing (or creating) `config/api.yml` in the SatOP directory. E.g. the following will listen on all interfaces on port 1234:

```yaml
host: 0.0.0.0
port: 1234
```

In the future, more configuration options will become available.

### Plugins

Plugins can be installed on the platform by placing their directory in the

### Testing

The project includes a dedicated service for running the test suite.

To run all pytest tests:

```sh
docker-compose run --rm test
```

## Development

For development, start by cloning the repository

```sh
git clone git@github.com:discosat/satop-platform.git
```

or

```sh
git clone https://github.com/discosat/satop-platform.git
```

Enter the `satop-platform` directory:

```
cd satop-platform
```

Create and activate a Python virtual environment

Windows

```ps1
python -m venv .venv
.venv\Scripts\activate
```

Linux / macOS

```sh
python -m venv .venv
source .venv/bin/activate
```

Install the satop platform as a development package in the virtual environment, which makes changes take affect as modifications are made.

```sh
pip install --editable .
```

It can then be started with

```sh
python -m satop_platform [-vv] [--install-plugin-requirements]
```

Note that the `--install-plugin-requirements` flag will install any requirements specified in the plugins' `config.yaml` files. This flag is only necessary if its the first time the satop platform will be running or if there's an update to a plugins requirements.

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
requirements: [] # pip requirements
dependencies: [] # dependencies of other plugins. Given by their configured name
capabilities: # Additional capabilities
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

Capabilitites add a way to set extra steps that need to happen as plugins are initialised.

It is not a security feature, as plugins are not isolated/sandboxed processes, so even without the capability implementation, they could in theory do the same process. It is only there as a simple check to ease development.

The following capabilities are supported,

| Capability                       | Description                                                                                              |
| -------------------------------- | -------------------------------------------------------------------------------------------------------- |
| http.add_routes                  | The FastAPI APIRouter defined in the plugin will be mounted on the main FastAPI application              |
| security.authentication_provider | Allows the plugin access to authentication methods, such as creating JWT tokens, by dependency injection |

## Authentication and authorization

As API routes can be secured, only allowing access to authenticated and authorized users, some setup is required to define who is allowed to do what.

The two core principles of the authorization system is "entities" and "scopes". As the platform is made for interoperability, both people and other systems should be able to access the platform resources, so both of these are defined under the umbrella-term "entity".

Scopes are various permissions an entity has, and API routes can be setup to require a specific set of scopes.

Example of creating a new user with the included email-password authentication plugin:

1. Create a new _person_ entity in the authorisation database:

```
POST /api/auth/entities

Request body:
{
  "name": "John Smith",
  "type": "person",
  "scopes": "user,admin"
}

Response body:
{
  "type": "person",
  "scopes": "user,admin",
  "name": "John Smith",
  "id": "b3552f9d-9800-4fe1-9770-aafde5083af6"
}
```

2. Define the identity identifier that gets authenticated by the specified provider. In this case, the `email_password`-based provider should authenticate users based on what their email-address is:

```
POST /api/auth/entities/b3552f9d-9800-4fe1-9770-aafde5083af6/provider

Request body:
{
  "provider": "email_password",
  "identity": "john@example.com"
}

Response body:
{
  "entity_id": "b3552f9d-9800-4fe1-9770-aafde5083af6",
  "provider": "email_password",
  "identity": "john@example.com"
}
```

3. Create the user with a password for the identity-provider plugin's database. Alternative authentication plugins might not need this step, e.g. if it connects to a SSO-service where the user has already been created.

```
POST /api/plugins/login/user

Request body:
{
  "email": "john@example.com",
  "password": "correct-horse-battery-staple"
}

Response:
201 Created
```

4. An access token can then be obtained from the identity-provider plugin:

```
POST /api/plugins/login/token

Request body:
{
  "email": "john@example.com",
  "password": "correct-horse-battery-staple"
}

Response body:
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiMzU1MmY5ZC05ODAwLTRmZTEtOTc3MC1hYWZkZTUwODNhZjYiLCJ0eXAiOiJhY2Nlc3MiLCJleHAiOjE3Mzc1NTk1MDd9.it5LtH-CyhgQ7F3XgPbtkK-5nUzVNZR0rpuHAPI4-7M"
}
```

5. This token can then be used to access restricted API routes, by adding it as a `Bearer`-token in the request header.

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiMzU1MmY5ZC05ODAwLTRmZTEtOTc3MC1hYWZkZTUwODNhZjYiLCJ0eXAiOiJhY2Nlc3MiLCJleHAiOjE3Mzc1NTk1MDd9.it5LtH-CyhgQ7F3XgPbtkK-5nUzVNZR0rpuHAPI4-7M
```

### Test flag

The platform can be started with the following testing flag:

```sh
python -m satop_platform --test-auth
```

<ins>!! **THIS IS INHERENTLY INSECURE AND SHOULD NEVER BE USED IN PRODUCTION !!**</ins>

It allows using a fake token for authorization that specifies a test user and their allowed scopes.
The test token is a username and comma-seperated list of scopes, separated by a semi-colon.

Example in the auth-header:

```
Authorization: Bearer steve;user,admin,test
```

## TODO

The following is a starting point for missing features. Add more here and update the list as required.

When starting work on one of the missing features, first create a new issue on GitHub from the list.

### Auth

- [ ] Protect neccessary routes
- [ ] Bootstrapping first-user creation when these routes are protected
- [ ] Entity modification and management
- [x] Be able to refresh/renew tokens
- [ ] Standardize scopes and their naming scheme,
- [ ] Add a way for components and plugins to specify which scopes they add to the system to enable easier user creation.
- [ ] Scopes should be hierarchical, so e.g. a user with the "admin" scope would be authorized for routes requiring "admin.user_create".

### Logging

- [ ] Connect the syslog with a graph database to save event and traceability data
- [ ] Use the syslaog for all events that require traceability across the platform

### Plugins

- [ ] Refactor the plugin engine as a class
- [ ] Better structure when passing platform components to plugins
- [x] Support full life-cycle (also shutdown) for plugin targets

### New features

- [ ] Event-messaging system that allows emitting and listening for global events from any part of the platform.
