"""Constants used throughout the package."""

import os
from enum import Enum

import pkg_resources

# App names and versions.
# The name of the Pynecone module.
MODULE_NAME = "pynecone"
# The name of the pip install package.
PACKAGE_NAME = "pynecone-io"
# The current version of Pynecone.
VERSION = pkg_resources.get_distribution(PACKAGE_NAME).version

# Files and directories used to init a new project.
# The root directory of the pynecone library.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The name of the file used for pc init.
APP_TEMPLATE_FILE = "tutorial.py"
# The name of the assets directory.
APP_ASSETS_DIR = "assets"
# The template directory used during pc init.
TEMPLATE_DIR = os.path.join(ROOT_DIR, MODULE_NAME, ".templates")
# The web subdirectory of the template directory.
WEB_TEMPLATE_DIR = os.path.join(TEMPLATE_DIR, "web")
# The app subdirectory of the template directory.
APP_TEMPLATE_DIR = os.path.join(TEMPLATE_DIR, "app")
# The assets subdirectory of the template directory.
ASSETS_TEMPLATE_DIR = os.path.join(TEMPLATE_DIR, APP_ASSETS_DIR)

# The frontend directories in a project.
# The web folder where the NextJS app is compiled to.
WEB_DIR = ".web"
# The name of the utils file.
UTILS_DIR = "utils"
# The name of the state file.
STATE_PATH = os.path.join(UTILS_DIR, "state")
# The directory where the app pages are compiled to.
WEB_PAGES_DIR = os.path.join(WEB_DIR, "pages")
# The directory where the utils file is located.
WEB_UTILS_DIR = os.path.join(WEB_DIR, UTILS_DIR)
# The directory where the assets are located.
WEB_ASSETS_DIR = os.path.join(WEB_DIR, "public")
# The node modules directory.
NODE_MODULES = "node_modules"
# The package lock file.
PACKAGE_LOCK = "package-lock.json"

# Commands to run the app.
# The backend api url.
API_URL = "http://localhost:8000"
# The default path where bun is installed.
BUN_PATH = "$HOME/.bun/bin/bun"
# Command to install bun.
INSTALL_BUN = "curl https://bun.sh/install | bash"
# Command to run the backend in dev mode.
RUN_BACKEND = "uvicorn --log-level critical --reload --host 0.0.0.0".split()
# The number of workers to run in production mode by default.
NUM_WORKERS = (os.cpu_count() or 1) * 2 + 1
# The default timeout when launching the gunicorn server.
TIMEOUT = 120
# The command to run the backend in production mode.
RUN_BACKEND_PROD = f"gunicorn --worker-class uvicorn.workers.UvicornH11Worker --bind 0.0.0.0:8000 --workers {NUM_WORKERS} --threads {NUM_WORKERS} --preload --timeout {TIMEOUT} --log-level debug".split()

# Compiler variables.
# The extension for compiled Javascript files.
JS_EXT = ".js"
# The extension for python files.
PY_EXT = ".py"
# The expected variable name where the pc.App is stored.
APP_VAR = "app"
# The expected variable name where the API object is stored for deployment.
API_VAR = "api"
# The name of the router variable.
ROUTER = "router"
# The name of the variable to hold API results.
RESULT = "result"
# The name of the process variable.
PROCESSING = "processing"
# The name of the state variable.
STATE = "state"
# The name of the events variable.
EVENTS = "events"
# The name of the initial hydrate event.
HYDRATE = "hydrate"
# The name of the index page.
INDEX_ROUTE = "index"
# The name of the document root page.
DOCUMENT_ROOT = "_document"
# The name of the theme page.
THEME = "theme"
# The prefix used to create setters for state vars.
SETTER_PREFIX = "set_"
# The name of the frontend zip during deployment.
FRONTEND_ZIP = "frontend.zip"
# The name of the backend zip during deployment.
BACKEND_ZIP = "backend.zip"
# The name of the sqlite database.
DB_NAME = "pynecone.db"
# The sqlite url.
DB_URL = f"sqlite:///{DB_NAME}"
# The default title to show for Pynecone apps.
DEFAULT_TITLE = "Pynecone App"
# The name of the pynecone config module.
CONFIG_MODULE = "pcconfig"
# The python config file.
CONFIG_FILE = f"{CONFIG_MODULE}{PY_EXT}"
# The deployment URL.
PRODUCTION_BACKEND_URL = "https://{username}-{app_name}.api.pynecone.app"
# Token expiration time in seconds.
TOKEN_EXPIRATION = 60 * 60


# Env modes
class Env(str, Enum):
    """The environment modes."""

    DEV = "dev"
    PROD = "prod"


class Endpoint(Enum):
    """Endpoints for the pynecone backend API."""

    PING = "ping"
    EVENT = "event"

    def __str__(self) -> str:
        """Get the string representation of the endpoint.

        Returns:
            The path for the endpoint.
        """
        return f"/{self.value}"

    def get_url(self) -> str:
        """Get the URL for the endpoint.

        Returns:
            The full URL for the endpoint.
        """
        from pynecone import utils

        config = utils.get_config()
        return "".join([config.api_url, str(self)])
