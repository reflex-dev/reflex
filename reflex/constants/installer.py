"""File for constants related to the installation process. (Bun/FNM/Node)."""

from __future__ import annotations

import platform
from pathlib import Path
from types import SimpleNamespace

from .base import IS_WINDOWS
from .utils import classproperty


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


# Bun config.
class Bun(SimpleNamespace):
    """Bun constants."""

    # The Bun version.
    VERSION = "1.1.29"

    # Min Bun Version
    MIN_VERSION = "0.7.0"

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


# FNM config.
class Fnm(SimpleNamespace):
    """FNM constants."""

    # The FNM version.
    VERSION = "1.35.1"

    FILENAME = get_fnm_name()

    # The URL to the fnm release binary
    INSTALL_URL = (
        f"https://github.com/Schniz/fnm/releases/download/v{VERSION}/{FILENAME}.zip"
    )

    @classproperty
    @classmethod
    def DIR(cls) -> Path:
        """The directory to store fnm.

        Returns:
            The directory to store fnm.
        """
        from reflex.config import environment

        return environment.REFLEX_DIR.get() / "fnm"

    @classproperty
    @classmethod
    def EXE(cls):
        """The fnm executable binary.

        Returns:
            The fnm executable binary.
        """
        return cls.DIR / ("fnm.exe" if IS_WINDOWS else "fnm")


# Node / NPM config
class Node(SimpleNamespace):
    """Node/ NPM constants."""

    # The Node version.
    VERSION = "22.11.0"
    # The minimum required node version.
    MIN_VERSION = "18.18.0"

    @classproperty
    @classmethod
    def BIN_PATH(cls):
        """The node bin path.

        Returns:
            The node bin path.
        """
        return (
            Fnm.DIR
            / "node-versions"
            / f"v{cls.VERSION}"
            / "installation"
            / ("bin" if not IS_WINDOWS else "")
        )

    @classproperty
    @classmethod
    def PATH(cls):
        """The default path where node is installed.

        Returns:
            The default path where node is installed.
        """
        return cls.BIN_PATH / ("node.exe" if IS_WINDOWS else "node")

    @classproperty
    @classmethod
    def NPM_PATH(cls):
        """The default path where npm is installed.

        Returns:
            The default path where npm is installed.
        """
        return cls.BIN_PATH / "npm"


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
        "@babel/standalone": "7.26.0",
        "@emotion/react": "11.13.3",
        "axios": "1.7.7",
        "json5": "2.2.3",
        "next": "14.2.16",
        "next-sitemap": "4.2.3",
        "next-themes": "0.3.0",
        "react": "18.3.1",
        "react-dom": "18.3.1",
        "react-focus-lock": "2.13.2",
        "socket.io-client": "4.8.1",
        "universal-cookie": "7.2.1",
    }
    DEV_DEPENDENCIES = {
        "autoprefixer": "10.4.20",
        "postcss": "8.4.47",
        "postcss-import": "16.1.0",
    }
