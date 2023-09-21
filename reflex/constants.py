"""Constants used throughout the package."""
from __future__ import annotations

import os
import platform
import re
from enum import Enum
from types import SimpleNamespace

from platformdirs import PlatformDirs

# importlib is only available for Python 3.8+ so we need the backport for Python 3.7
try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata  # pyright: ignore[reportMissingImports]

IS_WINDOWS = platform.system() == "Windows"


def get_fnm_name() -> str | None:
    """Get the appropriate fnm executable name based on the current platform.

    Returns:
            The fnm executable name for the current platform.
    """
    platform_os = platform.system()

    if platform_os == "Windows":
        return "fnm-windows"
    elif platform_os == "Darwin":
        return "fnm-macos"
    elif platform_os == "Linux":
        machine = platform.machine()
        if machine == "arm" or machine.startswith("armv7"):
            return "fnm-arm32"
        elif machine.startswith("aarch") or machine.startswith("armv8"):
            return "fnm-arm64"
        return "fnm-linux"
    return None


# App names and versions.
# The name of the Reflex package.
MODULE_NAME = "reflex"
# The current version of Reflex.
VERSION = metadata.version(MODULE_NAME)

# Files and directories used to init a new project.
# The directory to store reflex dependencies.
REFLEX_DIR = (
    # on windows, we use C:/Users/<username>/AppData/Local/reflex.
    # on macOS, we use ~/Library/Application Support/reflex.
    # on linux, we use ~/.local/share/reflex.
    PlatformDirs(MODULE_NAME, False).user_data_dir
)
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

# Bun config.
# The Bun version.
BUN_VERSION = "0.7.3"
# Min Bun Version
MIN_BUN_VERSION = "0.7.0"
# The directory to store the bun.
BUN_ROOT_PATH = os.path.join(REFLEX_DIR, "bun")
# Default bun path.
DEFAULT_BUN_PATH = os.path.join(BUN_ROOT_PATH, "bin", "bun")
# URL to bun install script.
BUN_INSTALL_URL = "https://bun.sh/install"

# FNM / Node config.
# The FNM version.
FNM_VERSION = "1.35.1"
# The Node version.
NODE_VERSION = "18.17.0"
# The minimum required node version.
NODE_VERSION_MIN = "16.8.0"
# The directory to store fnm.
FNM_DIR = os.path.join(REFLEX_DIR, "fnm")
FNM_FILENAME = get_fnm_name()
# The fnm executable binary.
FNM_EXE = os.path.join(FNM_DIR, "fnm.exe" if IS_WINDOWS else "fnm")
# The node bin path.
NODE_BIN_PATH = os.path.join(
    FNM_DIR,
    "node-versions",
    f"v{NODE_VERSION}",
    "installation",
    "bin" if not IS_WINDOWS else "",
)
# The default path where node is installed.
NODE_PATH = os.path.join(NODE_BIN_PATH, "node.exe" if IS_WINDOWS else "node")
# The default path where npm is installed.
NPM_PATH = os.path.join(NODE_BIN_PATH, "npm")
# The URL to the fnm release binary
FNM_INSTALL_URL = (
    f"https://github.com/Schniz/fnm/releases/download/v{FNM_VERSION}/{FNM_FILENAME}.zip"
)
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
# The directory where styles are located.
STYLES_DIR = os.path.join(WEB_DIR, "styles")
# The Tailwind config.
TAILWIND_CONFIG = os.path.join(WEB_DIR, "tailwind.config.js")
# Default Tailwind content paths
TAILWIND_CONTENT = ["./pages/**/*.{js,ts,jsx,tsx}"]
# Relative tailwind style path to root stylesheet in STYLES_DIR.
TAILWIND_ROOT_STYLE_PATH = "./tailwind.css"
# The Tailwindcss version
TAILWIND_VERSION = "tailwindcss@^3.3.2"
# The package json file
PACKAGE_JSON_PATH = os.path.join(WEB_DIR, "package.json")
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

# Compiler variables.
# The extension for compiled Javascript files.
JS_EXT = ".js"
# The extension for python files.
PY_EXT = ".py"
# The extension for css files.
CSS_EXT = ".css"
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
# The name of the app root page.
APP_ROOT = "_app"
# The root stylesheet filename.
STYLESHEET_ROOT = "styles"
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
DEFAULT_GITIGNORE = {WEB_DIR, "*.db", "__pycache__/", "*.py[cod]"}
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
# Maximum time in milliseconds that a state can be locked for exclusive access.
LOCK_EXPIRATION = 10000

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

    def __le__(self, other: LogLevel) -> bool:
        """Compare log levels.

        Args:
            other: The other log level.

        Returns:
            True if the log level is less than or equal to the other log level.
        """
        levels = list(LogLevel)
        return levels.index(self) <= levels.index(other)


# Templates
class Template(str, Enum):
    """The templates to use for the app."""

    DEFAULT = "default"
    COUNTER = "counter"


class Endpoint(Enum):
    """Endpoints for the reflex backend API."""

    PING = "ping"
    EVENT = "_event"
    UPLOAD = "_upload"

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
    ORIGIN = "asPath"
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


class PackageJsonCommands(SimpleNamespace):
    """Commands used in package.json file."""

    DEV = "next dev"
    EXPORT = "next build && next export -o _static"
    EXPORT_SITEMAP = "next build && next-sitemap && next export -o _static"
    PROD = "next start"


PACKAGE_DEPENDENCIES = {
    "@chakra-ui/react": "^2.6.0",
    "@chakra-ui/system": "^2.5.6",
    "@emotion/react": "^11.10.6",
    "@emotion/styled": "^11.10.6",
    "axios": "^1.4.0",
    "chakra-react-select": "^4.6.0",
    "focus-visible": "^5.2.0",
    "json5": "^2.2.3",
    "next": "^13.3.1",
    "next-sitemap": "^4.1.8",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "socket.io-client": "^4.6.1",
    "universal-cookie": "^4.0.4",
}
PACKAGE_DEV_DEPENDENCIES = {
    "autoprefixer": "^10.4.14",
    "postcss": "^8.4.24",
}

# 404 variables
SLUG_404 = "404"
TITLE_404 = "404 - Not Found"
FAVICON_404 = "favicon.ico"
DESCRIPTION_404 = "The page was not found"
ROUTE_NOT_FOUND = "routeNotFound"

# Color mode variables
USE_COLOR_MODE = "useColorMode"
COLOR_MODE = "colorMode"
TOGGLE_COLOR_MODE = "toggleColorMode"

# Server socket configuration variables
POLLING_MAX_HTTP_BUFFER_SIZE = 1000 * 1000
PING_INTERVAL = 25
PING_TIMEOUT = 120

# Alembic migrations
ALEMBIC_CONFIG = os.environ.get("ALEMBIC_CONFIG", "alembic.ini")

# Keys in the client_side_storage dict
COOKIES = "cookies"
LOCAL_STORAGE = "local_storage"


class EventTriggers(SimpleNamespace):
    """All trigger names used in Reflex."""

    ON_FOCUS = "on_focus"
    ON_BLUR = "on_blur"
    ON_CANCEL = "on_cancel"
    ON_CLICK = "on_click"
    ON_CHANGE = "on_change"
    ON_CHANGE_END = "on_change_end"
    ON_CHANGE_START = "on_change_start"
    ON_COMPLETE = "on_complete"
    ON_CONTEXT_MENU = "on_context_menu"
    ON_DOUBLE_CLICK = "on_double_click"
    ON_DROP = "on_drop"
    ON_EDIT = "on_edit"
    ON_KEY_DOWN = "on_key_down"
    ON_KEY_UP = "on_key_up"
    ON_MOUSE_DOWN = "on_mouse_down"
    ON_MOUSE_ENTER = "on_mouse_enter"
    ON_MOUSE_LEAVE = "on_mouse_leave"
    ON_MOUSE_MOVE = "on_mouse_move"
    ON_MOUSE_OUT = "on_mouse_out"
    ON_MOUSE_OVER = "on_mouse_over"
    ON_MOUSE_UP = "on_mouse_up"
    ON_SCROLL = "on_scroll"
    ON_SUBMIT = "on_submit"
    ON_MOUNT = "on_mount"
    ON_UNMOUNT = "on_unmount"


# If this env var is set to "yes", App.compile will be a no-op
SKIP_COMPILE_ENV_VAR = "__REFLEX_SKIP_COMPILE"
