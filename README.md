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

### Development Environment Users

When running the `dev` service, the database is automatically reset and seeded with default users for a clean development experience. Each time you run `docker compose up dev`, the environment will be returned to this clean state.

You can log in with the following credentials:

- **Admin User**
  - **Email:** `admin@example.com`
  - **Password:** `adminpassword`
- **Operator User**
  - **Email:** `operator@example.com`
  - **Password:** `operatorpassword`

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

**Note:** When running the platform manually (outside of the provided Docker development environment), the database will not be automatically seeded. You will need to create the first user and roles manually using the API endpoints described in the 'Authentication and Authorization' section.

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

## Authentication and Authorization

The platform's security is built on three core principles: **Entities**, **Roles**, and **Scopes**.

- An **Entity** is any actor that interacts with the system (a person, a ground station, etc.).
- A **Role** is a job function with a defined set of permissions (e.g., `flight-operator`, `mission-director`).
- A **Scope** is a single, granular permission (e.g., `scheduling.flightplan.approve`).

The standard workflow is: Scopes are assigned to Roles, and Roles are assigned to Entities.

### API Workflow for User Creation

The following example demonstrates the multi-step API workflow for creating a new user from scratch. **Note:** For the Docker-based development environment (`docker compose up dev`), this entire process is automated, and default users are created for you (see the Docker section above).

**1. Create a `mission-director` Role:**
First, an administrator defines a role and assigns the necessary scopes to it.

`POST /api/auth/roles`

```json
{
  "name": "mission-director",
  "scopes": [
    "scheduling.flightplan.create",
    "scheduling.flightplan.read",
    "scheduling.flightplan.approve"
  ]
}
```

**2. Create a new `person` Entity:**
Next, create the user entity and assign the `mission-director` role to them.

`POST /api/auth/entities`

```json
{
  "name": "Jane Doe",
  "type": "person",
  "roles": "mission-director"
}
```

_Response Body:_

```json
{
  "type": "person",
  "roles": "mission-director",
  "name": "Jane Doe",
  "id": "b3552f9d-9800-4fe1-9770-aafde5083af6"
}
```

**3. Connect the Entity to an Authentication Provider:**
Link the entity's core ID to a real-world identifier, like an email address. Note the plural `providers` in the URL.

`POST /api/auth/entities/b3552f9d-9800-4fe1-9770-aafde5083af6/providers`

```json
{
  "provider": "email_password",
  "identity": "jane@example.com"
}
```

**4. Create the User's Credentials:**
This step is specific to the `email_password` plugin, creating the user's password.

`POST /api/plugins/login/user`

```json
{
  "email": "jane@example.com",
  "password": "correct-horse-battery-staple"
}
```

**5. Obtain Access and Refresh Tokens:**
The user can now log in to get their tokens. The response includes both an access and a refresh token. For a smooth frontend experience, it's recommended to also return the user's effective scopes.

`POST /api/plugins/login/token`

```json
{
  "email": "jane@example.com",
  "password": "correct-horse-battery-staple"
}
```

_Response Body:_

```json
{
  "access_token": "ey...",
  "refresh_token": "ey...",
  "scopes": [
    "scheduling.flightplan.create",
    "scheduling.flightplan.read",
    "scheduling.flightplan.approve"
  ]
}
```

### Test Mode

To enable a special test mode for development, you must set the `SATOP_ENABLE_TEST_AUTH` environment variable before starting the server. This is enabled by default in the dev Docker service.

<ins>!! **THIS IS INHERENTLY INSECURE AND SHOULD NEVER BE USED IN PRODUCTION !!**</ins>

**PowerShell:**

```powershell
$env:SATOP_ENABLE_TEST_AUTH=1; python -m satop_platform
```

**Linux / macOS:**

```sh
SATOP_ENABLE_TEST_AUTH=1 python -m satop_platform
```

This allows you to use a fake bearer token that specifies a username and their scopes directly. The format is `username;scope1,scope2`.

**Example:**
`Authorization: Bearer test-user;scheduling.flightplan.read,*`

## TODO

The following is a starting point for missing features. Add more here and update the list as required.

When starting work on one of the missing features, first create a new issue on GitHub from the list.

### Auth

- [x] Protect neccessary routes
- [x] Bootstrapping first-user creation when these routes are protected
- [x] Entity modification and management
- [x] Be able to refresh/renew tokens
- [x] Standardize scopes and their naming scheme,
- [ ] Add a way for components and plugins to specify which scopes they add to the system to enable easier user creation.
- [x] Scopes should be hierarchical, so e.g. a user with the "admin" scope would be authorized for routes requiring "admin.user_create".

### Logging

- [ ] Connect the syslog with a graph database to save event and traceability data
- [ ] Use the syslaog for all events that require traceability across the platform

### Plugins

- [ ] Refactor the plugin engine as a class
- [ ] Better structure when passing platform components to plugins
- [x] Support full life-cycle (also shutdown) for plugin targets

### New features

- [ ] Event-messaging system that allows emitting and listening for global events from any part of the platform.

```

```
