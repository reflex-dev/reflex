"""File for constants related to the installation process. (Bun/Node)."""

from __future__ import annotations

import logging
import os
from types import SimpleNamespace

from .base import IS_WINDOWS
from .utils import classproperty

logger = logging.getLogger(__name__)


# Bun config.
class Bun(SimpleNamespace):
    """Bun constants."""

    # The Bun version.
    VERSION = "1.3.14"

    # Min Bun Version
    MIN_VERSION = "1.3.0"

    # URL to bun install script.
    INSTALL_URL = "https://raw.githubusercontent.com/reflex-dev/reflex/main/scripts/bun_install.sh"

    # URL to windows install script.
    WINDOWS_INSTALL_URL = (
        "https://raw.githubusercontent.com/reflex-dev/reflex/main/scripts/install.ps1"
    )

    # Path of the bunfig file
    CONFIG_PATH = "bunfig.toml"

    # Path of the bun lockfile.
    LOCKFILE_PATH = "bun.lock"

    # Directory in the app root where the canonical bun lockfile is stored.
    # A dedicated directory avoids clashes with a user's own bun project
    # that may sit in the same directory as the Reflex project.
    ROOT_LOCKFILE_DIR = "reflex.lock"

    @classproperty
    @classmethod
    def ROOT_PATH(cls):
        """The directory to store the bun.

        Returns:
            The directory to store the bun.
        """
        from reflex_base.environment import environment

        return environment.REFLEX_DIR.get() / "bun"

    @classproperty
    @classmethod
    def DEFAULT_PATH(cls):
        """Default bun path.

        Returns:
            The default bun path.
        """
        return cls.ROOT_PATH / "bin" / ("bun" if not IS_WINDOWS else "bun.exe")

    DEFAULT_CONFIG = """
[install]
registry = "{registry}"
"""


# Node / NPM config
class Node(SimpleNamespace):
    """Node/ NPM constants."""

    # The minimum required node version.
    MIN_VERSION = "22.22.0"

    # Path of the node config file.
    CONFIG_PATH = ".npmrc"

    # Path of the npm lockfile.
    LOCKFILE_PATH = "package-lock.json"

    DEFAULT_CONFIG = """
registry={registry}
fetch-retries=0
"""


def _determine_react_router_version() -> str:
    # Requires Node >= 22.22.0 and React >= 19.2.7; keep Node.MIN_VERSION and
    # _determine_react_version in step when bumping.
    default_version = "8.3.0"
    if (version := os.getenv("REACT_ROUTER_VERSION")) and version != default_version:
        logger.warning(
            f"You have requested react-router@{version} but the supported version is {default_version}, abandon all hope ye who enter here."
        )
        return version
    return default_version


def _determine_react_version() -> str:
    default_version = "19.2.8"
    if (version := os.getenv("REACT_VERSION")) and version != default_version:
        logger.warning(
            f"You have requested react@{version} but the supported version is {default_version}, abandon all hope ye who enter here."
        )
        return version
    return default_version


class PackageJson(SimpleNamespace):
    """Constants used to build the package.json file."""

    class Commands(SimpleNamespace):
        """The commands to define in package.json."""

        DEV = "react-router dev --host"
        EXPORT = "react-router build"

    PATH = "package.json"

    _react_version = _determine_react_version()

    _react_router_version = _determine_react_router_version()

    @classproperty
    @classmethod
    def DEPENDENCIES(cls) -> dict[str, str]:
        """The dependencies to include in package.json.

        Returns:
            A dictionary of dependencies with their versions.
        """
        return {
            "react-router": cls._react_router_version,
            "@react-router/node": cls._react_router_version,
            "react": cls._react_version,
            "react-helmet": "6.1.0",
            "react-dom": cls._react_version,
            "isbot": "5.2.1",
            "socket.io-client": "4.8.3",
            "universal-cookie": "8.1.2",
        }

    DEV_DEPENDENCIES = {
        "@emotion/react": "11.14.0",
        "autoprefixer": "10.5.4",
        "postcss": "8.5.23",
        "postcss-import": "16.1.1",
        "@react-router/dev": _react_router_version,
        "@react-router/fs-routes": _react_router_version,
        "vite": "8.2.0",
    }
    # Force specific transitive npm deps to a single resolved version when
    # needed. Prefer a `DEV_DEPENDENCIES`/`DEPENDENCIES` pin when the package is
    # one we depend on directly: a top-level pin already satisfies and dedupes
    # every transitive requirer, and unlike an override it is not persisted into
    # a project's `reflex.lock/package.json` (where a later removal here cannot
    # clean it up again). Reserve overrides for packages we do not declare.
    OVERRIDES: dict[str, str] = {}
