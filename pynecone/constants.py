"""Constants used throughout the package."""

import os
import re
from enum import Enum
from types import SimpleNamespace

import pkg_resources

# App names and versions.
# The name of the Pynecone module.
MODULE_NAME = "pynecone"
# The name of the pip install package.
PACKAGE_NAME = "pynecone"
# The current version of Pynecone.
VERSION = pkg_resources.get_distribution(PACKAGE_NAME).version
# Minimum version of Node.js required to run Pynecone.
MIN_NODE_VERSION = "12.22.0"

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
STATE_PATH = "/".join([UTILS_DIR, "state"])
# The name of the components file.
COMPONENTS_PATH = "/".join([UTILS_DIR, "components"])
# The directory where the app pages are compiled to.
WEB_PAGES_DIR = os.path.join(WEB_DIR, "pages")
# The directory where the static build is located.
WEB_STATIC_DIR = os.path.join(WEB_DIR, "_static")
# The directory where the utils file is located.
WEB_UTILS_DIR = os.path.join(WEB_DIR, UTILS_DIR)
# The directory where the assets are located.
WEB_ASSETS_DIR = os.path.join(WEB_DIR, "public")
# The node modules directory.
NODE_MODULES = "node_modules"
# The package lock file.
PACKAGE_LOCK = "package-lock.json"
# The pcversion template file.
PCVERSION_TEMPLATE_FILE = os.path.join(WEB_TEMPLATE_DIR, "pcversion.txt")
# The pcversion app file.
PCVERSION_APP_FILE = os.path.join(WEB_DIR, "pcversion.txt")


# Commands to run the app.
# The frontend default port.
FRONTEND_PORT = "3000"
# The backend api url.
API_URL = "http://localhost:8000"
# The default path where bun is installed.
BUN_PATH = "$HOME/.bun/bin/bun"
# Command to install bun.
INSTALL_BUN = "curl -fsSL https://bun.sh/install | bash -s -- bun-v0.5.5"
# Default host in dev mode.
BACKEND_HOST = "0.0.0.0"
# The default timeout when launching the gunicorn server.
TIMEOUT = 120
# The command to run the backend in production mode.
RUN_BACKEND_PROD = f"gunicorn --worker-class uvicorn.workers.UvicornH11Worker --preload --timeout {TIMEOUT} --log-level critical".split()

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
# The name of the socket variable.
SOCKET = "socket"
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
# The default description to show for Pynecone apps.
DEFAULT_DESCRIPTION = "A Pynecone app."
# The default image to show for Pynecone apps.
DEFAULT_IMAGE = "favicon.ico"


# The gitignore file.
GITIGNORE_FILE = ".gitignore"
# Files to gitignore.
DEFAULT_GITIGNORE = {WEB_DIR, DB_NAME}
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


# Log levels
class LogLevel(str, Enum):
    """The log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


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
        # Import here to avoid circular imports.
        from pynecone import utils

        # Get the API URL from the config.
        config = utils.get_config()
        url = "".join([config.api_url, str(self)])

        # The event endpoint is a websocket.
        if self == Endpoint.EVENT:
            # Replace the protocol with ws.
            url = url.replace("https://", "wss://").replace("http://", "ws://")

        # Return the url.
        return url


class SocketEvent(Enum):
    """Socket events sent by the pynecone backend API."""

    PING = "ping"
    EVENT = "event"

    def __str__(self) -> str:
        """Get the string representation of the event name.

        Returns:
            The event name string.
        """
        return str(self.value)


class Transports(Enum):
    """Socket transports used by the pynecone backend API."""

    POLLING_WEBSOCKET = "['polling', 'websocket']"
    WEBSOCKET_POLLING = "['websocket', 'polling']"
    WEBSOCKET_ONLY = "['websocket']"
    POLLING_ONLY = "['polling']"

    def __str__(self) -> str:
        """Get the string representation of the transports.

        Returns:
            The transports string.
        """
        return str(self.value)

    def get_transports(self) -> str:
        """Get the transports config for the backend.

        Returns:
            The transports config for the backend.
        """
        # Import here to avoid circular imports.
        from pynecone import utils

        # Get the transports from the config.
        config = utils.get_config()
        return str(config.backend_transports)


class RouteArgType(SimpleNamespace):
    """Type of dynamic route arg extracted from URI route."""

    # Typecast to str is needed for Enum to work.
    SINGLE = str("arg_single")
    LIST = str("arg_list")


class RouteVar(SimpleNamespace):
    """Names of variables used in the router_data dict stored in State."""

    CLIENT_IP = "ip"
    CLIENT_TOKEN = "token"
    HEADERS = "headers"
    PATH = "pathname"
    SESSION_ID = "sid"
    QUERY = "query"


class RouteRegex(SimpleNamespace):
    """Regex used for extracting route args in route."""

    ARG = re.compile(r"\[(?!\.)([^\[\]]+)\]")
    # group return the catchall pattern (i.e. "[[..slug]]")
    CATCHALL = re.compile(r"(\[?\[\.{3}(?![0-9]).*\]?\])")
    # group return the arg name (i.e. "slug")
    STRICT_CATCHALL = re.compile(r"\[\.{3}([a-zA-Z_][\w]*)\]")
    # group return the arg name (i.e. "slug")
    OPT_CATCHALL = re.compile(r"\[\[\.{3}([a-zA-Z_][\w]*)\]\]")


# 404 variables
ROOT_404 = ""
SLUG_404 = "[..._]"
TITLE_404 = "404 - Not Found"
FAVICON_404 = "favicon.ico"
DESCRIPTION_404 = "The page was not found"

# Color mode variables
USE_COLOR_MODE = "useColorMode"
COLOR_MODE = "colorMode"
TOGGLE_COLOR_MODE = "toggleColorMode"

# Server socket configuration variables
CORS_ALLOWED_ORIGINS = "*"
POLLING_MAX_HTTP_BUFFER_SIZE = 1000 * 1000
