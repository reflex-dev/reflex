"""Constants used throughout the package."""

import os
import re
from enum import Enum
from types import SimpleNamespace
from typing import Any, Type

# importlib is only available for Python 3.8+ so we need the backport for Python 3.7
try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata  # pyright: ignore[reportMissingImports]


def get_value(key: str, default: Any = None, type_: Type = str) -> Type:
    """Get the value for the constant.
    Obtain os env value and cast non-string types into
    their original types.

    Args:
        key: constant name.
        default: default value if key doesn't exist.
        type_: the type of the constant.

    Returns:
        the value of the constant in its designated type
    """
    value = os.getenv(key, default)
    try:
        if value and type_ != str:
            value = eval(value)
    except Exception:
        pass
    finally:
        # Special case for db_url expects None to be a valid input when
        # user explicitly overrides db_url as None
        return value if value != "None" else None  # noqa B012


# App names and versions.
# The name of the Reflex package.
MODULE_NAME = "reflex"
# The current version of Reflex.
VERSION = metadata.version(MODULE_NAME)
# Minimum version of Node.js required to run Reflex.
MIN_NODE_VERSION = "16.8.0"

# Valid bun versions.
MIN_BUN_VERSION = "0.5.9"
MAX_BUN_VERSION = "0.6.9"

# Files and directories used to init a new project.
# The root directory of the reflex library.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The name of the assets directory.
APP_ASSETS_DIR = "assets"
# The template directory used during reflex init.
TEMPLATE_DIR = os.path.join(ROOT_DIR, MODULE_NAME, ".templates")
# The web subdirectory of the template directory.
WEB_TEMPLATE_DIR = os.path.join(TEMPLATE_DIR, "web")
# The assets subdirectory of the template directory.
ASSETS_TEMPLATE_DIR = os.path.join(TEMPLATE_DIR, APP_ASSETS_DIR)
# The jinja template directory.
JINJA_TEMPLATE_DIR = os.path.join(TEMPLATE_DIR, "jinja")

# The frontend directories in a project.
# The web folder where the NextJS app is compiled to.
WEB_DIR = ".web"
# The name of the utils file.
UTILS_DIR = "utils"
# The name of the output static directory.
STATIC_DIR = "_static"
# The name of the state file.
STATE_PATH = "/".join([UTILS_DIR, "state"])
# The name of the components file.
COMPONENTS_PATH = "/".join([UTILS_DIR, "components"])
# The directory where the app pages are compiled to.
WEB_PAGES_DIR = os.path.join(WEB_DIR, "pages")
# The directory where the static build is located.
WEB_STATIC_DIR = os.path.join(WEB_DIR, STATIC_DIR)
# The directory where the utils file is located.
WEB_UTILS_DIR = os.path.join(WEB_DIR, UTILS_DIR)
# The directory where the assets are located.
WEB_ASSETS_DIR = os.path.join(WEB_DIR, "public")
# The Tailwind config.
TAILWIND_CONFIG = os.path.join(WEB_DIR, "tailwind.config.js")
# Default Tailwind content paths
TAILWIND_CONTENT = ["./pages/**/*.{js,ts,jsx,tsx}"]
# The NextJS config file
NEXT_CONFIG_FILE = "next.config.js"
# The sitemap config file.
SITEMAP_CONFIG_FILE = os.path.join(WEB_DIR, "next-sitemap.config.js")
# The node modules directory.
NODE_MODULES = "node_modules"
# The package lock file.
PACKAGE_LOCK = "package-lock.json"
# The reflex json file.
REFLEX_JSON = os.path.join(WEB_DIR, "reflex.json")
# The env json file.
ENV_JSON = os.path.join(WEB_DIR, "env.json")

# Commands to run the app.
DOT_ENV_FILE = ".env"
# The frontend default port.
FRONTEND_PORT = get_value("FRONTEND_PORT", "3000")
# The backend default port.
BACKEND_PORT = get_value("BACKEND_PORT", "8000")
# The backend api url.
API_URL = get_value("API_URL", "http://localhost:8000")
# The deploy url
DEPLOY_URL = get_value("DEPLOY_URL")
# bun root location
BUN_ROOT_PATH = "$HOME/.bun"
# The default path where bun is installed.
BUN_PATH = get_value("BUN_PATH", f"{BUN_ROOT_PATH}/bin/bun")
# Command to install bun.
INSTALL_BUN = f"curl -fsSL https://bun.sh/install | bash -s -- bun-v{MAX_BUN_VERSION}"
# Default host in dev mode.
BACKEND_HOST = get_value("BACKEND_HOST", "0.0.0.0")
# The default timeout when launching the gunicorn server.
TIMEOUT = get_value("TIMEOUT", 120, type_=int)
# The command to run the backend in production mode.
RUN_BACKEND_PROD = f"gunicorn --worker-class uvicorn.workers.UvicornH11Worker --preload --timeout {TIMEOUT} --log-level critical".split()
RUN_BACKEND_PROD_WINDOWS = f"uvicorn --timeout-keep-alive {TIMEOUT}".split()
# Socket.IO web server
PING_INTERVAL = 25
PING_TIMEOUT = 120
# flag to make the engine print all the SQL statements it executes
SQLALCHEMY_ECHO = get_value("SQLALCHEMY_ECHO", False, type_=bool)

# Compiler variables.
# The extension for compiled Javascript files.
JS_EXT = ".js"
# The extension for python files.
PY_EXT = ".py"
# The expected variable name where the rx.App is stored.
APP_VAR = "app"
# The expected variable name where the API object is stored for deployment.
API_VAR = "api"
# The name of the router variable.
ROUTER = "router"
# The name of the socket variable.
SOCKET = "socket"
# The name of the variable to hold API results.
RESULT = "result"
# The name of the final variable.
FINAL = "final"
# The name of the process variable.
PROCESSING = "processing"
# The name of the state variable.
STATE = "state"
# The name of the events variable.
EVENTS = "events"
# The name of the initial hydrate event.
HYDRATE = "hydrate"
# The name of the is_hydrated variable.
IS_HYDRATED = "is_hydrated"
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
DB_NAME = os.getenv("DB_NAME", "reflex.db")
# The sqlite url.
DB_URL = get_value("DB_URL", f"sqlite:///{DB_NAME}")
# The redis url
REDIS_URL = get_value("REDIS_URL")
# The default title to show for Reflex apps.
DEFAULT_TITLE = "Reflex App"
# The default description to show for Reflex apps.
DEFAULT_DESCRIPTION = "A Reflex app."
# The default image to show for Reflex apps.
DEFAULT_IMAGE = "favicon.ico"
# The default meta list to show for Reflex apps.
DEFAULT_META_LIST = []

# The gitignore file.
GITIGNORE_FILE = ".gitignore"
# Files to gitignore.
DEFAULT_GITIGNORE = {WEB_DIR, DB_NAME, "__pycache__/", "*.py[cod]"}
# The name of the reflex config module.
CONFIG_MODULE = "rxconfig"
# The python config file.
CONFIG_FILE = f"{CONFIG_MODULE}{PY_EXT}"
# The previous config file.
OLD_CONFIG_FILE = f"pcconfig{PY_EXT}"
# The deployment URL.
PRODUCTION_BACKEND_URL = "https://{username}-{app_name}.api.pynecone.app"
# Token expiration time in seconds.
TOKEN_EXPIRATION = 60 * 60
# The event namespace for websocket
EVENT_NAMESPACE = get_value("EVENT_NAMESPACE")

# Testing variables.
# Testing os env set by pytest when running a test case.
PYTEST_CURRENT_TEST = "PYTEST_CURRENT_TEST"

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


# Templates
class Template(str, Enum):
    """The templates to use for the app."""

    DEFAULT = "default"
    COUNTER = "counter"


class Endpoint(Enum):
    """Endpoints for the reflex backend API."""

    PING = "ping"
    EVENT = "event"
    UPLOAD = "upload"

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
        from reflex.config import get_config

        # Get the API URL from the config.
        config = get_config()
        url = "".join([config.api_url, str(self)])

        # The event endpoint is a websocket.
        if self == Endpoint.EVENT:
            # Replace the protocol with ws.
            url = url.replace("https://", "wss://").replace("http://", "ws://")

        # Return the url.
        return url


class SocketEvent(Enum):
    """Socket events sent by the reflex backend API."""

    PING = "ping"
    EVENT = "event"

    def __str__(self) -> str:
        """Get the string representation of the event name.

        Returns:
            The event name string.
        """
        return str(self.value)


class Transports(Enum):
    """Socket transports used by the reflex backend API."""

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
        from reflex.config import get_config

        # Get the API URL from the config.
        config = get_config()
        return str(config.backend_transports)


class RouteArgType(SimpleNamespace):
    """Type of dynamic route arg extracted from URI route."""

    # Typecast to str is needed for Enum to work.
    SINGLE = str("arg_single")
    LIST = str("arg_list")


# the name of the backend var containing path and client information
ROUTER_DATA = "router_data"


class RouteVar(SimpleNamespace):
    """Names of variables used in the router_data dict stored in State."""

    CLIENT_IP = "ip"
    CLIENT_TOKEN = "token"
    HEADERS = "headers"
    PATH = "pathname"
    SESSION_ID = "sid"
    QUERY = "query"
    COOKIE = "cookie"


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
SLUG_404 = "404"
TITLE_404 = "404 - Not Found"
FAVICON_404 = "favicon.ico"
DESCRIPTION_404 = "The page was not found"

# Color mode variables
USE_COLOR_MODE = "useColorMode"
COLOR_MODE = "colorMode"
TOGGLE_COLOR_MODE = "toggleColorMode"

# Server socket configuration variables
CORS_ALLOWED_ORIGINS = get_value("CORS_ALLOWED_ORIGINS", ["*"], list)
POLLING_MAX_HTTP_BUFFER_SIZE = 1000 * 1000

# Alembic migrations
ALEMBIC_CONFIG = os.environ.get("ALEMBIC_CONFIG", "alembic.ini")
