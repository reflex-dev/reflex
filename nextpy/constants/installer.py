"""File for constants related to the installation process. (Bun/FNM/Node)."""
from __future__ import annotations

import os
import platform
from types import SimpleNamespace

from .base import IS_WINDOWS, Dirs, Nextpy


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
    VERSION = "1.0.4"
    # Min Bun Version
    MIN_VERSION = "0.7.0"
    # The directory to store the bun.
    ROOT_PATH = os.path.join(Nextpy.DIR, "bun")
    # Default bun path.
    DEFAULT_PATH = os.path.join(ROOT_PATH, "bin", "bun")
    # URL to bun install script.
    INSTALL_URL = "https://bun.sh/install"


# FNM config.
class Fnm(SimpleNamespace):
    """FNM constants."""

    # The FNM version.
    VERSION = "1.35.1"
    # The directory to store fnm.
    DIR = os.path.join(Nextpy.DIR, "fnm")
    FILENAME = get_fnm_name()
    # The fnm executable binary.
    EXE = os.path.join(DIR, "fnm.exe" if IS_WINDOWS else "fnm")

    # The URL to the fnm release binary
    INSTALL_URL = (
        f"https://github.com/Schniz/fnm/releases/download/v{VERSION}/{FILENAME}.zip"
    )


# Node / NPM config
class Node(SimpleNamespace):
    """Node/ NPM constants."""

    # The Node version.
    VERSION = "18.17.0"
    # The minimum required node version.
    MIN_VERSION = "16.8.0"

    # The node bin path.
    BIN_PATH = os.path.join(
        Fnm.DIR,
        "node-versions",
        f"v{VERSION}",
        "installation",
        "bin" if not IS_WINDOWS else "",
    )
    # The default path where node is installed.
    PATH = os.path.join(BIN_PATH, "node.exe" if IS_WINDOWS else "node")

    # The default path where npm is installed.
    NPM_PATH = os.path.join(BIN_PATH, "npm")


class PackageJson(SimpleNamespace):
    """Constants used to build the package.json file."""

    class Commands(SimpleNamespace):
        """The commands to define in package.json."""

        DEV = "next dev"
        EXPORT = "next build && next export -o _static"
        EXPORT_SITEMAP = "next build && next-sitemap && next export -o _static"
        PROD = "next start"

    PATH = os.path.join(Dirs.WEB, "package.json")

    DEPENDENCIES = {
        "axios": "1.4.0",
        "focus-visible": "5.2.0",
        "framer-motion": "10.16.4",
        "json5": "2.2.3",
        "next": "13.5.4",
        "next-sitemap": "4.1.8",
        "next-themes": "0.2.0",
        "react": "18.2.0",
        "react-dom": "18.2.0",
        "socket.io-client": "4.6.1",
        "universal-cookie": "4.0.4",
    }
    DEV_DEPENDENCIES = {
        "autoprefixer": "10.4.14",
        "postcss": "8.4.24",
    }
