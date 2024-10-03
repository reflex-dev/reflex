"""Base file for constants that don't fit any other categories."""

from __future__ import annotations

import os
import platform
from enum import Enum
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace

from platformdirs import PlatformDirs

IS_WINDOWS = platform.system() == "Windows"


class Dirs(SimpleNamespace):
    """Various directories/paths used by Reflex."""

    # The frontend directories in a project.
    # The web folder where the NextJS app is compiled to.
    WEB = ".web"
    # The name of the assets directory.
    APP_ASSETS = "assets"
    # The name of the assets directory for external ressource (a subfolder of APP_ASSETS).
    EXTERNAL_APP_ASSETS = "external"
    # The name of the utils file.
    UTILS = "utils"
    # The name of the state file.
    STATE_PATH = "/".join([UTILS, "state"])
    # The name of the components file.
    COMPONENTS_PATH = "/".join([UTILS, "components"])
    # The name of the contexts file.
    CONTEXTS_PATH = "/".join([UTILS, "context"])
    # The name of the output static directory.
    STATIC = "_static"
    # The name of the public html directory served at "/"
    PUBLIC = "public"
    # The directory where styles are located.
    STYLES = "styles"
    # The name of the pages directory.
    PAGES = "pages"
    # The name of the env json file.
    ENV_JSON = "env.json"
    # The name of the reflex json file.
    REFLEX_JSON = "reflex.json"
    # The name of the postcss config file.
    POSTCSS_JS = "postcss.config.js"
    # The name of the states directory.
    STATES = "states"


class Reflex(SimpleNamespace):
    """Base constants concerning Reflex."""

    # App names and versions.
    # The name of the Reflex package.
    MODULE_NAME = "reflex"
    # The current version of Reflex.
    VERSION = metadata.version(MODULE_NAME)

    # The reflex json file.
    JSON = "reflex.json"

    # Files and directories used to init a new project.
    # The directory to store reflex dependencies.
    # Get directory value from enviroment variables if it exists.
    _dir = os.environ.get("REFLEX_DIR", "")

    DIR = Path(
        _dir
        or (
            # on windows, we use C:/Users/<username>/AppData/Local/reflex.
            # on macOS, we use ~/Library/Application Support/reflex.
            # on linux, we use ~/.local/share/reflex.
            # If user sets REFLEX_DIR envroment variable use that instead.
            PlatformDirs(MODULE_NAME, False).user_data_dir
        )
    )
    # The root directory of the reflex library.

    ROOT_DIR = Path(__file__).parents[2]

    RELEASES_URL = f"https://api.github.com/repos/reflex-dev/templates/releases"


class ReflexHostingCLI(SimpleNamespace):
    """Base constants concerning Reflex Hosting CLI."""

    # The name of the Reflex Hosting CLI package.
    MODULE_NAME = "reflex-hosting-cli"


class Templates(SimpleNamespace):
    """Constants related to Templates."""

    # The route on Reflex backend to query which templates are available and their URLs.
    APP_TEMPLATES_ROUTE = "/app-templates"

    # The default template
    DEFAULT = "blank"

    # The reflex.build frontend host
    REFLEX_BUILD_FRONTEND = os.environ.get(
        "REFLEX_BUILD_FRONTEND", "https://flexgen.reflex.run"
    )

    # The reflex.build backend host
    REFLEX_BUILD_BACKEND = os.environ.get(
        "REFLEX_BUILD_BACKEND", "https://flexgen-prod-flexgen.fly.dev"
    )

    # The URL to redirect to reflex.build
    REFLEX_BUILD_URL = (
        REFLEX_BUILD_FRONTEND + "/gen?reflex_init_token={reflex_init_token}"
    )

    # The URL to poll waiting for the user to select a generation.
    REFLEX_BUILD_POLL_URL = REFLEX_BUILD_BACKEND + "/api/init/{reflex_init_token}"

    # The URL to fetch the generation's reflex code
    REFLEX_BUILD_CODE_URL = (
        REFLEX_BUILD_BACKEND + "/api/gen/{generation_hash}/refactored"
    )

    class Dirs(SimpleNamespace):
        """Folders used by the template system of Reflex."""

        # The template directory used during reflex init.
        BASE = Reflex.ROOT_DIR / Reflex.MODULE_NAME / ".templates"
        # The web subdirectory of the template directory.
        WEB_TEMPLATE = BASE / "web"
        # The jinja template directory.
        JINJA_TEMPLATE = BASE / "jinja"
        # Where the code for the templates is stored.
        CODE = "code"


class Next(SimpleNamespace):
    """Constants related to NextJS."""

    # The NextJS config file
    CONFIG_FILE = "next.config.js"
    # The sitemap config file.
    SITEMAP_CONFIG_FILE = "next-sitemap.config.js"
    # The node modules directory.
    NODE_MODULES = "node_modules"
    # The package lock file.
    PACKAGE_LOCK = "package-lock.json"
    # Regex to check for message displayed when frontend comes up
    FRONTEND_LISTENING_REGEX = "Local:[\\s]+(.*)"


# Color mode variables
class ColorMode(SimpleNamespace):
    """Constants related to ColorMode."""

    NAME = "rawColorMode"
    RESOLVED_NAME = "resolvedColorMode"
    USE = "useColorMode"
    TOGGLE = "toggleColorMode"
    SET = "setColorMode"


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

# If this env var is set to "yes", App.compile will be a no-op
SKIP_COMPILE_ENV_VAR = "__REFLEX_SKIP_COMPILE"

# This env var stores the execution mode of the app
ENV_MODE_ENV_VAR = "REFLEX_ENV_MODE"

# Testing variables.
# Testing os env set by pytest when running a test case.
PYTEST_CURRENT_TEST = "PYTEST_CURRENT_TEST"
RELOAD_CONFIG = "__REFLEX_RELOAD_CONFIG"

REFLEX_VAR_OPENING_TAG = "<reflex.Var>"
REFLEX_VAR_CLOSING_TAG = "</reflex.Var>"
