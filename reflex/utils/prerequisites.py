"""Everything related to fetching or initializing build prerequisites."""

from __future__ import annotations

import glob
import json
import os
import re
import sys
import tempfile
import zipfile
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
from reflex.utils import console, path_ops, processes


def check_node_version() -> bool:
    """Check the version of Node.js.

    Returns:
        Whether the version of Node.js is valid.
    """
    current_version = get_node_version()
    if current_version:
        # Compare the version numbers
        return (
            current_version >= version.parse(constants.NODE_VERSION_MIN)
            if constants.IS_WINDOWS
            else current_version == version.parse(constants.NODE_VERSION)
        )
    return False


def get_node_version() -> Optional[version.Version]:
    """Get the version of node.

    Returns:
        The version of node.
    """
    try:
        result = processes.new_process([constants.NODE_PATH, "-v"], run=True)
        # The output will be in the form "vX.Y.Z", but version.parse() can handle it
        return version.parse(result.stdout)  # type: ignore
    except FileNotFoundError:
        return None


def get_bun_version() -> Optional[version.Version]:
    """Get the version of bun.

    Returns:
        The version of bun.
    """
    try:
        # Run the bun -v command and capture the output
        result = processes.new_process([get_config().bun_path, "-v"], run=True)
        return version.parse(result.stdout)  # type: ignore
    except FileNotFoundError:
        return None


def get_install_package_manager() -> str:
    """Get the package manager executable for installation.
      currently on unix systems, bun is used for installation only.

    Returns:
        The path to the package manager.
    """
    # On Windows, we use npm instead of bun.
    if constants.IS_WINDOWS:
        return constants.NPM_PATH

    # On other platforms, we use bun.
    return get_config().bun_path


def get_package_manager() -> str:
    """Get the package manager executable for running app.
      currently on unix systems, npm is used for running the app only.

    Returns:
        The path to the package manager.
    """
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
        raise typer.Exit(1)

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


def remove_existing_bun_installation():
    """Remove existing bun installation."""
    console.debug("Removing existing bun installation.")
    if os.path.exists(get_config().bun_path):
        path_ops.rm(constants.BUN_ROOT_PATH)


def download_and_run(url: str, *args, show_status: bool = False, **env):
    """Download and run a script.

    Args:
        url: The url of the script.
        args: The arguments to pass to the script.
        show_status: Whether to show the status of the script.
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
    env = {**os.environ, **env}
    process = processes.new_process(["bash", f.name, *args], env=env)
    show = processes.show_status if show_status else processes.show_logs
    show(f"Installing {url}", process)


def download_and_extract_fnm_zip(url: str):
    """Download and run a script.

    Args:
        url: The url of the fnm release zip binary.

    Raises:
        Exit: If an error occurs while downloading or extracting the FNM zip.
    """
    # TODO: make this OS agnostic
    # Download the zip file
    console.debug(f"Downloading {url}")
    fnm_zip_file = f"{constants.FNM_DIR}\\fnm_windows.zip"
    # Function to download and extract the FNM zip release
    try:
        # Download the FNM zip release
        # TODO: show progress to improve UX
        with httpx.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()
            with open(fnm_zip_file, "wb") as output_file:
                for chunk in response.iter_bytes():
                    output_file.write(chunk)

        # Extract the downloaded zip file
        with zipfile.ZipFile(fnm_zip_file, "r") as zip_ref:
            zip_ref.extractall(constants.FNM_DIR)

        console.debug("FNM for Windows downloaded and extracted successfully.")
    except Exception as e:
        console.error(f"An error occurred while downloading fnm package: {e}")
        raise typer.Exit(1) from e
    finally:
        # Clean up the downloaded zip file
        path_ops.rm(fnm_zip_file)


def install_node():
    """Install nvm and nodejs for use by Reflex.
    Independent of any existing system installations.
    """
    if constants.IS_WINDOWS:
        path_ops.mkdir(constants.FNM_DIR)
        if not os.path.exists(constants.FNM_EXE):
            download_and_extract_fnm_zip(constants.FNM_WINDOWS_INSTALL_URL)

        # Install node.
        process = processes.new_process(
            [
                "powershell",
                "-Command",
                f'& "{constants.FNM_EXE}" install {constants.NODE_VERSION} --fnm-dir "{constants.FNM_DIR}"',
            ],
        )
    else:  # All other platforms (Linux, MacOS)
        # TODO we can skip installation if check_node_version() checks out
        # Create the nvm directory and install.
        path_ops.mkdir(constants.NVM_DIR)
        env = {**os.environ, "NVM_DIR": constants.NVM_DIR}
        download_and_run(constants.NVM_INSTALL_URL, show_status=True, **env)

        # Install node.
        # We use bash -c as we need to source nvm.sh to use nvm.
        process = processes.new_process(
            [
                "bash",
                "-c",
                f". {constants.NVM_DIR}/nvm.sh && nvm install {constants.NODE_VERSION}",
            ],
            env=env,
        )
    processes.show_status("Installing node", process)


def install_bun():
    """Install bun onto the user's system.

    Raises:
        FileNotFoundError: If required packages are not found.
    """
    # Bun is not supported on Windows.
    if constants.IS_WINDOWS:
        console.debug("Skipping bun installation on Windows.")
        return

    # Skip if bun is already installed.
    if os.path.exists(get_config().bun_path):
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
    process = processes.new_process(
        [get_install_package_manager(), "install", "--loglevel", "silly"],
        cwd=constants.WEB_DIR,
        shell=constants.IS_WINDOWS,
    )
    processes.show_status("Installing base frontend packages", process)

    # Install the app packages.
    packages = get_config().frontend_packages
    if len(packages) > 0:
        process = processes.new_process(
            [get_install_package_manager(), "add", *packages],
            cwd=constants.WEB_DIR,
            shell=constants.IS_WINDOWS,
        )
        processes.show_status("Installing custom frontend packages", process)


def check_initialized(frontend: bool = True):
    """Check that the app is initialized.

    Args:
        frontend: Whether to check if the frontend is initialized.

    Raises:
        Exit: If the app is not initialized.
    """
    has_config = os.path.exists(constants.CONFIG_FILE)
    has_reflex_dir = not frontend or os.path.exists(constants.REFLEX_DIR)
    has_web_dir = not frontend or os.path.exists(constants.WEB_DIR)

    # Check if the app is initialized.
    if not (has_config and has_reflex_dir and has_web_dir):
        console.error(
            f"The app is not initialized. Run [bold]{constants.MODULE_NAME} init[/bold] first."
        )
        raise typer.Exit(1)

    # Check that the template is up to date.
    if frontend and not is_latest_template():
        console.error(
            "The base app template has updated. Run [bold]reflex init[/bold] again."
        )
        raise typer.Exit(1)

    # Print a warning for Windows users.
    if constants.IS_WINDOWS:
        console.warn(
            """Windows Subsystem for Linux (WSL) is recommended for improving initial install times."""
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


def validate_bun():
    """Validate bun if a custom bun path is specified to ensure the bun version meets requirements.

    Raises:
        Exit: If custom specified bun does not exist or does not meet requirements.
    """
    # if a custom bun path is provided, make sure its valid
    # This is specific to non-FHS OS
    bun_path = get_config().bun_path
    if bun_path != constants.DEFAULT_BUN_PATH:
        bun_version = get_bun_version()
        if not bun_version:
            console.error(
                "Failed to obtain bun version. Make sure the specified bun path in your config is correct."
            )
            raise typer.Exit(1)
        elif bun_version < version.parse(constants.MIN_BUN_VERSION):
            console.error(
                f"Reflex requires bun version {constants.BUN_VERSION} or higher to run, but the detected version is "
                f"{bun_version}. If you have specified a custom bun path in your config, make sure to provide one "
                f"that satisfies the minimum version requirement."
            )

            raise typer.Exit(1)


def validate_frontend_dependencies():
    """Validate frontend dependencies to ensure they meet requirements."""
    if constants.IS_WINDOWS:
        return
    return validate_bun()


def initialize_frontend_dependencies():
    """Initialize all the frontend dependencies."""
    # Create the reflex directory.
    path_ops.mkdir(constants.REFLEX_DIR)
    # validate dependencies before install
    validate_frontend_dependencies()
    # Install the frontend dependencies.
    processes.run_concurrently(install_node, install_bun)

    # Set up the web directory.
    initialize_web_directory()


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
