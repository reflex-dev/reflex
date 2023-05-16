"""Everything related to fetching or initializing build prerequisites."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional

import typer
from packaging import version
from redis import Redis

from pynecone import constants
from pynecone.config import get_config
from pynecone.utils import console, path_ops


def check_node_version(min_version=constants.MIN_NODE_VERSION):
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
        # The output will be in the form "vX.Y.Z", but version.parse() can handle it
        current_version = version.parse(result.stdout.decode())
        # Compare the version numbers
        return current_version >= version.parse(min_version)
    except Exception:
        return False


def get_bun_version() -> Optional[version.Version]:
    """Get the version of bun.

    Returns:
        The version of bun.
    """
    try:
        # Run the bun -v command and capture the output
        result = subprocess.run(
            [os.path.expandvars(get_config().bun_path), "-v"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return version.parse(result.stdout.decode().strip())
    except Exception:
        return None


def get_package_manager() -> str:
    """Get the package manager executable.

    Returns:
        The path to the package manager.

    Raises:
        FileNotFoundError: If bun or npm is not installed.
        Exit: If the app directory is invalid.

    """
    config = get_config()

    # Check that the node version is valid.
    if not check_node_version():
        console.print(
            f"[red]Node.js version {constants.MIN_NODE_VERSION} or higher is required to run Pynecone."
        )
        raise typer.Exit()

    # On Windows, we use npm instead of bun.
    if platform.system() == "Windows" or config.disable_bun:
        npm_path = path_ops.which("npm")
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

    config_name = f"{re.sub(r'[^a-zA-Z]', '', app_name).capitalize()}Config"
    with open(constants.CONFIG_FILE, "w") as f:
        f.write(templates.PCCONFIG.render(app_name=app_name, config_name=config_name))


def create_web_directory(root: Path) -> str:
    """Creates a web directory in the given root directory
    and returns the path to the directory.

    Args:
        root (Path): The root directory of the project.

    Returns:
        The path to the web directory.
    """
    web_dir = str(root / constants.WEB_DIR)
    path_ops.cp(constants.WEB_TEMPLATE_DIR, web_dir, overwrite=False)
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
        f.write(path_ops.join(files))


def initialize_app_directory(app_name: str, template: constants.Template):
    """Initialize the app directory on pc init.

    Args:
        app_name: The name of the app.
        template: The template to use.
    """
    console.log("Initializing the app directory.")
    path_ops.cp(os.path.join(constants.TEMPLATE_DIR, "apps", template.value), app_name)
    path_ops.mv(
        os.path.join(app_name, template.value + ".py"),
        os.path.join(app_name, app_name + constants.PY_EXT),
    )
    path_ops.cp(constants.ASSETS_TEMPLATE_DIR, constants.APP_ASSETS_DIR)


def initialize_web_directory():
    """Initialize the web directory on pc init."""
    console.log("Initializing the web directory.")
    path_ops.rm(os.path.join(constants.WEB_TEMPLATE_DIR, constants.NODE_MODULES))
    path_ops.rm(os.path.join(constants.WEB_TEMPLATE_DIR, constants.PACKAGE_LOCK))
    path_ops.cp(constants.WEB_TEMPLATE_DIR, constants.WEB_DIR)

    # Write the current version of distributed pynecone package to a PCVERSION_APP_FILE."""
    with open(constants.PCVERSION_APP_FILE, "w") as f:
        pynecone_json = {"version": constants.VERSION}
        json.dump(pynecone_json, f, ensure_ascii=False)


def validate_and_install_bun(initialize=True):
    """Check that bun version requirements are met. If they are not,
    ask user whether to install required version.

    Args:
        initialize: whether this function is called on `pc init` or `pc run`.

    Raises:
        Exit: If the bun version is not supported.

    """
    bun_version = get_bun_version()
    if bun_version is not None and (
        bun_version < version.parse(constants.MIN_BUN_VERSION)
        or bun_version > version.parse(constants.MAX_BUN_VERSION)
    ):
        console.print(
            f"""[red]Bun version {bun_version} is not supported by Pynecone. Please change your to bun version to be between {constants.MIN_BUN_VERSION} and {constants.MAX_BUN_VERSION}."""
        )
        action = console.ask(
            "Enter 'yes' to install the latest supported bun version or 'no' to exit.",
            choices=["yes", "no"],
            default="no",
        )

        if action == "yes":
            remove_existing_bun_installation()
            install_bun()
            return
        else:
            raise typer.Exit()

    if initialize:
        install_bun()


def remove_existing_bun_installation():
    """Remove existing bun installation."""
    package_manager = get_package_manager()
    if os.path.exists(package_manager):
        console.log("Removing bun...")
        path_ops.rm(os.path.expandvars(constants.BUN_ROOT_PATH))


def install_bun():
    """Install bun onto the user's system.

    Raises:
        FileNotFoundError: if unzip or curl packages are not found.
    """
    # Bun is not supported on Windows.
    if platform.system() == "Windows":
        console.log("Skipping bun installation on Windows.")
        return

    # Only install if bun is not already installed.
    if not os.path.exists(get_package_manager()):
        console.log("Installing bun...")

        # Check if curl is installed
        curl_path = path_ops.which("curl")
        if curl_path is None:
            raise FileNotFoundError("Pynecone requires curl to be installed.")

        # Check if unzip is installed
        unzip_path = path_ops.which("unzip")
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
    if not os.path.exists(constants.PCVERSION_APP_FILE):
        return False
    with open(constants.PCVERSION_APP_FILE) as f:  # type: ignore
        app_version = json.load(f)["version"]
    return app_version == constants.VERSION
