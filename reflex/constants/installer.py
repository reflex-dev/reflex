"""File for constants related to the installation process. (Bun/Node)."""

from __future__ import annotations

import os
from types import SimpleNamespace

from .base import IS_WINDOWS
from .utils import classproperty


# Bun config.
class Bun(SimpleNamespace):
    """Bun constants."""

    # The Bun version.
    VERSION = "1.2.18"

    # Min Bun Version
    MIN_VERSION = "1.2.17"

    # URL to bun install script.
    INSTALL_URL = "https://raw.githubusercontent.com/reflex-dev/reflex/main/scripts/bun_install.sh"

    # URL to windows install script.
    WINDOWS_INSTALL_URL = (
        "https://raw.githubusercontent.com/reflex-dev/reflex/main/scripts/install.ps1"
    )

    # Path of the bunfig file
    CONFIG_PATH = "bunfig.toml"

    @classproperty
    @classmethod
    def ROOT_PATH(cls):
        """The directory to store the bun.

        Returns:
            The directory to store the bun.
        """
        from reflex.environment import environment

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
    MIN_VERSION = "20.19.0"

    # Path of the node config file.
    CONFIG_PATH = ".npmrc"

    DEFAULT_CONFIG = """
registry={registry}
fetch-retries=0
"""


def _determine_react_router_version() -> str:
    default_version = "7.6.3"
    if (version := os.getenv("REACT_ROUTER_VERSION")) and version != default_version:
        from reflex.utils import console

        console.warn(
            f"You have requested react-router@{version} but the supported version is {default_version}, abandon all hope ye who enter here."
        )
        return version
    return default_version


def _determine_react_version() -> str:
    default_version = "19.1.0"
    if (version := os.getenv("REACT_VERSION")) and version != default_version:
        from reflex.utils import console

        console.warn(
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
        PROD = "serve ./build/client"

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
            "json5": "2.2.3",
            "react-router": cls._react_router_version,
            "react-router-dom": cls._react_router_version,
            "@react-router/node": cls._react_router_version,
            "serve": "14.2.4",
            "react": cls._react_version,
            "react-helmet": "6.1.0",
            "react-dom": cls._react_version,
            "isbot": "5.1.28",
            "socket.io-client": "4.8.1",
            "universal-cookie": "7.2.2",
        }

    DEV_DEPENDENCIES = {
        "@emotion/react": "11.14.0",
        "autoprefixer": "10.4.21",
        "postcss": "8.5.6",
        "postcss-import": "16.1.1",
        "@react-router/dev": _react_router_version,
        "@react-router/fs-routes": _react_router_version,
        "rolldown-vite": "7.0.9",
    }
    OVERRIDES = {
        # This should always match the `react` version in DEPENDENCIES for recharts compatibility.
        "react-is": _react_version,
        "cookie": "1.0.2",
        "rollup": "4.44.2",
    }
