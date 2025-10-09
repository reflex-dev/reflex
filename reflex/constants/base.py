"""Base file for constants that don't fit any other categories."""

from __future__ import annotations

import platform
from enum import Enum
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from platformdirs import PlatformDirs

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


class Dirs(SimpleNamespace):
    """Various directories/paths used by Reflex."""

    # The frontend directories in a project.
    # The web folder where the frontend app is compiled to.
    WEB = ".web"
    # The directory where uploaded files are stored.
    UPLOADED_FILES = "uploaded_files"
    # The name of the assets directory.
    APP_ASSETS = "assets"
    # The name of the assets directory for external resources (a subfolder of APP_ASSETS).
    EXTERNAL_APP_ASSETS = "external"
    # The name of the utils file.
    UTILS = "utils"
    # The name of the state file.
    STATE_PATH = UTILS + "/state"
    # The name of the components file.
    COMPONENTS_PATH = UTILS + "/components"
    # The name of the contexts file.
    CONTEXTS_PATH = UTILS + "/context"
    # The name of the output directory.
    BUILD_DIR = "build"
    # The name of the static files directory.
    STATIC = BUILD_DIR + "/client"
    # The name of the public html directory served at "/"
    PUBLIC = "public"
    # The directory where styles are located.
    STYLES = "styles"
    # The name of the pages directory.
    PAGES = "app"
    # The name of the routes directory.
    ROUTES = "routes"
    # The name of the env json file.
    ENV_JSON = "env.json"
    # The name of the reflex json file.
    REFLEX_JSON = "reflex.json"
    # The name of the postcss config file.
    POSTCSS_JS = "postcss.config.js"
    # The name of the states directory.
    STATES = ".states"
    # Where compilation artifacts for the backend are stored.
    BACKEND = "backend"
    # JSON-encoded list of page routes that need to be evaluated on the backend.
    STATEFUL_PAGES = "stateful_pages.json"
    # Marker file indicating that upload component was used in the frontend.
    UPLOAD_IS_USED = "upload_is_used"


def _reflex_version() -> str:
    """Get the Reflex version.

    Returns:
        The Reflex version.
    """
    try:
        return metadata.version("reflex")
    except metadata.PackageNotFoundError:
        return "unknown"


class Reflex(SimpleNamespace):
    """Base constants concerning Reflex."""

    # App names and versions.
    # The name of the Reflex package.
    MODULE_NAME = "reflex"
    # The current version of Reflex.
    VERSION = _reflex_version()

    # The reflex json file.
    JSON = "reflex.json"

    # Files and directories used to init a new project.
    # The directory to store reflex dependencies.
    # on windows, we use C:/Users/<username>/AppData/Local/reflex.
    # on macOS, we use ~/Library/Application Support/reflex.
    # on linux, we use ~/.local/share/reflex.
    # If user sets REFLEX_DIR envroment variable use that instead.
    DIR = PlatformDirs(MODULE_NAME, False).user_data_path

    LOGS_DIR = DIR / "logs"

    # The root directory of the reflex library.
    ROOT_DIR = Path(__file__).parents[2]

    RELEASES_URL = "https://api.github.com/repos/reflex-dev/templates/releases"

    # The reflex stylesheet language supported
    STYLESHEETS_SUPPORTED = ["css", "sass", "scss"]


class ReflexHostingCLI(SimpleNamespace):
    """Base constants concerning Reflex Hosting CLI."""

    # The name of the Reflex Hosting CLI package.
    MODULE_NAME = "reflex-hosting-cli"


class Templates(SimpleNamespace):
    """Constants related to Templates."""

    # The default template
    DEFAULT = "blank"

    # The AI template
    AI = "ai"

    # The option for the user to choose a remote template.
    CHOOSE_TEMPLATES = "choose-templates"

    # The URL to find reflex templates.
    REFLEX_TEMPLATES_URL = (
        "https://reflex.dev/docs/getting-started/open-source-templates/"
    )

    # The reflex.build frontend host
    REFLEX_BUILD_FRONTEND = "https://build.reflex.dev"

    # The reflex.build frontend with referrer
    REFLEX_BUILD_FRONTEND_WITH_REFERRER = (
        f"{REFLEX_BUILD_FRONTEND}/?utm_source=reflex_cli"
    )

    class Dirs(SimpleNamespace):
        """Folders used by the template system of Reflex."""

        # The template directory used during reflex init.
        BASE = Reflex.ROOT_DIR / Reflex.MODULE_NAME / ".templates"
        # The web subdirectory of the template directory.
        WEB_TEMPLATE = BASE / "web"
        # Where the code for the templates is stored.
        CODE = "code"


class Javascript(SimpleNamespace):
    """Constants related to Javascript."""

    # The node modules directory.
    NODE_MODULES = "node_modules"


class ReactRouter(Javascript):
    """Constants related to React Router."""

    # The react router config file
    CONFIG_FILE = "react-router.config.js"

    # The associated Vite config file
    VITE_CONFIG_FILE = "vite.config.js"

    # Regex to check for message displayed when frontend comes up
    DEV_FRONTEND_LISTENING_REGEX = r"Local:[\s]+"

    # Regex to pattern the route path in the config file
    # INFO  Accepting connections at http://localhost:3000
    PROD_FRONTEND_LISTENING_REGEX = r"Accepting connections at[\s]+"

    FRONTEND_LISTENING_REGEX = (
        rf"(?:{DEV_FRONTEND_LISTENING_REGEX}|{PROD_FRONTEND_LISTENING_REGEX})(.*)"
    )

    SPA_FALLBACK = "__spa-fallback.html"


# Color mode variables
class ColorMode(SimpleNamespace):
    """Constants related to ColorMode."""

    NAME = "rawColorMode"
    RESOLVED_NAME = "resolvedColorMode"
    USE = "useColorMode"
    TOGGLE = "toggleColorMode"
    SET = "setColorMode"


LITERAL_ENV = Literal["dev", "prod"]


# Env modes
class Env(str, Enum):
    """The environment modes."""

    DEV = "dev"
    PROD = "prod"


# Log levels
class LogLevel(str, Enum):
    """The log levels."""

    DEBUG = "debug"
    DEFAULT = "default"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @classmethod
    def from_string(cls, level: str | None) -> LogLevel | None:
        """Convert a string to a log level.

        Args:
            level: The log level as a string.

        Returns:
            The log level.
        """
        if not level:
            return None
        try:
            return LogLevel[level.upper()]
        except KeyError:
            return None

    def __le__(self, other: LogLevel) -> bool:
        """Compare log levels.

        Args:
            other: The other log level.

        Returns:
            True if the log level is less than or equal to the other log level.
        """
        levels = list(LogLevel)
        return levels.index(self) <= levels.index(other)

    def subprocess_level(self):
        """Return the log level for the subprocess.

        Returns:
            The log level for the subprocess
        """
        return self if self != LogLevel.DEFAULT else LogLevel.WARNING


# Server socket configuration variables
POLLING_MAX_HTTP_BUFFER_SIZE = 1000 * 1000


class Ping(SimpleNamespace):
    """PING constants."""

    # The 'ping' interval
    INTERVAL = 25
    # The 'ping' timeout
    TIMEOUT = 120


# Keys in the client_side_storage dict
COOKIES = "cookies"
LOCAL_STORAGE = "local_storage"
SESSION_STORAGE = "session_storage"

# Testing variables.
# Testing os env set by pytest when running a test case.
PYTEST_CURRENT_TEST = "PYTEST_CURRENT_TEST"
APP_HARNESS_FLAG = "APP_HARNESS_FLAG"

REFLEX_VAR_OPENING_TAG = "<reflex.Var>"
REFLEX_VAR_CLOSING_TAG = "</reflex.Var>"
