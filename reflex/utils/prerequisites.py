"""Everything related to fetching or initializing build prerequisites."""

from __future__ import annotations

import glob
import json
import os
import platform
import re
import sys
import tempfile
import threading
from fileinput import FileInput
from pathlib import Path
from types import ModuleType
from typing import Optional

import httpx
import typer
from alembic.util.exc import CommandError
from packaging import version
from redis import Redis

from reflex import constants, model
from reflex.config import get_config
from reflex.utils import console, path_ops
from reflex.utils.processes import new_process, show_logs

IS_WINDOWS = platform.system() == "Windows"


def check_node_version() -> bool:
    """Check the version of Node.js.

    Returns:
        Whether the version of Node.js is valid.
    """
    try:
        # Run the node -v command and capture the output.
        result = new_process([constants.NODE_PATH, "-v"], run=True)
    except FileNotFoundError:
        return False

    # The output will be in the form "vX.Y.Z", but version.parse() can handle it
    current_version = version.parse(result.stdout)  # type: ignore
    # Compare the version numbers
    return (
        current_version >= version.parse(constants.NODE_VERSION_MIN)
        if IS_WINDOWS
        else current_version == version.parse(constants.NODE_VERSION)
    )


def get_bun_version() -> Optional[version.Version]:
    """Get the version of bun.

    Returns:
        The version of bun.
    """
    try:
        # Run the bun -v command and capture the output
        result = new_process([constants.BUN_PATH, "-v"], run=True)
        return version.parse(result.stdout)  # type: ignore
    except FileNotFoundError:
        return None


def get_windows_package_manager() -> str:
    """Get the package manager for windows.

    Returns:
        The path to the package manager for windows.

    Raises:
        FileNotFoundError: If bun or npm is not installed.
    """
    npm_path = path_ops.which("npm")
    if npm_path is None:
        raise FileNotFoundError("Reflex requires npm to be installed on Windows.")
    return npm_path


def get_install_package_manager() -> str:
    """Get the package manager executable for installation.
      currently on unix systems, bun is used for installation only.

    Returns:
        The path to the package manager.
    """
    get_config()

    # On Windows, we use npm instead of bun.
    if platform.system() == "Windows":
        return get_windows_package_manager()

    # On other platforms, we use bun.
    return constants.BUN_PATH


def get_package_manager() -> str:
    """Get the package manager executable for running app.
      currently on unix systems, npm is used for running the app only.

    Returns:
        The path to the package manager.
    """
    get_config()

    if platform.system() == "Windows":
        return get_windows_package_manager()
    return constants.NPM_PATH


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
    console.info(f"Using redis at {config.redis_url}")
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

    Raises:
        Exit: if the app directory name is reflex.
    """
    app_name = os.getcwd().split(os.path.sep)[-1].replace("-", "_")

    # Make sure the app is not named "reflex".
    if app_name == constants.MODULE_NAME:
        console.error(
            f"The app directory cannot be named [bold]{constants.MODULE_NAME}[/bold]."
        )
        raise typer.Exit()

    return app_name


def create_config(app_name: str):
    """Create a new rxconfig file.

    Args:
        app_name: The name of the app.
    """
    # Import here to avoid circular imports.
    from reflex.compiler import templates

    config_name = f"{re.sub(r'[^a-zA-Z]', '', app_name).capitalize()}Config"
    with open(constants.CONFIG_FILE, "w") as f:
        console.debug(f"Creating {constants.CONFIG_FILE}")
        f.write(templates.RXCONFIG.render(app_name=app_name, config_name=config_name))


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
        console.debug(f"Creating {constants.GITIGNORE_FILE}")
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


def initialize_bun():
    """Check that bun requirements are met, and install if not."""
    if IS_WINDOWS:
        # Bun is not supported on Windows.
        console.debug("Skipping bun installation on Windows.")
        return

    # Check the bun version.
    bun_version = get_bun_version()
    if bun_version != version.parse(constants.BUN_VERSION):
        console.debug(
            f"Current bun version ({bun_version}) does not match ({constants.BUN_VERSION})."
        )
        remove_existing_bun_installation()
        install_bun()


def remove_existing_bun_installation():
    """Remove existing bun installation."""
    console.debug("Removing existing bun installation.")
    if os.path.exists(constants.BUN_PATH):
        path_ops.rm(constants.BUN_ROOT_PATH)


def initialize_node():
    """Validate nodejs have install or not."""
    if not check_node_version():
        install_node()


def download_and_run(url: str, *args, **env):
    """Download and run a script.

    Args:
        url: The url of the script.
        args: The arguments to pass to the script.
        env: The environment variables to use.
    """
    # Download the script
    console.debug(f"Downloading {url}")
    response = httpx.get(url)
    if response.status_code != httpx.codes.OK:
        response.raise_for_status()

    # Save the script to a temporary file.
    script = tempfile.NamedTemporaryFile()
    with open(script.name, "w") as f:
        f.write(response.text)

    # Run the script.
    env = {
        **os.environ,
        **env,
    }
    process = new_process(["bash", f.name, *args], env=env)
    show_logs(f"Installing {url}", process)


def install_node():
    """Install nvm and nodejs for use by Reflex.
       Independent of any existing system installations.

    Raises:
        Exit: if installation failed
    """
    # NVM is not supported on Windows.
    if IS_WINDOWS:
        console.error(
            f"Node.js version {constants.NODE_VERSION} or higher is required to run Reflex."
        )
        raise typer.Exit()

    # Create the nvm directory and install.
    path_ops.mkdir(constants.NVM_DIR)
    env = {**os.environ, "NVM_DIR": constants.NVM_DIR}
    download_and_run(constants.NVM_INSTALL_URL, **env)

    # Install node.
    # We use bash -c as we need to source nvm.sh to use nvm.
    process = new_process(
        [
            "bash",
            "-c",
            f". {constants.NVM_DIR}/nvm.sh && nvm install {constants.NODE_VERSION}",
        ],
        env=env,
    )
    show_logs("Installing node", process)


def install_bun():
    """Install bun onto the user's system.

    Raises:
        FileNotFoundError: If required packages are not found.
    """
    # Bun is not supported on Windows.
    if IS_WINDOWS:
        console.debug("Skipping bun installation on Windows.")
        return

    # Skip if bun is already installed.
    if os.path.exists(constants.BUN_PATH):
        console.debug("Skipping bun installation as it is already installed.")
        return

    #  if unzip is installed
    unzip_path = path_ops.which("unzip")
    if unzip_path is None:
        raise FileNotFoundError("Reflex requires unzip to be installed.")

    # Run the bun install script.
    download_and_run(
        constants.BUN_INSTALL_URL,
        f"bun-v{constants.BUN_VERSION}",
        BUN_INSTALL=constants.BUN_ROOT_PATH,
    )


def install_frontend_packages():
    """Installs the base and custom frontend packages."""
    # Install the base packages.
    process = new_process(
        [get_install_package_manager(), "install"],
        cwd=constants.WEB_DIR,
    )
    show_logs("Installing base frontend packages", process)

    # Install the app packages.
    packages = get_config().frontend_packages
    if len(packages) > 0:
        process = new_process(
            [get_install_package_manager(), "add", *packages],
            cwd=constants.WEB_DIR,
        )
        show_logs("Installing custom frontend packages", process)


def check_initialized(frontend: bool = True):
    """Check that the app is initialized.

    Args:
        frontend: Whether to check if the frontend is initialized.

    Raises:
        Exit: If the app is not initialized.
    """
    has_config = os.path.exists(constants.CONFIG_FILE)
    has_reflex_dir = IS_WINDOWS or os.path.exists(constants.REFLEX_DIR)
    has_web_dir = not frontend or os.path.exists(constants.WEB_DIR)

    # Check if the app is initialized.
    if not (has_config and has_reflex_dir and has_web_dir):
        console.error(
            f"The app is not initialized. Run [bold]{constants.MODULE_NAME} init[/bold] first."
        )
        raise typer.Exit()

    # Check that the template is up to date.
    if frontend and not is_latest_template():
        console.error(
            "The base app template has updated. Run [bold]reflex init[/bold] again."
        )
        raise typer.Exit()

    # Print a warning for Windows users.
    if IS_WINDOWS:
        console.warn(
            "We strongly advise using Windows Subsystem for Linux (WSL) for optimal performance with reflex."
        )


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


def initialize_frontend_dependencies():
    """Initialize all the frontend dependencies."""
    # Create the reflex directory.
    path_ops.mkdir(constants.REFLEX_DIR)

    # Install the frontend dependencies.
    threads = [
        threading.Thread(target=initialize_bun),
        threading.Thread(target=initialize_node),
    ]
    for thread in threads:
        thread.start()

    # Set up the web directory.
    initialize_web_directory()

    # Wait for the threads to finish.
    for thread in threads:
        thread.join()


def check_admin_settings():
    """Check if admin settings are set and valid for logging in cli app."""
    admin_dash = get_config().admin_dash
    if admin_dash:
        if not admin_dash.models:
            console.log(
                f"[yellow][Admin Dashboard][/yellow] :megaphone: Admin dashboard enabled, but no models defined in [bold magenta]rxconfig.py[/bold magenta]."
            )
        else:
            console.log(
                f"[yellow][Admin Dashboard][/yellow] Admin enabled, building admin dashboard."
            )
            console.log(
                "Admin dashboard running at: [bold green]http://localhost:8000/admin[/bold green]"
            )


def check_db_initialized() -> bool:
    """Check if the database migrations are initialized.

    Returns:
        True if alembic is initialized (or if database is not used).
    """
    if get_config().db_url is not None and not Path(constants.ALEMBIC_CONFIG).exists():
        console.error(
            "Database is not initialized. Run [bold]reflex db init[/bold] first."
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
                console.error(
                    "Detected database schema changes. Run [bold]reflex db makemigrations[/bold] "
                    "to generate migration scripts.",
                )
        except CommandError as command_error:
            if "Target database is not up to date." in str(command_error):
                console.error(
                    f"{command_error} Run [bold]reflex db migrate[/bold] to update database."
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
    console.log(
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
