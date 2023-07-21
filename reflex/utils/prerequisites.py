"""Everything related to fetching or initializing build prerequisites."""

from __future__ import annotations

import glob
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime
from fileinput import FileInput
from pathlib import Path
from types import ModuleType
from typing import Optional

import typer
from alembic.util.exc import CommandError
from packaging import version
from redis import Redis

from reflex import constants, model
from reflex.config import get_config
from reflex.utils import console, path_ops


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
            f"[red]Node.js version {constants.MIN_NODE_VERSION} or higher is required to run Reflex."
        )
        raise typer.Exit()

    # On Windows, we use npm instead of bun.
    if platform.system() == "Windows" or config.disable_bun:
        npm_path = path_ops.which("npm")
        if npm_path is None:
            raise FileNotFoundError("Reflex requires npm to be installed on Windows.")
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
    """Create a new rxconfig file.

    Args:
        app_name: The name of the app.
    """
    # Import here to avoid circular imports.
    from reflex.compiler import templates

    config_name = f"{re.sub(r'[^a-zA-Z]', '', app_name).capitalize()}Config"
    with open(constants.CONFIG_FILE, "w") as f:
        f.write(templates.RXCONFIG.render(app_name=app_name, config_name=config_name))


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
            files |= set([line.strip() for line in f.readlines()])
    # Write files to the .gitignore file.
    with open(constants.GITIGNORE_FILE, "w") as f:
        f.write(f"{(path_ops.join(sorted(files))).lstrip()}")


def initialize_app_directory(app_name: str, template: constants.Template):
    """Initialize the app directory on reflex init.

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
    """Initialize the web directory on reflex init."""
    console.log("Initializing the web directory.")
    path_ops.cp(constants.WEB_TEMPLATE_DIR, constants.WEB_DIR)
    path_ops.mkdir(constants.WEB_ASSETS_DIR)

    # update nextJS config based on rxConfig
    next_config_file = os.path.join(constants.WEB_DIR, constants.NEXT_CONFIG_FILE)

    with open(next_config_file, "r") as file:
        lines = file.readlines()
        for i, line in enumerate(lines):
            if "compress:" in line:
                new_line = line.replace(
                    "true", "true" if get_config().next_compression else "false"
                )
                lines[i] = new_line

    with open(next_config_file, "w") as file:
        file.writelines(lines)

    # Write the current version of distributed reflex package to a REFLEX_JSON."""
    with open(constants.REFLEX_JSON, "w") as f:
        reflex_json = {"version": constants.VERSION}
        json.dump(reflex_json, f, ensure_ascii=False)


def validate_and_install_bun(initialize=True):
    """Check that bun version requirements are met. If they are not,
    ask user whether to install required version.

    Args:
        initialize: whether this function is called on `reflex init` or `reflex run`.

    Raises:
        Exit: If the bun version is not supported.

    """
    bun_version = get_bun_version()
    if bun_version is not None and (
        bun_version < version.parse(constants.MIN_BUN_VERSION)
        or bun_version > version.parse(constants.MAX_BUN_VERSION)
    ):
        console.print(
            f"""[red]Bun version {bun_version} is not supported by Reflex. Please change your to bun version to be between {constants.MIN_BUN_VERSION} and {constants.MAX_BUN_VERSION}."""
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
        Exit: if installation failed
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
            raise FileNotFoundError("Reflex requires curl to be installed.")

        # Check if unzip is installed
        unzip_path = path_ops.which("unzip")
        if unzip_path is None:
            raise FileNotFoundError("Reflex requires unzip to be installed.")

        result = subprocess.run(constants.INSTALL_BUN, shell=True)

        if result.returncode != 0:
            raise typer.Exit(code=result.returncode)


def install_frontend_packages(web_dir: str):
    """Installs the base and custom frontend packages
    into the given web directory.

    Args:
        web_dir: The directory where the frontend code is located.
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
    if not os.path.exists(constants.REFLEX_JSON):
        return False
    with open(constants.REFLEX_JSON) as f:  # type: ignore
        app_version = json.load(f)["version"]
    return app_version == constants.VERSION


def check_admin_settings():
    """Check if admin settings are set and valid for logging in cli app."""
    admin_dash = get_config().admin_dash
    current_time = datetime.now()
    if admin_dash:
        if not admin_dash.models:
            console.print(
                f"[yellow][Admin Dashboard][/yellow] :megaphone: Admin dashboard enabled, but no models defined in [bold magenta]rxconfig.py[/bold magenta]. Time: {current_time}"
            )
        else:
            console.print(
                f"[yellow][Admin Dashboard][/yellow] Admin enabled, building admin dashboard. Time: {current_time}"
            )
            console.print(
                "Admin dashboard running at: [bold green]http://localhost:8000/admin[/bold green]"
            )


def check_db_initialized() -> bool:
    """Check if the database migrations are initialized.

    Returns:
        True if alembic is initialized (or if database is not used).
    """
    if get_config().db_url is not None and not Path(constants.ALEMBIC_CONFIG).exists():
        console.print(
            "[red]Database is not initialized. Run [bold]reflex db init[/bold] first."
        )
        return False
    return True


def check_schema_up_to_date():
    """Check if the sqlmodel metadata matches the current database schema."""
    if get_config().db_url is None or not Path(constants.ALEMBIC_CONFIG).exists():
        return
    with model.Model.get_db_engine().connect() as connection:
        try:
            if model.Model.alembic_autogenerate(
                connection=connection,
                write_migration_scripts=False,
            ):
                console.print(
                    "[red]Detected database schema changes. Run [bold]reflex db makemigrations[/bold] "
                    "to generate migration scripts.",
                )
        except CommandError as command_error:
            if "Target database is not up to date." in str(command_error):
                console.print(
                    f"[red]{command_error} Run [bold]reflex db migrate[/bold] to update database."
                )


def migrate_to_reflex():
    """Migration from Pynecone to Reflex."""
    # Check if the old config file exists.
    if not os.path.exists(constants.OLD_CONFIG_FILE):
        return

    # Ask the user if they want to migrate.
    action = console.ask(
        "Pynecone project detected. Automatically upgrade to Reflex?",
        choices=["y", "n"],
    )
    if action == "n":
        return

    # Rename pcconfig to rxconfig.
    console.print(
        f"[bold]Renaming {constants.OLD_CONFIG_FILE} to {constants.CONFIG_FILE}"
    )
    os.rename(constants.OLD_CONFIG_FILE, constants.CONFIG_FILE)

    # Find all python files in the app directory.
    file_pattern = os.path.join(get_config().app_name, "**/*.py")
    file_list = glob.glob(file_pattern, recursive=True)

    # Add the config file to the list of files to be migrated.
    file_list.append(constants.CONFIG_FILE)

    # Migrate all files.
    updates = {
        "Pynecone": "Reflex",
        "pynecone as pc": "reflex as rx",
        "pynecone.io": "reflex.dev",
        "pynecone": "reflex",
        "pc.": "rx.",
        "pcconfig": "rxconfig",
    }
    for file_path in file_list:
        with FileInput(file_path, inplace=True) as file:
            for line in file:
                for old, new in updates.items():
                    line = line.replace(old, new)
                print(line, end="")
