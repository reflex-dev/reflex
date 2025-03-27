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
    VERSION = "1.2.4"

    # Min Bun Version
    MIN_VERSION = "1.2.4"

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
        from reflex.config import environment

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

    # The Node version.
    VERSION = "22.11.0"
    # The minimum required node version.
    MIN_VERSION = "18.18.0"

    # Path of the node config file.
    CONFIG_PATH = ".npmrc"

    DEFAULT_CONFIG = """
registry={registry}
fetch-retries=0
"""


def _determine_nextjs_version() -> str:
    default_version = "15.2.4"
    if (version := os.getenv("NEXTJS_VERSION")) and version != default_version:
        from reflex.utils import console

        console.warn(
            f"You have requested next@{version} but the supported version is {default_version}, abandon all hope ye who enter here."
        )
        return version
    return default_version


class PackageJson(SimpleNamespace):
    """Constants used to build the package.json file."""

    class Commands(SimpleNamespace):
        """The commands to define in package.json."""

        DEV = "next dev"
        EXPORT = "next build"
        EXPORT_SITEMAP = "next build && next-sitemap"
        PROD = "next start"

    PATH = "package.json"

    DEPENDENCIES = {
        "@emotion/react": "11.14.0",
        "axios": "1.8.3",
        "json5": "2.2.3",
        "next": _determine_nextjs_version(),
        "next-sitemap": "4.2.3",
        "next-themes": "0.4.6",
        "react": "19.0.0",
        "react-dom": "19.0.0",
        "react-focus-lock": "2.13.6",
        "socket.io-client": "4.8.1",
        "universal-cookie": "7.2.2",
    }
    DEV_DEPENDENCIES = {
        "autoprefixer": "10.4.21",
        "postcss": "8.5.3",
        "postcss-import": "16.1.0",
    }
    OVERRIDES = {
        # This should always match the `react` version in DEPENDENCIES for recharts compatibility.
        "react-is": "19.0.0"
    }
