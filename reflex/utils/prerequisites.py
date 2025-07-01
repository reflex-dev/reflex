"""Everything related to fetching or initializing build prerequisites."""

from __future__ import annotations

import contextlib
import dataclasses
import functools
import importlib
import importlib.metadata
import importlib.util
import io
import json
import os
import platform
import random
import re
import shutil
import sys
import tempfile
import typing
import zipfile
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import NamedTuple
from urllib.parse import urlparse

import click
import httpx
from alembic.util.exc import CommandError
from packaging import version
from redis import Redis as RedisSync
from redis.asyncio import Redis
from redis.exceptions import RedisError

from reflex import constants, model
from reflex.compiler import templates
from reflex.config import Config, get_config
from reflex.environment import environment
from reflex.utils import console, net, path_ops, processes, redir
from reflex.utils.exceptions import SystemPackageMissingError
from reflex.utils.misc import get_module_path
from reflex.utils.registry import get_npm_registry

if typing.TYPE_CHECKING:
    from reflex.app import App


class AppInfo(NamedTuple):
    """A tuple containing the app instance and module."""

    app: App
    module: ModuleType


@dataclasses.dataclass(frozen=True)
class Template:
    """A template for a Reflex app."""

    name: str
    description: str
    code_url: str


@dataclasses.dataclass(frozen=True)
class CpuInfo:
    """Model to save cpu info."""

    manufacturer_id: str | None
    model_name: str | None
    address_width: int | None


def get_web_dir() -> Path:
    """Get the working directory for the frontend.

    Can be overridden with REFLEX_WEB_WORKDIR.

    Returns:
        The working directory.
    """
    return environment.REFLEX_WEB_WORKDIR.get()


def get_states_dir() -> Path:
    """Get the working directory for the states.

    Can be overridden with REFLEX_STATES_WORKDIR.

    Returns:
        The working directory.
    """
    return environment.REFLEX_STATES_WORKDIR.get()


def get_backend_dir() -> Path:
    """Get the working directory for the backend.

    Returns:
        The working directory.
    """
    return get_web_dir() / constants.Dirs.BACKEND


def check_latest_package_version(package_name: str):
    """Check if the latest version of the package is installed.

    Args:
        package_name: The name of the package.
    """
    if environment.REFLEX_CHECK_LATEST_VERSION.get() is False:
        return
    try:
        console.debug(f"Checking for the latest version of {package_name}...")
        # Get the latest version from PyPI
        current_version = importlib.metadata.version(package_name)
        url = f"https://pypi.org/pypi/{package_name}/json"
        response = net.get(url, timeout=2)
        latest_version = response.json()["info"]["version"]
        console.debug(f"Latest version of {package_name}: {latest_version}")
        if get_or_set_last_reflex_version_check_datetime():
            # Versions were already checked and saved in reflex.json, no need to warn again
            return
        if version.parse(current_version) < version.parse(latest_version):
            # Show a warning when the host version is older than PyPI version
            console.warn(
                f"Your version ({current_version}) of {package_name} is out of date. Upgrade to {latest_version} with 'pip install {package_name} --upgrade'"
            )
    except Exception:
        console.debug(f"Failed to check for the latest version of {package_name}.")


def get_or_set_last_reflex_version_check_datetime():
    """Get the last time a check was made for the latest reflex version.
    This is typically useful for cases where the host reflex version is
    less than that on Pypi.

    Returns:
        The last version check datetime.
    """
    reflex_json_file = get_web_dir() / constants.Reflex.JSON
    if not reflex_json_file.exists():
        return None
    # Open and read the file
    data = json.loads(reflex_json_file.read_text())
    last_version_check_datetime = data.get("last_version_check_datetime")
    if not last_version_check_datetime:
        data.update({"last_version_check_datetime": str(datetime.now())})
        path_ops.update_json_file(reflex_json_file, data)
    return last_version_check_datetime


def set_last_reflex_run_time():
    """Set the last Reflex run time."""
    path_ops.update_json_file(
        get_web_dir() / constants.Reflex.JSON,
        {"last_reflex_run_datetime": str(datetime.now())},
    )


def check_node_version() -> bool:
    """Check the version of Node.js.

    Returns:
        Whether the version of Node.js is valid.
    """
    current_version = get_node_version()
    return current_version is not None and current_version >= version.parse(
        constants.Node.MIN_VERSION
    )


def get_node_version() -> version.Version | None:
    """Get the version of node.

    Returns:
        The version of node.
    """
    node_path = path_ops.get_node_path()
    if node_path is None:
        return None
    try:
        result = processes.new_process([node_path, "-v"], run=True)
        # The output will be in the form "vX.Y.Z", but version.parse() can handle it
        return version.parse(result.stdout)
    except (FileNotFoundError, TypeError):
        return None


def get_bun_version(bun_path: Path | None = None) -> version.Version | None:
    """Get the version of bun.

    Args:
        bun_path: The path to the bun executable.

    Returns:
        The version of bun.
    """
    bun_path = bun_path or path_ops.get_bun_path()
    if bun_path is None:
        return None
    try:
        # Run the bun -v command and capture the output
        result = processes.new_process([str(bun_path), "-v"], run=True)
        return version.parse(str(result.stdout))
    except FileNotFoundError:
        return None
    except version.InvalidVersion as e:
        console.warn(
            f"The detected bun version ({e.args[0]}) is not valid. Defaulting to None."
        )
        return None


def prefer_npm_over_bun() -> bool:
    """Check if npm should be preferred over bun.

    Returns:
        If npm should be preferred over bun.
    """
    return npm_escape_hatch() or (
        constants.IS_WINDOWS and windows_check_onedrive_in_path()
    )


def get_nodejs_compatible_package_managers(
    raise_on_none: bool = True,
) -> Sequence[str]:
    """Get the package manager executable for installation. Typically, bun is used for installation.

    Args:
        raise_on_none: Whether to raise an error if the package manager is not found.

    Returns:
        The path to the package manager.

    Raises:
        FileNotFoundError: If the package manager is not found and raise_on_none is True.
    """
    bun_package_manager = (
        str(bun_path) if (bun_path := path_ops.get_bun_path()) else None
    )

    npm_package_manager = (
        str(npm_path) if (npm_path := path_ops.get_npm_path()) else None
    )

    if prefer_npm_over_bun():
        package_managers = [npm_package_manager, bun_package_manager]
    else:
        package_managers = [bun_package_manager, npm_package_manager]

    package_managers = list(filter(None, package_managers))

    if not package_managers and raise_on_none:
        msg = "Bun or npm not found. You might need to rerun `reflex init` or install either."
        raise FileNotFoundError(msg)

    return package_managers


def is_outdated_nodejs_installed():
    """Check if the installed Node.js version is outdated.

    Returns:
        If the installed Node.js version is outdated.
    """
    current_version = get_node_version()
    if current_version is not None and current_version < version.parse(
        constants.Node.MIN_VERSION
    ):
        console.warn(
            f"Your version ({current_version}) of Node.js is out of date. Upgrade to {constants.Node.MIN_VERSION} or higher."
        )
        return True
    return False


def get_js_package_executor(raise_on_none: bool = False) -> Sequence[Sequence[str]]:
    """Get the paths to package managers for running commands. Ordered by preference.
    This is currently identical to get_install_package_managers, but may change in the future.

    Args:
        raise_on_none: Whether to raise an error if no package managers is not found.

    Returns:
        The paths to the package managers as a list of lists, where each list is the command to run and its arguments.

    Raises:
        FileNotFoundError: If no package managers are found and raise_on_none is True.
    """
    bun_package_manager = (
        [str(bun_path)] + (["--bun"] if is_outdated_nodejs_installed() else [])
        if (bun_path := path_ops.get_bun_path())
        else None
    )

    npm_package_manager = (
        [str(npm_path)] if (npm_path := path_ops.get_npm_path()) else None
    )

    if prefer_npm_over_bun():
        package_managers = [npm_package_manager, bun_package_manager]
    else:
        package_managers = [bun_package_manager, npm_package_manager]

    package_managers = list(filter(None, package_managers))

    if not package_managers and raise_on_none:
        msg = "Bun or npm not found. You might need to rerun `reflex init` or install either."
        raise FileNotFoundError(msg)

    return package_managers


def windows_check_onedrive_in_path() -> bool:
    """For windows, check if oneDrive is present in the project dir path.

    Returns:
        If oneDrive is in the path of the project directory.
    """
    return "onedrive" in str(Path.cwd()).lower()


def npm_escape_hatch() -> bool:
    """If the user sets REFLEX_USE_NPM, prefer npm over bun.

    Returns:
        If the user has set REFLEX_USE_NPM.
    """
    return environment.REFLEX_USE_NPM.get()


def _check_app_name(config: Config):
    """Check if the app name is valid and matches the folder structure.

    Args:
        config: The config object.

    Raises:
        RuntimeError: If the app name is not set, folder doesn't exist, or doesn't match config.
        ModuleNotFoundError: If the app_name is not importable (i.e., not a valid Python package, folder structure being wrong).
    """
    if not config.app_name:
        msg = (
            "Cannot get the app module because `app_name` is not set in rxconfig! "
            "If this error occurs in a reflex test case, ensure that `get_app` is mocked."
        )
        raise RuntimeError(msg)

    from reflex.utils.misc import get_module_path, with_cwd_in_syspath

    with with_cwd_in_syspath():
        module_path = get_module_path(config.module)
        if module_path is None:
            msg = f"Module {config.module} not found. "
            if config.app_module_import is not None:
                msg += f"Ensure app_module_import='{config.app_module_import}' in rxconfig.py matches your folder structure."
            else:
                msg += f"Ensure app_name='{config.app_name}' in rxconfig.py matches your folder structure."
            raise ModuleNotFoundError(msg)


def get_app(reload: bool = False) -> ModuleType:
    """Get the app module based on the default config.

    Args:
        reload: Re-import the app module from disk

    Returns:
        The app based on the default config.

    Raises:
        Exception: If an error occurs while getting the app module.
    """
    from reflex.utils import telemetry

    try:
        config = get_config()

        _check_app_name(config)

        module = config.module
        sys.path.insert(0, str(Path.cwd()))
        app = (
            __import__(module, fromlist=(constants.CompileVars.APP,))
            if not config.app_module
            else config.app_module
        )
        if reload:
            from reflex.page import DECORATED_PAGES
            from reflex.state import reload_state_module

            # Reset rx.State subclasses to avoid conflict when reloading.
            reload_state_module(module=module)

            DECORATED_PAGES.clear()

            # Reload the app module.
            importlib.reload(app)
    except Exception as ex:
        telemetry.send_error(ex, context="frontend")
        raise
    else:
        return app


def get_and_validate_app(
    reload: bool = False, check_if_schema_up_to_date: bool = False
) -> AppInfo:
    """Get the app instance based on the default config and validate it.

    Args:
        reload: Re-import the app module from disk
        check_if_schema_up_to_date: If True, check if the schema is up to date.

    Returns:
        The app instance and the app module.

    Raises:
        RuntimeError: If the app instance is not an instance of rx.App.
    """
    from reflex.app import App

    app_module = get_app(reload=reload)
    app = getattr(app_module, constants.CompileVars.APP)
    if not isinstance(app, App):
        msg = "The app instance in the specified app_module_import in rxconfig must be an instance of rx.App."
        raise RuntimeError(msg)

    if check_if_schema_up_to_date:
        check_schema_up_to_date()

    return AppInfo(app=app, module=app_module)


def validate_app(
    reload: bool = False, check_if_schema_up_to_date: bool = False
) -> None:
    """Validate the app instance based on the default config.

    Args:
        reload: Re-import the app module from disk
        check_if_schema_up_to_date: If True, check if the schema is up to date.
    """
    get_and_validate_app(
        reload=reload, check_if_schema_up_to_date=check_if_schema_up_to_date
    )


def get_compiled_app(
    reload: bool = False,
    prerender_routes: bool = False,
    dry_run: bool = False,
    check_if_schema_up_to_date: bool = False,
) -> ModuleType:
    """Get the app module based on the default config after first compiling it.

    Args:
        reload: Re-import the app module from disk
        prerender_routes: Whether to prerender routes.
        dry_run: If True, do not write the compiled app to disk.
        check_if_schema_up_to_date: If True, check if the schema is up to date.

    Returns:
        The compiled app based on the default config.
    """
    app, app_module = get_and_validate_app(
        reload=reload, check_if_schema_up_to_date=check_if_schema_up_to_date
    )
    # For py3.9 compatibility when redis is used, we MUST add any decorator pages
    # before compiling the app in a thread to avoid event loop error (REF-2172).
    app._apply_decorated_pages()
    app._compile(prerender_routes=prerender_routes, dry_run=dry_run)
    return app_module


def compile_app(
    reload: bool = False,
    prerender_routes: bool = False,
    dry_run: bool = False,
    check_if_schema_up_to_date: bool = False,
) -> None:
    """Compile the app module based on the default config.

    Args:
        reload: Re-import the app module from disk
        prerender_routes: Whether to prerender routes.
        dry_run: If True, do not write the compiled app to disk.
        check_if_schema_up_to_date: If True, check if the schema is up to date.
    """
    get_compiled_app(
        reload=reload,
        prerender_routes=prerender_routes,
        dry_run=dry_run,
        check_if_schema_up_to_date=check_if_schema_up_to_date,
    )


def _can_colorize() -> bool:
    """Check if the output can be colorized.

    Copied from _colorize.can_colorize.

    https://raw.githubusercontent.com/python/cpython/refs/heads/main/Lib/_colorize.py

    Returns:
        If the output can be colorized
    """
    file = sys.stdout

    if not sys.flags.ignore_environment:
        if os.environ.get("PYTHON_COLORS") == "0":
            return False
        if os.environ.get("PYTHON_COLORS") == "1":
            return True
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("TERM") == "dumb":
        return False

    if not hasattr(file, "fileno"):
        return False

    if sys.platform == "win32":
        try:
            import nt

            if not nt._supports_virtual_terminal():
                return False
        except (ImportError, AttributeError):
            return False

    try:
        return os.isatty(file.fileno())
    except io.UnsupportedOperation:
        return file.isatty()


def compile_or_validate_app(
    compile: bool = False,
    check_if_schema_up_to_date: bool = False,
    prerender_routes: bool = False,
) -> bool:
    """Compile or validate the app module based on the default config.

    Args:
        compile: Whether to compile the app.
        check_if_schema_up_to_date: If True, check if the schema is up to date.
        prerender_routes: Whether to prerender routes.

    Returns:
        If the app is compiled successfully.
    """
    try:
        if compile:
            compile_app(
                check_if_schema_up_to_date=check_if_schema_up_to_date,
                prerender_routes=prerender_routes,
            )
        else:
            validate_app(check_if_schema_up_to_date=check_if_schema_up_to_date)
    except Exception as e:
        if isinstance(e, click.exceptions.Exit):
            return False

        import traceback

        sys_exception = sys.exception()

        try:
            colorize = _can_colorize()
            traceback.print_exception(e, colorize=colorize)  # pyright: ignore[reportCallIssue]
        except Exception:
            traceback.print_exception(sys_exception)
        return False
    return True


def get_redis() -> Redis | None:
    """Get the asynchronous redis client.

    Returns:
        The asynchronous redis client.
    """
    if (redis_url := parse_redis_url()) is not None:
        return Redis.from_url(
            redis_url,
            retry_on_error=[RedisError],
        )
    return None


def get_redis_sync() -> RedisSync | None:
    """Get the synchronous redis client.

    Returns:
        The synchronous redis client.
    """
    if (redis_url := parse_redis_url()) is not None:
        return RedisSync.from_url(
            redis_url,
            retry_on_error=[RedisError],
        )
    return None


def parse_redis_url() -> str | None:
    """Parse the REFLEX_REDIS_URL in config if applicable.

    Returns:
        If url is non-empty, return the URL as it is.

    Raises:
        ValueError: If the REFLEX_REDIS_URL is not a supported scheme.
    """
    config = get_config()
    if not config.redis_url:
        return None
    if not config.redis_url.startswith(("redis://", "rediss://", "unix://")):
        msg = "REFLEX_REDIS_URL must start with 'redis://', 'rediss://', or 'unix://'."
        raise ValueError(msg)
    return config.redis_url


async def get_redis_status() -> dict[str, bool | None]:
    """Checks the status of the Redis connection.

    Attempts to connect to Redis and send a ping command to verify connectivity.

    Returns:
        The status of the Redis connection.
    """
    try:
        status = True
        redis_client = get_redis_sync()
        if redis_client is not None:
            redis_client.ping()
        else:
            status = None
    except RedisError:
        status = False

    return {"redis": status}


def validate_app_name(app_name: str | None = None) -> str:
    """Validate the app name.

    The default app name is the name of the current directory.

    Args:
        app_name: the name passed by user during reflex init

    Returns:
        The app name after validation.

    Raises:
        Exit: if the app directory name is reflex or if the name is not standard for a python package name.
    """
    app_name = app_name if app_name else Path.cwd().name.replace("-", "_")
    # Make sure the app is not named "reflex".
    if app_name.lower() == constants.Reflex.MODULE_NAME:
        console.error(
            f"The app directory cannot be named [bold]{constants.Reflex.MODULE_NAME}[/bold]."
        )
        raise click.exceptions.Exit(1)

    # Make sure the app name is standard for a python package name.
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", app_name):
        console.error(
            "The app directory name must start with a letter and can contain letters, numbers, and underscores."
        )
        raise click.exceptions.Exit(1)

    return app_name


def rename_path_up_tree(full_path: str | Path, old_name: str, new_name: str) -> Path:
    """Rename all instances of `old_name` in the path (file and directories) to `new_name`.
    The renaming stops when we reach the directory containing `rxconfig.py`.

    Args:
        full_path: The full path to start renaming from.
        old_name: The name to be replaced.
        new_name: The replacement name.

    Returns:
         The updated path after renaming.
    """
    current_path = Path(full_path)
    new_path = None

    while True:
        directory, base = current_path.parent, current_path.name
        # Stop renaming when we reach the root dir (which contains rxconfig.py)
        if current_path.is_dir() and (current_path / "rxconfig.py").exists():
            new_path = current_path
            break

        if old_name == base.removesuffix(constants.Ext.PY):
            new_base = base.replace(old_name, new_name)
            new_path = directory / new_base
            current_path.rename(new_path)
            console.debug(f"Renamed {current_path} -> {new_path}")
            current_path = new_path
        else:
            new_path = current_path

        # Move up the directory tree
        current_path = directory

    return new_path


def rename_app(new_app_name: str, loglevel: constants.LogLevel):
    """Rename the app directory.

    Args:
        new_app_name: The new name for the app.
        loglevel: The log level to use.

    Raises:
        Exit: If the command is not ran in the root dir or the app module cannot be imported.
    """
    # Set the log level.
    console.set_log_level(loglevel)

    if not constants.Config.FILE.exists():
        console.error(
            "No rxconfig.py found. Make sure you are in the root directory of your app."
        )
        raise click.exceptions.Exit(1)

    sys.path.insert(0, str(Path.cwd()))

    config = get_config()
    module_path = get_module_path(config.module)
    if module_path is None:
        console.error(f"Could not find module {config.module}.")
        raise click.exceptions.Exit(1)

    console.info(f"Renaming app directory to {new_app_name}.")
    process_directory(
        Path.cwd(),
        config.app_name,
        new_app_name,
        exclude_dirs=[constants.Dirs.WEB, constants.Dirs.APP_ASSETS],
    )

    rename_path_up_tree(module_path, config.app_name, new_app_name)

    console.success(f"App directory renamed to [bold]{new_app_name}[/bold].")


def rename_imports_and_app_name(file_path: str | Path, old_name: str, new_name: str):
    """Rename imports the file using string replacement as well as app_name in rxconfig.py.

    Args:
        file_path: The file to process.
        old_name: The old name to replace.
        new_name: The new name to use.
    """
    file_path = Path(file_path)
    content = file_path.read_text()

    # Replace `from old_name.` or `from old_name` with `from new_name`
    content = re.sub(
        rf"\bfrom {re.escape(old_name)}(\b|\.|\s)",
        lambda match: f"from {new_name}{match.group(1)}",
        content,
    )

    # Replace `import old_name` with `import new_name`
    content = re.sub(
        rf"\bimport {re.escape(old_name)}\b",
        f"import {new_name}",
        content,
    )

    # Replace `app_name="old_name"` in rx.Config
    content = re.sub(
        rf'\bapp_name\s*=\s*["\']{re.escape(old_name)}["\']',
        f'app_name="{new_name}"',
        content,
    )

    # Replace positional argument `"old_name"` in rx.Config
    content = re.sub(
        rf'\brx\.Config\(\s*["\']{re.escape(old_name)}["\']',
        f'rx.Config("{new_name}"',
        content,
    )

    file_path.write_text(content)


def process_directory(
    directory: str | Path,
    old_name: str,
    new_name: str,
    exclude_dirs: list | None = None,
    extensions: list | None = None,
):
    """Process files with specified extensions in a directory, excluding specified directories.

    Args:
        directory: The root directory to process.
        old_name: The old name to replace.
        new_name: The new name to use.
        exclude_dirs: List of directory names to exclude. Defaults to None.
        extensions: List of file extensions to process.
    """
    exclude_dirs = exclude_dirs or []
    extensions = extensions or [
        constants.Ext.PY,
        constants.Ext.MD,
    ]  # include .md files, typically used in reflex-web.
    extensions_set = {ext.lstrip(".") for ext in extensions}
    directory = Path(directory)

    root_exclude_dirs = {directory / exclude_dir for exclude_dir in exclude_dirs}

    files = (
        p.resolve()
        for p in directory.glob("**/*")
        if p.is_file() and p.suffix.lstrip(".") in extensions_set
    )

    for file_path in files:
        if not any(
            file_path.is_relative_to(exclude_dir) for exclude_dir in root_exclude_dirs
        ):
            rename_imports_and_app_name(file_path, old_name, new_name)


def create_config(app_name: str):
    """Create a new rxconfig file.

    Args:
        app_name: The name of the app.
    """
    # Import here to avoid circular imports.
    from reflex.compiler import templates

    config_name = f"{re.sub(r'[^a-zA-Z]', '', app_name).capitalize()}Config"

    console.debug(f"Creating {constants.Config.FILE}")
    constants.Config.FILE.write_text(
        templates.RXCONFIG.render(app_name=app_name, config_name=config_name)
    )


def initialize_gitignore(
    gitignore_file: Path = constants.GitIgnore.FILE,
    files_to_ignore: set[str] | list[str] = constants.GitIgnore.DEFAULTS,
):
    """Initialize the template .gitignore file.

    Args:
        gitignore_file: The .gitignore file to create.
        files_to_ignore: The files to add to the .gitignore file.
    """
    # Combine with the current ignored files.
    current_ignore: list[str] = []
    if gitignore_file.exists():
        current_ignore = [ln.strip() for ln in gitignore_file.read_text().splitlines()]

    if files_to_ignore == current_ignore:
        console.debug(f"{gitignore_file} already up to date.")
        return
    files_to_ignore = [ln for ln in files_to_ignore if ln not in current_ignore]
    files_to_ignore += current_ignore

    # Write files to the .gitignore file.
    gitignore_file.touch(exist_ok=True)
    console.debug(f"Creating {gitignore_file}")
    gitignore_file.write_text("\n".join(files_to_ignore) + "\n")


def initialize_requirements_txt() -> bool:
    """Initialize the requirements.txt file.
    If absent and no pyproject.toml file exists, generate one for the user.
    If the requirements.txt does not have reflex as dependency,
    generate a requirement pinning current version and append to
    the requirements.txt file.

    Returns:
        True if the user has to update the requirements.txt file.

    Raises:
        Exit: If the requirements.txt file cannot be read or written to.
    """
    requirements_file_path = Path(constants.RequirementsTxt.FILE)
    if (
        not requirements_file_path.exists()
        and Path(constants.PyprojectToml.FILE).exists()
    ):
        return True

    requirements_file_path.touch(exist_ok=True)

    for encoding in [None, "utf-8"]:
        try:
            content = requirements_file_path.read_text(encoding)
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            console.error(f"Failed to read {requirements_file_path}.")
            raise click.exceptions.Exit(1) from e
    else:
        return True

    for line in content.splitlines():
        if re.match(r"^reflex[^a-zA-Z0-9]", line):
            console.debug(f"{requirements_file_path} already has reflex as dependency.")
            return False

    console.debug(
        f"Appending {constants.RequirementsTxt.DEFAULTS_STUB} to {requirements_file_path}"
    )
    with requirements_file_path.open("a", encoding=encoding) as f:
        f.write(
            "\n" + constants.RequirementsTxt.DEFAULTS_STUB + constants.Reflex.VERSION
        )

    return False


def initialize_app_directory(
    app_name: str,
    template_name: str = constants.Templates.DEFAULT,
    template_code_dir_name: str | None = None,
    template_dir: Path | None = None,
):
    """Initialize the app directory on reflex init.

    Args:
        app_name: The name of the app.
        template_name: The name of the template to use.
        template_code_dir_name: The name of the code directory in the template.
        template_dir: The directory of the template source files.

    Raises:
        Exit: If template_name, template_code_dir_name, template_dir combination is not supported.
    """
    console.log("Initializing the app directory.")

    # By default, use the blank template from local assets.
    if template_name == constants.Templates.DEFAULT:
        if template_code_dir_name is not None or template_dir is not None:
            console.error(
                f"Only {template_name=} should be provided, got {template_code_dir_name=}, {template_dir=}."
            )
            raise click.exceptions.Exit(1)
        template_code_dir_name = constants.Templates.Dirs.CODE
        template_dir = Path(constants.Templates.Dirs.BASE, "apps", template_name)
    else:
        if template_code_dir_name is None or template_dir is None:
            console.error(
                f"For `{template_name}` template, `template_code_dir_name` and `template_dir` should both be provided."
            )
            raise click.exceptions.Exit(1)

    console.debug(f"Using {template_name=} {template_dir=} {template_code_dir_name=}.")

    # Remove __pycache__ dirs in template directory and current directory.
    for pycache_dir in [
        *template_dir.glob("**/__pycache__"),
        *Path.cwd().glob("**/__pycache__"),
    ]:
        shutil.rmtree(pycache_dir, ignore_errors=True)

    for file in template_dir.iterdir():
        # Copy the file to current directory but keep the name the same.
        path_ops.cp(str(file), file.name)

    # Rename the template app to the app name.
    path_ops.mv(template_code_dir_name, app_name)
    path_ops.mv(
        Path(app_name) / (template_name + constants.Ext.PY),
        Path(app_name) / (app_name + constants.Ext.PY),
    )

    # Fix up the imports.
    path_ops.find_replace(
        app_name,
        f"from {template_name}",
        f"from {app_name}",
    )


def get_project_hash(raise_on_fail: bool = False) -> int | None:
    """Get the project hash from the reflex.json file if the file exists.

    Args:
        raise_on_fail: Whether to raise an error if the file does not exist.

    Returns:
        project_hash: The app hash.
    """
    json_file = get_web_dir() / constants.Reflex.JSON
    if not json_file.exists() and not raise_on_fail:
        return None
    data = json.loads(json_file.read_text())
    return data.get("project_hash")


def initialize_web_directory():
    """Initialize the web directory on reflex init."""
    console.log("Initializing the web directory.")

    # Reuse the hash if one is already created, so we don't over-write it when running reflex init
    project_hash = get_project_hash()

    console.debug(f"Copying {constants.Templates.Dirs.WEB_TEMPLATE} to {get_web_dir()}")
    path_ops.copy_tree(constants.Templates.Dirs.WEB_TEMPLATE, str(get_web_dir()))

    console.debug("Initializing the web directory.")
    initialize_package_json()

    console.debug("Initializing the bun config file.")
    initialize_bun_config()

    console.debug("Initializing the .npmrc file.")
    initialize_npmrc()

    console.debug("Initializing the public directory.")
    path_ops.mkdir(get_web_dir() / constants.Dirs.PUBLIC)

    console.debug("Initializing the react-router.config.js file.")
    update_react_router_config()

    console.debug("Initializing the reflex.json file.")
    # Initialize the reflex json file.
    init_reflex_json(project_hash=project_hash)


def _compile_package_json():
    return templates.PACKAGE_JSON.render(
        scripts={
            "dev": constants.PackageJson.Commands.DEV,
            "export": constants.PackageJson.Commands.EXPORT,
            "prod": constants.PackageJson.Commands.PROD,
        },
        dependencies=constants.PackageJson.DEPENDENCIES,
        dev_dependencies=constants.PackageJson.DEV_DEPENDENCIES,
        overrides=constants.PackageJson.OVERRIDES,
    )


def initialize_package_json():
    """Render and write in .web the package.json file."""
    output_path = get_web_dir() / constants.PackageJson.PATH
    output_path.write_text(_compile_package_json())


def initialize_bun_config():
    """Initialize the bun config file."""
    bun_config_path = get_web_dir() / constants.Bun.CONFIG_PATH

    if (custom_bunfig := Path(constants.Bun.CONFIG_PATH)).exists():
        bunfig_content = custom_bunfig.read_text()
        console.info(f"Copying custom bunfig.toml inside {get_web_dir()} folder")
    else:
        best_registry = get_npm_registry()
        bunfig_content = constants.Bun.DEFAULT_CONFIG.format(registry=best_registry)

    bun_config_path.write_text(bunfig_content)


def initialize_npmrc():
    """Initialize the .npmrc file."""
    npmrc_path = get_web_dir() / constants.Node.CONFIG_PATH

    if (custom_npmrc := Path(constants.Node.CONFIG_PATH)).exists():
        npmrc_content = custom_npmrc.read_text()
        console.info(f"Copying custom .npmrc inside {get_web_dir()} folder")
    else:
        best_registry = get_npm_registry()
        npmrc_content = constants.Node.DEFAULT_CONFIG.format(registry=best_registry)

    npmrc_path.write_text(npmrc_content)


def init_reflex_json(project_hash: int | None):
    """Write the hash of the Reflex project to a REFLEX_JSON.

    Reuse the hash if one is already created, therefore do not
    overwrite it every time we run the reflex init command
    .

    Args:
        project_hash: The app hash.
    """
    if project_hash is not None:
        console.debug(f"Project hash is already set to {project_hash}.")
    else:
        # Get a random project hash.
        project_hash = random.getrandbits(128)
        console.debug(f"Setting project hash to {project_hash}.")

    # Write the hash and version to the reflex json file.
    reflex_json = {
        "version": constants.Reflex.VERSION,
        "project_hash": project_hash,
    }
    path_ops.update_json_file(get_web_dir() / constants.Reflex.JSON, reflex_json)


def update_react_router_config(prerender_routes: bool = False):
    """Update react-router.config.js config from Reflex config.

    Args:
        prerender_routes: Whether to enable prerendering of routes.
    """
    react_router_config_file_path = get_web_dir() / constants.ReactRouter.CONFIG_FILE

    new_react_router_config = _update_react_router_config(
        get_config(), prerender_routes=prerender_routes
    )

    # Overwriting the config file triggers a full server reload, so make sure
    # there is actually a diff.
    old_react_router_config = (
        react_router_config_file_path.read_text()
        if react_router_config_file_path.exists()
        else ""
    )
    if old_react_router_config != new_react_router_config:
        react_router_config_file_path.write_text(new_react_router_config)


def _update_react_router_config(config: Config, prerender_routes: bool = False):
    react_router_config = {
        "basename": "/" + (config.frontend_path or "").removeprefix("/"),
        "future": {
            "unstable_optimizeDeps": True,
        },
        "ssr": False,
    }

    if prerender_routes:
        react_router_config["prerender"] = True
        react_router_config["build"] = constants.Dirs.BUILD_DIR

    return f"export default {json.dumps(react_router_config)};"


def remove_existing_bun_installation():
    """Remove existing bun installation."""
    console.debug("Removing existing bun installation.")
    if Path(get_config().bun_path).exists():
        path_ops.rm(constants.Bun.ROOT_PATH)


def download_and_run(url: str, *args, show_status: bool = False, **env):
    """Download and run a script.

    Args:
        url: The url of the script.
        args: The arguments to pass to the script.
        show_status: Whether to show the status of the script.
        env: The environment variables to use.

    Raises:
        Exit: If the script fails to download.
    """
    # Download the script
    console.debug(f"Downloading {url}")
    try:
        response = net.get(url)
        response.raise_for_status()
    except httpx.HTTPError as e:
        console.error(
            f"Failed to download bun install script. You can install or update bun manually from https://bun.sh \n{e}"
        )
        raise click.exceptions.Exit(1) from None

    # Save the script to a temporary file.
    with tempfile.NamedTemporaryFile() as tempfile_file:
        script = Path(tempfile_file.name)

        script.write_text(response.text)

        # Run the script.
        env = {**os.environ, **env}
        process = processes.new_process(["bash", str(script), *args], env=env)
        show = processes.show_status if show_status else processes.show_logs
        show(f"Installing {url}", process)


def install_bun():
    """Install bun onto the user's system.

    Raises:
        SystemPackageMissingError: If "unzip" is missing.
    """
    one_drive_in_path = windows_check_onedrive_in_path()
    if constants.IS_WINDOWS and one_drive_in_path:
        console.warn(
            "Creating project directories in OneDrive is not recommended for bun usage on windows. This will fallback to npm."
        )

    bun_path = path_ops.get_bun_path()

    # Skip if bun is already installed.
    if (
        bun_path
        and (current_version := get_bun_version(bun_path=bun_path))
        and current_version >= version.parse(constants.Bun.MIN_VERSION)
    ):
        console.debug("Skipping bun installation as it is already installed.")
        return

    if bun_path and path_ops.use_system_bun():
        validate_bun(bun_path=bun_path)
        return

    #  if unzip is installed
    if constants.IS_WINDOWS:
        processes.new_process(
            [
                "powershell",
                "-c",
                f"irm {constants.Bun.WINDOWS_INSTALL_URL}|iex",
            ],
            env={
                "BUN_INSTALL": str(constants.Bun.ROOT_PATH),
                "BUN_VERSION": constants.Bun.VERSION,
            },
            shell=True,
            run=True,
            show_logs=console.is_debug(),
        )
    else:
        if path_ops.which("unzip") is None:
            msg = "unzip"
            raise SystemPackageMissingError(msg)

        # Run the bun install script.
        download_and_run(
            constants.Bun.INSTALL_URL,
            f"bun-v{constants.Bun.VERSION}",
            BUN_INSTALL=str(constants.Bun.ROOT_PATH),
            BUN_VERSION=str(constants.Bun.VERSION),
        )


def _write_cached_procedure_file(payload: str, cache_file: str | Path):
    cache_file = Path(cache_file)
    cache_file.write_text(payload)


def _read_cached_procedure_file(cache_file: str | Path) -> str | None:
    cache_file = Path(cache_file)
    if cache_file.exists():
        return cache_file.read_text()
    return None


def _clear_cached_procedure_file(cache_file: str | Path):
    cache_file = Path(cache_file)
    if cache_file.exists():
        cache_file.unlink()


def cached_procedure(
    cache_file: str | None,
    payload_fn: Callable[..., str],
    cache_file_fn: Callable[[], str] | None = None,
):
    """Decorator to cache the runs of a procedure on disk. Procedures should not have
       a return value.

    Args:
        cache_file: The file to store the cache payload in.
        payload_fn: Function that computes cache payload from function args.
        cache_file_fn: Function that computes the cache file name at runtime.

    Returns:
        The decorated function.

    Raises:
        ValueError: If both cache_file and cache_file_fn are provided.
    """
    if cache_file and cache_file_fn is not None:
        msg = "cache_file and cache_file_fn cannot both be provided."
        raise ValueError(msg)

    def _inner_decorator(func: Callable):
        def _inner(*args, **kwargs):
            _cache_file = cache_file_fn() if cache_file_fn is not None else cache_file
            if not _cache_file:
                msg = "Unknown cache file, cannot cache result."
                raise ValueError(msg)
            payload = _read_cached_procedure_file(_cache_file)
            new_payload = payload_fn(*args, **kwargs)
            if payload != new_payload:
                _clear_cached_procedure_file(_cache_file)
                func(*args, **kwargs)
                _write_cached_procedure_file(new_payload, _cache_file)

        return _inner

    return _inner_decorator


@cached_procedure(
    cache_file_fn=lambda: str(
        get_web_dir() / "reflex.install_frontend_packages.cached"
    ),
    payload_fn=lambda p, c: f"{sorted(p)!r},{c.json()}",
    cache_file=None,
)
def install_frontend_packages(packages: set[str], config: Config):
    """Installs the base and custom frontend packages.

    Args:
        packages: A list of package names to be installed.
        config: The config object.

    Example:
        >>> install_frontend_packages(["react", "react-dom"], get_config())
    """
    install_package_managers = get_nodejs_compatible_package_managers(
        raise_on_none=True
    )

    env = (
        {
            "NODE_TLS_REJECT_UNAUTHORIZED": "0",
        }
        if environment.SSL_NO_VERIFY.get()
        else {}
    )

    primary_package_manager = install_package_managers[0]
    fallbacks = install_package_managers[1:]

    run_package_manager = functools.partial(
        processes.run_process_with_fallbacks,
        fallbacks=fallbacks,
        analytics_enabled=True,
        cwd=get_web_dir(),
        shell=constants.IS_WINDOWS,
        env=env,
    )

    run_package_manager(
        [primary_package_manager, "install", "--legacy-peer-deps"],
        show_status_message="Installing base frontend packages",
    )

    development_deps: set[str] = set()
    for plugin in config.plugins:
        development_deps.update(plugin.get_frontend_development_dependencies())
        packages.update(plugin.get_frontend_dependencies())

    if development_deps:
        run_package_manager(
            [
                primary_package_manager,
                "add",
                "--legacy-peer-deps",
                "-d",
                *development_deps,
            ],
            show_status_message="Installing frontend development dependencies",
        )

    # Install custom packages defined in frontend_packages
    if packages:
        run_package_manager(
            [primary_package_manager, "add", "--legacy-peer-deps", *packages],
            show_status_message="Installing frontend packages from config and components",
        )


def check_running_mode(frontend: bool, backend: bool) -> tuple[bool, bool]:
    """Check if the app is running in frontend or backend mode.

    Args:
        frontend: Whether to run the frontend of the app.
        backend: Whether to run the backend of the app.

    Returns:
        The running modes.
    """
    if not frontend and not backend:
        return True, True
    return frontend, backend


def assert_in_reflex_dir():
    """Assert that the current working directory is the reflex directory.

    Raises:
        Exit: If the current working directory is not the reflex directory.
    """
    if not constants.Config.FILE.exists():
        console.error(
            f"[cyan]{constants.Config.FILE}[/cyan] not found. Move to the root folder of your project, or run [bold]{constants.Reflex.MODULE_NAME} init[/bold] to start a new project."
        )
        raise click.exceptions.Exit(1)


def needs_reinit() -> bool:
    """Check if an app needs to be reinitialized.

    Returns:
        Whether the app needs to be reinitialized.
    """
    # Make sure the .reflex directory exists.
    if not environment.REFLEX_DIR.get().exists():
        return True

    # Make sure the .web directory exists in frontend mode.
    if not get_web_dir().exists():
        return True

    # If the template is out of date, then we need to re-init
    if not is_latest_template():
        return True

    if constants.IS_WINDOWS:
        console.warn(
            """Windows Subsystem for Linux (WSL) is recommended for improving initial install times."""
        )

        if windows_check_onedrive_in_path():
            console.warn(
                "Creating project directories in OneDrive may lead to performance issues. For optimal performance, It is recommended to avoid using OneDrive for your reflex app."
            )
    # No need to reinitialize if the app is already initialized.
    return False


def is_latest_template() -> bool:
    """Whether the app is using the latest template.

    Returns:
        Whether the app is using the latest template.
    """
    json_file = get_web_dir() / constants.Reflex.JSON
    if not json_file.exists():
        return False
    app_version = json.loads(json_file.read_text()).get("version")
    return app_version == constants.Reflex.VERSION


def validate_bun(bun_path: Path | None = None):
    """Validate bun if a custom bun path is specified to ensure the bun version meets requirements.

    Args:
        bun_path: The path to the bun executable. If None, the default bun path is used.

    Raises:
        Exit: If custom specified bun does not exist or does not meet requirements.
    """
    bun_path = bun_path or path_ops.get_bun_path()

    if bun_path is None:
        return

    if not path_ops.samefile(bun_path, constants.Bun.DEFAULT_PATH):
        console.info(f"Using custom Bun path: {bun_path}")
        bun_version = get_bun_version()
        if bun_version is None:
            console.error(
                "Failed to obtain bun version. Make sure the specified bun path in your config is correct."
            )
            raise click.exceptions.Exit(1)
        if bun_version < version.parse(constants.Bun.MIN_VERSION):
            console.warn(
                f"Reflex requires bun version {constants.Bun.MIN_VERSION} or higher to run, but the detected version is "
                f"{bun_version}. If you have specified a custom bun path in your config, make sure to provide one "
                f"that satisfies the minimum version requirement. You can upgrade bun by running [bold]bun upgrade[/bold]."
            )


def validate_frontend_dependencies(init: bool = True):
    """Validate frontend dependencies to ensure they meet requirements.

    Args:
        init: whether running `reflex init`

    Raises:
        Exit: If the package manager is invalid.
    """
    if not init:
        try:
            get_js_package_executor(raise_on_none=True)
        except FileNotFoundError as e:
            raise click.exceptions.Exit(1) from e

    if prefer_npm_over_bun() and not check_node_version():
        node_version = get_node_version()
        console.error(
            f"Reflex requires node version {constants.Node.MIN_VERSION} or higher to run, but the detected version is {node_version}",
        )
        raise click.exceptions.Exit(1)


def ensure_reflex_installation_id() -> int | None:
    """Ensures that a reflex distinct id has been generated and stored in the reflex directory.

    Returns:
        Distinct id.
    """
    try:
        console.debug("Ensuring reflex installation id.")
        initialize_reflex_user_directory()
        installation_id_file = environment.REFLEX_DIR.get() / "installation_id"

        installation_id = None
        if installation_id_file.exists():
            with contextlib.suppress(Exception):
                installation_id = int(installation_id_file.read_text())
                # If anything goes wrong at all... just regenerate.
                # Like what? Examples:
                #     - file not exists
                #     - file not readable
                #     - content not parseable as an int

        if installation_id is None:
            installation_id = random.getrandbits(128)
            installation_id_file.write_text(str(installation_id))
    except Exception as e:
        console.debug(f"Failed to ensure reflex installation id: {e}")
        return None
    else:
        # If we get here, installation_id is definitely set
        return installation_id


def initialize_reflex_user_directory():
    """Initialize the reflex user directory."""
    console.debug(f"Creating {environment.REFLEX_DIR.get()}")
    # Create the reflex directory.
    path_ops.mkdir(environment.REFLEX_DIR.get())


def initialize_frontend_dependencies():
    """Initialize all the frontend dependencies."""
    # validate dependencies before install
    console.debug("Validating frontend dependencies.")
    validate_frontend_dependencies()
    # Install the frontend dependencies.
    console.debug("Installing or validating bun.")
    install_bun()
    # Set up the web directory.
    initialize_web_directory()


def check_db_used() -> bool:
    """Check if the database is used.

    Returns:
        True if the database is used.
    """
    return bool(get_config().db_url)


def check_redis_used() -> bool:
    """Check if Redis is used.

    Returns:
        True if Redis is used.
    """
    return bool(get_config().redis_url)


def check_db_initialized() -> bool:
    """Check if the database migrations are initialized.

    Returns:
        True if alembic is initialized (or if database is not used).
    """
    if (
        get_config().db_url is not None
        and not environment.ALEMBIC_CONFIG.get().exists()
    ):
        console.error(
            "Database is not initialized. Run [bold]reflex db init[/bold] first."
        )
        return False
    return True


def check_schema_up_to_date():
    """Check if the sqlmodel metadata matches the current database schema."""
    if get_config().db_url is None or not environment.ALEMBIC_CONFIG.get().exists():
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


def prompt_for_template_options(templates: list[Template]) -> str:
    """Prompt the user to specify a template.

    Args:
        templates: The templates to choose from.

    Returns:
        The template name the user selects.

    Raises:
        Exit: If the user does not select a template.
    """
    # Show the user the URLs of each template to preview.
    console.print("\nGet started with a template:")

    # Prompt the user to select a template.
    for index, template in enumerate(templates):
        console.print(f"({index}) {template.description}")

    template = console.ask(
        "Which template would you like to use?",
        choices=[str(i) for i in range(len(templates))],
        show_choices=False,
        default="0",
    )

    if not template:
        console.error("No template selected.")
        raise click.exceptions.Exit(1)

    try:
        template_index = int(template)
    except ValueError:
        console.error("Invalid template selected.")
        raise click.exceptions.Exit(1) from None

    if template_index < 0 or template_index >= len(templates):
        console.error("Invalid template selected.")
        raise click.exceptions.Exit(1)

    # Return the template.
    return templates[template_index].name


def fetch_app_templates(version: str) -> dict[str, Template]:
    """Fetch a dict of templates from the templates repo using github API.

    Args:
        version: The version of the templates to fetch.

    Returns:
        The dict of templates.
    """

    def get_release_by_tag(tag: str) -> dict | None:
        response = net.get(constants.Reflex.RELEASES_URL)
        response.raise_for_status()
        releases = response.json()
        for release in releases:
            if release["tag_name"] == f"v{tag}":
                return release
        return None

    release = get_release_by_tag(version)
    if release is None:
        console.warn(f"No templates known for version {version}")
        return {}

    assets = release.get("assets", [])
    asset = next((a for a in assets if a["name"] == "templates.json"), None)
    if asset is None:
        console.warn(f"Templates metadata not found for version {version}")
        return {}
    templates_url = asset["browser_download_url"]

    templates_data = net.get(templates_url, follow_redirects=True).json()["templates"]

    for template in templates_data:
        if template["name"] == "blank":
            template["code_url"] = ""
            continue
        template["code_url"] = next(
            (
                a["browser_download_url"]
                for a in assets
                if a["name"] == f"{template['name']}.zip"
            ),
            None,
        )

    filtered_templates = {}
    for tp in templates_data:
        if tp["hidden"] or tp["code_url"] is None:
            continue
        known_fields = {f.name for f in dataclasses.fields(Template)}
        filtered_templates[tp["name"]] = Template(
            **{k: v for k, v in tp.items() if k in known_fields}
        )
    return filtered_templates


def create_config_init_app_from_remote_template(app_name: str, template_url: str):
    """Create new rxconfig and initialize app using a remote template.

    Args:
        app_name: The name of the app.
        template_url: The path to the template source code as a zip file.

    Raises:
        Exit: If any download, file operations fail or unexpected zip file format.

    """
    # Create a temp directory for the zip download.
    try:
        temp_dir = tempfile.mkdtemp()
    except OSError as ose:
        console.error(f"Failed to create temp directory for download: {ose}")
        raise click.exceptions.Exit(1) from ose

    # Use httpx GET with redirects to download the zip file.
    zip_file_path: Path = Path(temp_dir) / "template.zip"
    try:
        # Note: following redirects can be risky. We only allow this for reflex built templates at the moment.
        response = net.get(template_url, follow_redirects=True)
        console.debug(f"Server responded download request: {response}")
        response.raise_for_status()
    except httpx.HTTPError as he:
        console.error(f"Failed to download the template: {he}")
        raise click.exceptions.Exit(1) from he
    try:
        zip_file_path.write_bytes(response.content)
        console.debug(f"Downloaded the zip to {zip_file_path}")
    except OSError as ose:
        console.error(f"Unable to write the downloaded zip to disk {ose}")
        raise click.exceptions.Exit(1) from ose

    # Create a temp directory for the zip extraction.
    try:
        unzip_dir = Path(tempfile.mkdtemp())
    except OSError as ose:
        console.error(f"Failed to create temp directory for extracting zip: {ose}")
        raise click.exceptions.Exit(1) from ose

    try:
        zipfile.ZipFile(zip_file_path).extractall(path=unzip_dir)
        # The zip file downloaded from github looks like:
        # repo-name-branch/**/*, so we need to remove the top level directory.
    except Exception as uze:
        console.error(f"Failed to unzip the template: {uze}")
        raise click.exceptions.Exit(1) from uze

    if len(subdirs := list(unzip_dir.iterdir())) != 1:
        console.error(f"Expected one directory in the zip, found {subdirs}")
        raise click.exceptions.Exit(1)

    template_dir = unzip_dir / subdirs[0]
    console.debug(f"Template folder is located at {template_dir}")

    # Move the rxconfig file here first.
    path_ops.mv(str(template_dir / constants.Config.FILE), constants.Config.FILE)
    new_config = get_config(reload=True)

    # Get the template app's name from rxconfig in case it is different than
    # the source code repo name on github.
    template_name = new_config.app_name

    create_config(app_name)
    initialize_app_directory(
        app_name,
        template_name=template_name,
        template_code_dir_name=template_name,
        template_dir=template_dir,
    )
    req_file = Path("requirements.txt")
    if req_file.exists() and len(req_file.read_text().splitlines()) > 1:
        console.info(
            "Run `pip install -r requirements.txt` to install the required python packages for this template."
        )
    #  Clean up the temp directories.
    shutil.rmtree(temp_dir)
    shutil.rmtree(unzip_dir)


def initialize_default_app(app_name: str):
    """Initialize the default app.

    Args:
        app_name: The name of the app.
    """
    create_config(app_name)
    initialize_app_directory(app_name)


def validate_and_create_app_using_remote_template(
    app_name: str, template: str, templates: dict[str, Template]
):
    """Validate and create an app using a remote template.

    Args:
        app_name: The name of the app.
        template: The name of the template.
        templates: The available templates.

    Raises:
        Exit: If the template is not found.
    """
    # If user selects a template, it needs to exist.
    if template in templates:
        from reflex_cli.v2.utils import hosting

        authenticated_token = hosting.authenticated_token()
        if not authenticated_token or not authenticated_token[0]:
            console.print(
                f"Please use `reflex login` to access the '{template}' template."
            )
            raise click.exceptions.Exit(3)

        template_url = templates[template].code_url
    else:
        template_parsed_url = urlparse(template)
        # Check if the template is a github repo.
        if template_parsed_url.hostname == "github.com":
            path = template_parsed_url.path.strip("/").removesuffix(".git")
            template_url = f"https://github.com/{path}/archive/main.zip"
        else:
            console.error(f"Template `{template}` not found or invalid.")
            raise click.exceptions.Exit(1)

    if template_url is None:
        return

    create_config_init_app_from_remote_template(
        app_name=app_name, template_url=template_url
    )


def fetch_remote_templates(
    template: str,
) -> tuple[str, dict[str, Template]]:
    """Fetch the available remote templates.

    Args:
        template: The name of the template.

    Returns:
        The selected template and the available templates.
    """
    available_templates = {}

    try:
        # Get the available templates
        available_templates = fetch_app_templates(constants.Reflex.VERSION)
    except Exception as e:
        console.warn("Failed to fetch templates. Falling back to default template.")
        console.debug(f"Error while fetching templates: {e}")
        template = constants.Templates.DEFAULT

    return template, available_templates


def initialize_app(app_name: str, template: str | None = None) -> str | None:
    """Initialize the app either from a remote template or a blank app. If the config file exists, it is considered as reinit.

    Args:
        app_name: The name of the app.
        template: The name of the template to use.

    Returns:
        The name of the template.

    Raises:
        Exit: If the template is not valid or unspecified.
    """
    # Local imports to avoid circular imports.
    from reflex.utils import telemetry

    # Check if the app is already initialized.
    if constants.Config.FILE.exists():
        telemetry.send("reinit")
        return None

    templates: dict[str, Template] = {}

    # Don't fetch app templates if the user directly asked for DEFAULT.
    if template is not None and (template not in (constants.Templates.DEFAULT,)):
        template, templates = fetch_remote_templates(template)

    if template is None:
        template = prompt_for_template_options(get_init_cli_prompt_options())

        if template == constants.Templates.CHOOSE_TEMPLATES:
            redir.reflex_templates()
            raise click.exceptions.Exit(0)

    if template == constants.Templates.AI:
        redir.reflex_build_redirect()
        raise click.exceptions.Exit(0)

    # If the blank template is selected, create a blank app.
    if template == constants.Templates.DEFAULT:
        # Default app creation behavior: a blank app.
        initialize_default_app(app_name)
    else:
        validate_and_create_app_using_remote_template(
            app_name=app_name, template=template, templates=templates
        )

    telemetry.send("init", template=template)

    return template


def get_init_cli_prompt_options() -> list[Template]:
    """Get the CLI options for initializing a Reflex app.

    Returns:
        The CLI options.
    """
    return [
        Template(
            name=constants.Templates.DEFAULT,
            description="A blank Reflex app.",
            code_url="",
        ),
        Template(
            name=constants.Templates.AI,
            description="[bold]Try our free AI builder.",
            code_url="",
        ),
        Template(
            name=constants.Templates.CHOOSE_TEMPLATES,
            description="Premade templates built by the Reflex team.",
            code_url="",
        ),
    ]


def format_address_width(address_width: str | None) -> int | None:
    """Cast address width to an int.

    Args:
        address_width: The address width.

    Returns:
        Address width int
    """
    try:
        return int(address_width) if address_width else None
    except ValueError:
        return None


def _retrieve_cpu_info() -> CpuInfo | None:
    """Retrieve the CPU info of the host.

    Returns:
        The CPU info.
    """
    platform_os = platform.system()
    cpuinfo = {}
    try:
        if platform_os == "Windows":
            cmd = 'powershell -Command "Get-CimInstance Win32_Processor | Select-Object -First 1 | Select-Object AddressWidth,Manufacturer,Name | ConvertTo-Json"'
            output = processes.execute_command_and_return_output(cmd)
            if output:
                cpu_data = json.loads(output)
                cpuinfo["address_width"] = cpu_data["AddressWidth"]
                cpuinfo["manufacturer_id"] = cpu_data["Manufacturer"]
                cpuinfo["model_name"] = cpu_data["Name"]
        elif platform_os == "Linux":
            output = processes.execute_command_and_return_output("lscpu")
            if output:
                lines = output.split("\n")
                for line in lines:
                    if "Architecture" in line:
                        cpuinfo["address_width"] = (
                            64 if line.split(":")[1].strip() == "x86_64" else 32
                        )
                    if "Vendor ID:" in line:
                        cpuinfo["manufacturer_id"] = line.split(":")[1].strip()
                    if "Model name" in line:
                        cpuinfo["model_name"] = line.split(":")[1].strip()
        elif platform_os == "Darwin":
            cpuinfo["address_width"] = format_address_width(
                processes.execute_command_and_return_output("getconf LONG_BIT")
            )
            cpuinfo["manufacturer_id"] = processes.execute_command_and_return_output(
                "sysctl -n machdep.cpu.brand_string"
            )
            cpuinfo["model_name"] = processes.execute_command_and_return_output(
                "uname -m"
            )
    except Exception as err:
        console.error(f"Failed to retrieve CPU info. {err}")
        return None

    return (
        CpuInfo(
            manufacturer_id=cpuinfo.get("manufacturer_id"),
            model_name=cpuinfo.get("model_name"),
            address_width=cpuinfo.get("address_width"),
        )
        if cpuinfo
        else None
    )


@functools.cache
def get_cpu_info() -> CpuInfo | None:
    """Get the CPU info of the underlining host.

    Returns:
        The CPU info.
    """
    cpu_info_file = environment.REFLEX_DIR.get() / "cpu_info.json"
    if cpu_info_file.exists() and (cpu_info := json.loads(cpu_info_file.read_text())):
        return CpuInfo(**cpu_info)
    cpu_info = _retrieve_cpu_info()
    if cpu_info:
        cpu_info_file.parent.mkdir(parents=True, exist_ok=True)
        cpu_info_file.write_text(json.dumps(dataclasses.asdict(cpu_info)))
    return cpu_info


def is_generation_hash(template: str) -> bool:
    """Check if the template looks like a generation hash.

    Args:
        template: The template name.

    Returns:
        True if the template is composed of 32 or more hex characters.
    """
    return re.match(r"^[0-9a-f]{32,}$", template) is not None


def get_user_tier():
    """Get the current user's tier.

    Returns:
        The current user's tier.
    """
    from reflex_cli.v2.utils import hosting

    authenticated_token = hosting.authenticated_token()
    return (
        authenticated_token[1].get("tier", "").lower()
        if authenticated_token[0]
        else "anonymous"
    )
