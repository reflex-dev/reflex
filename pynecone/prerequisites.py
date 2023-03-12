"""Everything related to fetching or initializing build prerequisites."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional

import typer
from redis import Redis

from pynecone import console, constants
from pynecone.config import get_config
from pynecone.path import cp, join, mv, rm, which


def check_node_version(min_version):
    """Check the version of Node.js.

    Args:
        min_version: The minimum version of Node.js required.

    Returns:
        Whether the version of Node.js is high enough.
    """
    try:
        # Run the node -v command and capture the output
        result = subprocess.run(
            ["node", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        # The output will be in the form "vX.Y.Z", so we can split it on the "v" character and take the second part
        version = result.stdout.decode().strip().split("v")[1]
        # Compare the version numbers
        return version.split(".") >= min_version.split(".")
    except Exception:
        return False


def get_package_manager() -> str:
    """Get the package manager executable.

    Returns:
        The path to the package manager.

    Raises:
        FileNotFoundError: If bun or npm is not installed.
        Exit: If the app directory is invalid.

    """
    # Check that the node version is valid.
    if not check_node_version(constants.MIN_NODE_VERSION):
        console.print(
            f"[red]Node.js version {constants.MIN_NODE_VERSION} or higher is required to run Pynecone."
        )
        raise typer.Exit()

    # On Windows, we use npm instead of bun.
    if platform.system() == "Windows":
        npm_path = which("npm")
        if npm_path is None:
            raise FileNotFoundError("Pynecone requires npm to be installed on Windows.")
        return npm_path

    # On other platforms, we use bun.
    return os.path.expandvars(get_config().bun_path)


def get_app() -> ModuleType:
    """Get the app module based on the default config.

    Returns:
        The app based on the default config.
    """
    config = get_config()
    module = ".".join([config.app_name, config.app_name])
    sys.path.insert(0, os.getcwd())
    return __import__(module, fromlist=(constants.APP_VAR,))


def get_redis() -> Optional[Redis]:
    """Get the redis client.

    Returns:
        The redis client.
    """
    config = get_config()
    if config.redis_url is None:
        return None
    redis_url, redis_port = config.redis_url.split(":")
    print("Using redis at", config.redis_url)
    return Redis(host=redis_url, port=int(redis_port), db=0)


def get_production_backend_url() -> str:
    """Get the production backend URL.

    Returns:
        The production backend URL.
    """
    config = get_config()
    return constants.PRODUCTION_BACKEND_URL.format(
        username=config.username,
        app_name=config.app_name,
    )


def get_default_app_name() -> str:
    """Get the default app name.

    The default app name is the name of the current directory.

    Returns:
        The default app name.
    """
    return os.getcwd().split(os.path.sep)[-1].replace("-", "_")


def create_config(app_name: str):
    """Create a new pcconfig file.

    Args:
        app_name: The name of the app.
    """
    # Import here to avoid circular imports.
    from pynecone.compiler import templates

    with open(constants.CONFIG_FILE, "w") as f:
        f.write(templates.PCCONFIG.format(app_name=app_name))


def create_web_directory(root: Path) -> str:
    """Creates a web directory in the given root directory
    and returns the path to the directory.

    Args:
      root (Path): The root directory of the project.

    Returns:
      The path to the web directory.
    """
    web_dir = str(root / constants.WEB_DIR)
    cp(constants.WEB_TEMPLATE_DIR, web_dir, overwrite=False)
    return web_dir


def initialize_gitignore():
    """Initialize the template .gitignore file."""
    # The files to add to the .gitignore file.
    files = constants.DEFAULT_GITIGNORE

    # Subtract current ignored files.
    if os.path.exists(constants.GITIGNORE_FILE):
        with open(constants.GITIGNORE_FILE, "r") as f:
            files -= set(f.read().splitlines())

    # Add the new files to the .gitignore file.
    with open(constants.GITIGNORE_FILE, "a") as f:
        f.write(join(files))


def initialize_app_directory(app_name: str):
    """Initialize the app directory on pc init.

    Args:
        app_name: The name of the app.
    """
    console.log("Initializing the app directory.")
    cp(constants.APP_TEMPLATE_DIR, app_name)
    mv(
        os.path.join(app_name, constants.APP_TEMPLATE_FILE),
        os.path.join(app_name, app_name + constants.PY_EXT),
    )
    cp(constants.ASSETS_TEMPLATE_DIR, constants.APP_ASSETS_DIR)


def initialize_web_directory():
    """Initialize the web directory on pc init."""
    console.log("Initializing the web directory.")
    rm(os.path.join(constants.WEB_TEMPLATE_DIR, constants.NODE_MODULES))
    rm(os.path.join(constants.WEB_TEMPLATE_DIR, constants.PACKAGE_LOCK))
    cp(constants.WEB_TEMPLATE_DIR, constants.WEB_DIR)


def install_bun():
    """Install bun onto the user's system.

    Raises:
        FileNotFoundError: If the required packages are not installed.
    """
    # Bun is not supported on Windows.
    if platform.system() == "Windows":
        console.log("Skipping bun installation on Windows.")
        return

    # Only install if bun is not already installed.
    if not os.path.exists(get_package_manager()):
        console.log("Installing bun...")

        # Check if curl is installed
        curl_path = which("curl")
        if curl_path is None:
            raise FileNotFoundError("Pynecone requires curl to be installed.")

        # Check if unzip is installed
        unzip_path = which("unzip")
        if unzip_path is None:
            raise FileNotFoundError("Pynecone requires unzip to be installed.")

        os.system(constants.INSTALL_BUN)


def install_frontend_packages(web_dir: str):
    """Installs the base and custom frontend packages
    into the given web directory.

    Args:
      web_dir (str): The directory where the frontend code is located.
    """
    # Install the frontend packages.
    console.rule("[bold]Installing frontend packages")

    # Install the base packages.
    subprocess.run(
        [get_package_manager(), "install"],
        cwd=web_dir,
        stdout=subprocess.PIPE,
    )

    # Install the app packages.
    packages = get_config().frontend_packages
    if len(packages) > 0:
        subprocess.run(
            [get_package_manager(), "add", *packages],
            cwd=web_dir,
            stdout=subprocess.PIPE,
        )


def is_initialized() -> bool:
    """Check whether the app is initialized.

    Returns:
        Whether the app is initialized in the current directory.
    """
    return os.path.exists(constants.CONFIG_FILE) and os.path.exists(constants.WEB_DIR)


def is_latest_template() -> bool:
    """Whether the app is using the latest template.

    Returns:
        Whether the app is using the latest template.
    """
    with open(constants.PCVERSION_TEMPLATE_FILE) as f:  # type: ignore
        template_version = json.load(f)["version"]
    if not os.path.exists(constants.PCVERSION_APP_FILE):
        return False
    with open(constants.PCVERSION_APP_FILE) as f:  # type: ignore
        app_version = json.load(f)["version"]
    return app_version >= template_version
