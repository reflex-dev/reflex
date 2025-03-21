"""File for constants related to the installation process. (Bun/Node)."""

from __future__ import annotations

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


class PackageJson(SimpleNamespace):
    """Constants used to build the package.json file."""

    class Commands(SimpleNamespace):
        """The commands to define in package.json."""

        DEV = "react-router dev"
        EXPORT = "react-router build"
        EXPORT_SITEMAP = EXPORT
        PROD = "react-router-serve ./build/server/index.js"

    PATH = "package.json"

    DEPENDENCIES = {
        "@emotion/react": "11.14.0",
        "axios": "1.8.3",
        "json5": "2.2.3",
        "react-router": "7.3.0",
        "react-router-dom": "7.3.0",
        "react-helmet": "6.1.0",
        "@react-router/node": "7.3.0",
        "@react-router/serve": "7.3.0",
        "react": "19.0.0",
        "react-dom": "19.0.0",
        "isbot": "5.1.17",
        "socket.io-client": "4.8.1",
        "universal-cookie": "7.2.2",
    }
    DEV_DEPENDENCIES = {
        "autoprefixer": "10.4.21",
        "postcss": "8.5.3",
        "postcss-import": "16.1.0",
        "@react-router/dev": "7.3.0",
        "@react-router/fs-routes": "7.3.0",
        "vite": "^6.2.2",
    }
    OVERRIDES = {
        # This should always match the `react` version in DEPENDENCIES for recharts compatibility.
        "react-is": "19.0.0"
    }
