"""Base file for constants that don't fit any other categories."""

from __future__ import annotations

import os
import platform
from enum import Enum
from importlib import metadata
from types import SimpleNamespace

from platformdirs import PlatformDirs

IS_WINDOWS = platform.system() == "Windows"


class Dirs(SimpleNamespace):
    """Various directories/paths used by Nextpy."""

    # The frontend directories in a project.
    # The web folder where the NextJS app is compiled to.
    WEB = ".web"
    # The name of the assets directory.
    APP_ASSETS = "assets"
    # The name of the utils file.
    UTILS = "utils"
    # The name of the output static directory.
    STATIC = "_static"
    # The name of the state file.
    STATE_PATH = "/".join([UTILS, "state"])
    # The name of the components file.
    COMPONENTS_PATH = "/".join([UTILS, "components"])
    # The directory where the app pages are compiled to.
    WEB_PAGES = os.path.join(WEB, "pages")
    # The directory where the static build is located.
    WEB_STATIC = os.path.join(WEB, STATIC)
    # The directory where the utils file is located.
    WEB_UTILS = os.path.join(WEB, UTILS)
    # The directory where the assets are located.
    WEB_ASSETS = os.path.join(WEB, "public")
    # The env json file.
    ENV_JSON = os.path.join(WEB, "env.json")
    # The nextpy json file.
    NEXTPY_JSON = os.path.join(WEB, "nextpy.json")


class Nextpy(SimpleNamespace):
    """Base constants concerning Nextpy."""

    # App names and versions.
    # The name of the Nextpy package.
    MODULE_NAME = "nextpy"
    # The current version of Nextpy.
    VERSION = metadata.version(MODULE_NAME)

    # The nextpy json file.
    JSON = os.path.join(Dirs.WEB, "nextpy.json")

    # Files and directories used to init a new project.
    # The directory to store nextpy dependencies.
    DIR = (
        # on windows, we use C:/Users/<username>/AppData/Local/nextpy.
        # on macOS, we use ~/Library/Application Support/nextpy.
        # on linux, we use ~/.local/share/nextpy.
        PlatformDirs(MODULE_NAME, False).user_data_dir
    )
    # The root directory of the nextpy library.

    ROOT_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )


class Templates(SimpleNamespace):
    """Constants related to Templates."""

    # Dynamically get the enum values from the .templates folder
    template_dir = os.path.join(Nextpy.ROOT_DIR, Nextpy.MODULE_NAME, ".templates/apps")
    template_dirs = next(os.walk(template_dir))[1]

    # Create an enum value for each directory in the .templates folder
    Kind = Enum("Kind", {template.upper(): template for template in template_dirs})

    class Dirs(SimpleNamespace):
        """Folders used by the template system of Nextpy."""

        # The template directory used during nextpy init.
        BASE = os.path.join(Nextpy.ROOT_DIR, Nextpy.MODULE_NAME, ".templates")
        # The web subdirectory of the template directory.
        WEB_TEMPLATE = os.path.join(BASE, "web")
        # The jinja template directory.
        JINJA_TEMPLATE = os.path.join(BASE, "jinja")
        # Where the code for the templates is stored.
        CODE = "code"


class Next(SimpleNamespace):
    """Constants related to NextJS."""

    # The NextJS config file
    CONFIG_FILE = "next.config.js"
    # The sitemap config file.
    SITEMAP_CONFIG_FILE = os.path.join(Dirs.WEB, "next-sitemap.config.js")
    # The node modules directory.
    NODE_MODULES = "node_modules"
    # The package lock file.
    PACKAGE_LOCK = "package-lock.json"
    # Regex to check for message displayed when frontend comes up
    FRONTEND_LISTENING_REGEX = "Local:[\\s]+(.*)"


# Color mode variables
class ColorMode(SimpleNamespace):
    """Constants related to ColorMode."""

    NAME = "colorMode"
    USE = "useColorMode"
    TOGGLE = "toggleColorMode"


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

# If this env var is set to "yes", App.compile will be a no-op
SKIP_COMPILE_ENV_VAR = "__NEXTPY_SKIP_COMPILE"

# Testing variables.
# Testing os env set by pytest when running a test case.
PYTEST_CURRENT_TEST = "PYTEST_CURRENT_TEST"
