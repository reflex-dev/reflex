"""Everything related to fetching or initializing build prerequisites."""

from __future__ import annotations

import contextlib
import dataclasses
import functools
import importlib
import importlib.metadata
import json
import os
import platform
import random
import re
import shutil
import stat
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Callable, List, Optional

import httpx
import typer
from alembic.util.exc import CommandError
from packaging import version
from redis import Redis as RedisSync
from redis import exceptions
from redis.asyncio import Redis

from reflex import constants, model
from reflex.compiler import templates
from reflex.config import Config, environment, get_config
from reflex.utils import console, net, path_ops, processes, redir
from reflex.utils.exceptions import (
    GeneratedCodeHasNoFunctionDefs,
    raise_system_package_missing_error,
)
from reflex.utils.format import format_library_name
from reflex.utils.registry import _get_npm_registry

CURRENTLY_INSTALLING_NODE = False


@dataclasses.dataclass(frozen=True)
class Template:
    """A template for a Reflex app."""

    name: str
    description: str
    code_url: str
    demo_url: str


@dataclasses.dataclass(frozen=True)
class CpuInfo:
    """Model to save cpu info."""

    manufacturer_id: Optional[str]
    model_name: Optional[str]
    address_width: Optional[int]


def get_web_dir() -> Path:
    """Get the working directory for the next.js commands.

    Can be overridden with REFLEX_WEB_WORKDIR.

    Returns:
        The working directory.
    """
    return environment.REFLEX_WEB_WORKDIR.get()


def _python_version_check():
    """Emit deprecation warning for deprecated python versions."""
    # Check for end-of-life python versions.
    if sys.version_info < (3, 10):
        console.deprecate(
            feature_name="Support for Python 3.9 and older",
            reason="please upgrade to Python 3.10 or newer",
            deprecation_version="0.6.0",
            removal_version="0.7.0",
        )


def check_latest_package_version(package_name: str):
    """Check if the latest version of the package is installed.

    Args:
        package_name: The name of the package.
    """
    if environment.REFLEX_CHECK_LATEST_VERSION.get() is False:
        return
    try:
        # Get the latest version from PyPI
        current_version = importlib.metadata.version(package_name)
        url = f"https://pypi.org/pypi/{package_name}/json"
        response = net.get(url)
        latest_version = response.json()["info"]["version"]
        if get_or_set_last_reflex_version_check_datetime():
            # Versions were already checked and saved in reflex.json, no need to warn again
            return
        if version.parse(current_version) < version.parse(latest_version):
            # Show a warning when the host version is older than PyPI version
            console.warn(
                f"Your version ({current_version}) of {package_name} is out of date. Upgrade to {latest_version} with 'pip install {package_name} --upgrade'"
            )
        # Check for depreacted python versions
        _python_version_check()
    except Exception:
        pass


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
        return version.parse(result.stdout)  # type: ignore
    except (FileNotFoundError, TypeError):
        return None


def get_fnm_version() -> version.Version | None:
    """Get the version of fnm.

    Returns:
        The version of FNM.
    """
    try:
        result = processes.new_process([constants.Fnm.EXE, "--version"], run=True)
        return version.parse(result.stdout.split(" ")[1])  # type: ignore
    except (FileNotFoundError, TypeError):
        return None
    except version.InvalidVersion as e:
        console.warn(
            f"The detected fnm version ({e.args[0]}) is not valid. Defaulting to None."
        )
        return None


def get_bun_version() -> version.Version | None:
    """Get the version of bun.

    Returns:
        The version of bun.
    """
    try:
        # Run the bun -v command and capture the output
        result = processes.new_process([str(get_config().bun_path), "-v"], run=True)
        return version.parse(result.stdout)  # type: ignore
    except FileNotFoundError:
        return None
    except version.InvalidVersion as e:
        console.warn(
            f"The detected bun version ({e.args[0]}) is not valid. Defaulting to None."
        )
        return None


def get_install_package_manager(on_failure_return_none: bool = False) -> str | None:
    """Get the package manager executable for installation.
      Currently, bun is used for installation only.

    Args:
        on_failure_return_none: Whether to return None on failure.

    Returns:
        The path to the package manager.
    """
    if constants.IS_WINDOWS and (
        not is_windows_bun_supported()
        or windows_check_onedrive_in_path()
        or windows_npm_escape_hatch()
    ):
        return get_package_manager(on_failure_return_none)
    return str(get_config().bun_path)


def get_package_manager(on_failure_return_none: bool = False) -> str | None:
    """Get the package manager executable for running app.
      Currently on unix systems, npm is used for running the app only.

    Args:
        on_failure_return_none: Whether to return None on failure.

    Returns:
        The path to the package manager.

    Raises:
        FileNotFoundError: If the package manager is not found.
    """
    npm_path = path_ops.get_npm_path()
    if npm_path is not None:
        return str(Path(npm_path).resolve())
    if on_failure_return_none:
        return None
    raise FileNotFoundError("NPM not found. You may need to run `reflex init`.")


def windows_check_onedrive_in_path() -> bool:
    """For windows, check if oneDrive is present in the project dir path.

    Returns:
        If oneDrive is in the path of the project directory.
    """
    return "onedrive" in str(Path.cwd()).lower()


def windows_npm_escape_hatch() -> bool:
    """For windows, if the user sets REFLEX_USE_NPM, use npm instead of bun.

    Returns:
        If the user has set REFLEX_USE_NPM.
    """
    return environment.REFLEX_USE_NPM.get()


def get_app(reload: bool = False) -> ModuleType:
    """Get the app module based on the default config.

    Args:
        reload: Re-import the app module from disk

    Returns:
        The app based on the default config.

    Raises:
        RuntimeError: If the app name is not set in the config.
    """
    from reflex.utils import telemetry

    try:
        environment.RELOAD_CONFIG.set(reload)
        config = get_config()
        if not config.app_name:
            raise RuntimeError(
                "Cannot get the app module because `app_name` is not set in rxconfig! "
                "If this error occurs in a reflex test case, ensure that `get_app` is mocked."
            )
        module = config.module
        sys.path.insert(0, str(Path.cwd()))
        app = __import__(module, fromlist=(constants.CompileVars.APP,))

        if reload:
            from reflex.state import reload_state_module

            # Reset rx.State subclasses to avoid conflict when reloading.
            reload_state_module(module=module)

            # Reload the app module.
            importlib.reload(app)

        return app
    except Exception as ex:
        telemetry.send_error(ex, context="frontend")
        raise


def get_compiled_app(reload: bool = False, export: bool = False) -> ModuleType:
    """Get the app module based on the default config after first compiling it.

    Args:
        reload: Re-import the app module from disk
        export: Compile the app for export

    Returns:
        The compiled app based on the default config.
    """
    app_module = get_app(reload=reload)
    app = getattr(app_module, constants.CompileVars.APP)
    # For py3.9 compatibility when redis is used, we MUST add any decorator pages
    # before compiling the app in a thread to avoid event loop error (REF-2172).
    app._apply_decorated_pages()
    app._compile(export=export)
    return app_module


def get_redis() -> Redis | None:
    """Get the asynchronous redis client.

    Returns:
        The asynchronous redis client.
    """
    if isinstance((redis_url_or_options := parse_redis_url()), str):
        return Redis.from_url(redis_url_or_options)
    elif isinstance(redis_url_or_options, dict):
        return Redis(**redis_url_or_options)
    return None


def get_redis_sync() -> RedisSync | None:
    """Get the synchronous redis client.

    Returns:
        The synchronous redis client.
    """
    if isinstance((redis_url_or_options := parse_redis_url()), str):
        return RedisSync.from_url(redis_url_or_options)
    elif isinstance(redis_url_or_options, dict):
        return RedisSync(**redis_url_or_options)
    return None


def parse_redis_url() -> str | dict | None:
    """Parse the REDIS_URL in config if applicable.

    Returns:
        If url is non-empty, return the URL as it is.

    Raises:
        ValueError: If the REDIS_URL is not a supported scheme.
    """
    config = get_config()
    if not config.redis_url:
        return None
    if not config.redis_url.startswith(("redis://", "rediss://", "unix://")):
        raise ValueError(
            "REDIS_URL must start with 'redis://', 'rediss://', or 'unix://'."
        )
    return config.redis_url


async def get_redis_status() -> bool | None:
    """Checks the status of the Redis connection.

    Attempts to connect to Redis and send a ping command to verify connectivity.

    Returns:
        bool or None: The status of the Redis connection:
            - True: Redis is accessible and responding.
            - False: Redis is not accessible due to a connection error.
            - None: Redis not used i.e redis_url is not set in rxconfig.
    """
    try:
        status = True
        redis_client = get_redis_sync()
        if redis_client is not None:
            redis_client.ping()
        else:
            status = None
    except exceptions.RedisError:
        status = False

    return status


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
        raise typer.Exit(1)

    # Make sure the app name is standard for a python package name.
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", app_name):
        console.error(
            "The app directory name must start with a letter and can contain letters, numbers, and underscores."
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


def initialize_requirements_txt():
    """Initialize the requirements.txt file.
    If absent, generate one for the user.
    If the requirements.txt does not have reflex as dependency,
    generate a requirement pinning current version and append to
    the requirements.txt file.
    """
    fp = Path(constants.RequirementsTxt.FILE)
    encoding = "utf-8"
    if not fp.exists():
        fp.touch()
    else:
        # Detect the encoding of the original file
        import charset_normalizer

        charset_matches = charset_normalizer.from_path(fp)
        maybe_charset_match = charset_matches.best()
        if maybe_charset_match is None:
            console.debug(f"Unable to detect encoding for {fp}, exiting.")
            return
        encoding = maybe_charset_match.encoding
        console.debug(f"Detected encoding for {fp} as {encoding}.")
    try:
        other_requirements_exist = False
        with fp.open("r", encoding=encoding) as f:
            for req in f:
                # Check if we have a package name that is reflex
                if re.match(r"^reflex[^a-zA-Z0-9]", req):
                    console.debug(f"{fp} already has reflex as dependency.")
                    return
                other_requirements_exist = True
        with fp.open("a", encoding=encoding) as f:
            preceding_newline = "\n" if other_requirements_exist else ""
            f.write(
                f"{preceding_newline}{constants.RequirementsTxt.DEFAULTS_STUB}{constants.Reflex.VERSION}\n"
            )
    except Exception:
        console.info(f"Unable to check {fp} for reflex dependency.")


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
            raise typer.Exit(1)
        template_code_dir_name = constants.Templates.Dirs.CODE
        template_dir = Path(constants.Templates.Dirs.BASE, "apps", template_name)
    else:
        if template_code_dir_name is None or template_dir is None:
            console.error(
                f"For `{template_name}` template, `template_code_dir_name` and `template_dir` should both be provided."
            )
            raise typer.Exit(1)

    console.debug(f"Using {template_name=} {template_dir=} {template_code_dir_name=}.")

    # Remove all pyc and __pycache__ dirs in template directory.
    for pyc_file in template_dir.glob("**/*.pyc"):
        pyc_file.unlink()
    for pycache_dir in template_dir.glob("**/__pycache__"):
        pycache_dir.rmdir()

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

    # Re-use the hash if one is already created, so we don't over-write it when running reflex init
    project_hash = get_project_hash()

    path_ops.cp(constants.Templates.Dirs.WEB_TEMPLATE, str(get_web_dir()))

    initialize_package_json()

    initialize_bun_config()

    path_ops.mkdir(get_web_dir() / constants.Dirs.PUBLIC)

    update_next_config()

    # Initialize the reflex json file.
    init_reflex_json(project_hash=project_hash)


def _compile_package_json():
    return templates.PACKAGE_JSON.render(
        scripts={
            "dev": constants.PackageJson.Commands.DEV,
            "export": constants.PackageJson.Commands.EXPORT,
            "export_sitemap": constants.PackageJson.Commands.EXPORT_SITEMAP,
            "prod": constants.PackageJson.Commands.PROD,
        },
        dependencies=constants.PackageJson.DEPENDENCIES,
        dev_dependencies=constants.PackageJson.DEV_DEPENDENCIES,
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
        best_registry = _get_npm_registry()
        bunfig_content = constants.Bun.DEFAULT_CONFIG.format(registry=best_registry)

    bun_config_path.write_text(bunfig_content)


def init_reflex_json(project_hash: int | None):
    """Write the hash of the Reflex project to a REFLEX_JSON.

    Re-use the hash if one is already created, therefore do not
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


def update_next_config(export=False, transpile_packages: Optional[List[str]] = None):
    """Update Next.js config from Reflex config.

    Args:
        export: if the method run during reflex export.
        transpile_packages: list of packages to transpile via next.config.js.
    """
    next_config_file = get_web_dir() / constants.Next.CONFIG_FILE

    next_config = _update_next_config(
        get_config(), export=export, transpile_packages=transpile_packages
    )

    # Overwriting the next.config.js triggers a full server reload, so make sure
    # there is actually a diff.
    orig_next_config = next_config_file.read_text() if next_config_file.exists() else ""
    if orig_next_config != next_config:
        next_config_file.write_text(next_config)


def _update_next_config(
    config: Config, export: bool = False, transpile_packages: Optional[List[str]] = None
):
    next_config = {
        "basePath": config.frontend_path or "",
        "compress": config.next_compression,
        "reactStrictMode": config.react_strict_mode,
        "trailingSlash": True,
        "staticPageGenerationTimeout": config.static_page_generation_timeout,
    }
    if transpile_packages:
        next_config["transpilePackages"] = list(
            {format_library_name(p) for p in transpile_packages}
        )
    if export:
        next_config["output"] = "export"
        next_config["distDir"] = constants.Dirs.STATIC

    next_config_json = re.sub(r'"([^"]+)"(?=:)', r"\1", json.dumps(next_config))
    return f"module.exports = {next_config_json};"


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
    """
    # Download the script
    console.debug(f"Downloading {url}")
    response = net.get(url)
    if response.status_code != httpx.codes.OK:
        response.raise_for_status()

    # Save the script to a temporary file.
    script = Path(tempfile.NamedTemporaryFile().name)

    script.write_text(response.text)

    # Run the script.
    env = {**os.environ, **env}
    process = processes.new_process(["bash", str(script), *args], env=env)
    show = processes.show_status if show_status else processes.show_logs
    show(f"Installing {url}", process)


def download_and_extract_fnm_zip():
    """Download and run a script.

    Raises:
        Exit: If an error occurs while downloading or extracting the FNM zip.
    """
    # Download the zip file
    url = constants.Fnm.INSTALL_URL
    console.debug(f"Downloading {url}")
    fnm_zip_file: Path = constants.Fnm.DIR / f"{constants.Fnm.FILENAME}.zip"
    # Function to download and extract the FNM zip release.
    try:
        # Download the FNM zip release.
        # TODO: show progress to improve UX
        response = net.get(url, follow_redirects=True)
        response.raise_for_status()
        with fnm_zip_file.open("wb") as output_file:
            for chunk in response.iter_bytes():
                output_file.write(chunk)

        # Extract the downloaded zip file.
        with zipfile.ZipFile(fnm_zip_file, "r") as zip_ref:
            zip_ref.extractall(constants.Fnm.DIR)

        console.debug("FNM package downloaded and extracted successfully.")
    except Exception as e:
        console.error(f"An error occurred while downloading fnm package: {e}")
        raise typer.Exit(1) from e
    finally:
        # Clean up the downloaded zip file.
        path_ops.rm(fnm_zip_file)


def install_node():
    """Install fnm and nodejs for use by Reflex.
    Independent of any existing system installations.
    """
    if not constants.Fnm.FILENAME:
        # fnm only support Linux, macOS and Windows distros.
        console.debug("")
        return

    # Skip installation if check_node_version() checks out
    if check_node_version():
        console.debug("Skipping node installation as it is already installed.")
        return

    path_ops.mkdir(constants.Fnm.DIR)
    if not constants.Fnm.EXE.exists():
        download_and_extract_fnm_zip()

    if constants.IS_WINDOWS:
        # Install node
        fnm_exe = Path(constants.Fnm.EXE).resolve()
        fnm_dir = Path(constants.Fnm.DIR).resolve()
        process = processes.new_process(
            [
                "powershell",
                "-Command",
                f'& "{fnm_exe}" install {constants.Node.VERSION} --fnm-dir "{fnm_dir}"',
            ],
        )
    else:  # All other platforms (Linux, MacOS).
        # Add execute permissions to fnm executable.
        constants.Fnm.EXE.chmod(stat.S_IXUSR)
        # Install node.
        # Specify arm64 arch explicitly for M1s and M2s.
        architecture_arg = (
            ["--arch=arm64"]
            if platform.system() == "Darwin" and platform.machine() == "arm64"
            else []
        )

        process = processes.new_process(
            [
                constants.Fnm.EXE,
                "install",
                *architecture_arg,
                constants.Node.VERSION,
                "--fnm-dir",
                constants.Fnm.DIR,
            ],
        )
    processes.show_status("Installing node", process)


def install_bun():
    """Install bun onto the user's system."""
    win_supported = is_windows_bun_supported()
    one_drive_in_path = windows_check_onedrive_in_path()
    if constants.IS_WINDOWS and (not win_supported or one_drive_in_path):
        if not win_supported:
            console.warn(
                "Bun for Windows is currently only available for x86 64-bit Windows. Installation will fall back on npm."
            )
        if one_drive_in_path:
            console.warn(
                "Creating project directories in OneDrive is not recommended for bun usage on windows. This will fallback to npm."
            )

    # Skip if bun is already installed.
    if Path(get_config().bun_path).exists() and get_bun_version() == version.parse(
        constants.Bun.VERSION
    ):
        console.debug("Skipping bun installation as it is already installed.")
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
        unzip_path = path_ops.which("unzip")
        if unzip_path is None:
            raise_system_package_missing_error("unzip")

        # Run the bun install script.
        download_and_run(
            constants.Bun.INSTALL_URL,
            f"bun-v{constants.Bun.VERSION}",
            BUN_INSTALL=str(constants.Bun.ROOT_PATH),
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


def cached_procedure(cache_file: str, payload_fn: Callable[..., str]):
    """Decorator to cache the runs of a procedure on disk. Procedures should not have
       a return value.

    Args:
        cache_file: The file to store the cache payload in.
        payload_fn: Function that computes cache payload from function args

    Returns:
        The decorated function.
    """

    def _inner_decorator(func):
        def _inner(*args, **kwargs):
            payload = _read_cached_procedure_file(cache_file)
            new_payload = payload_fn(*args, **kwargs)
            if payload != new_payload:
                _clear_cached_procedure_file(cache_file)
                func(*args, **kwargs)
                _write_cached_procedure_file(new_payload, cache_file)

        return _inner

    return _inner_decorator


@cached_procedure(
    cache_file=str(get_web_dir() / "reflex.install_frontend_packages.cached"),
    payload_fn=lambda p, c: f"{sorted(p)!r},{c.json()}",
)
def install_frontend_packages(packages: set[str], config: Config):
    """Installs the base and custom frontend packages.

    Args:
        packages: A list of package names to be installed.
        config: The config object.

    Raises:
        FileNotFoundError: If the package manager is not found.

    Example:
        >>> install_frontend_packages(["react", "react-dom"], get_config())
    """
    # unsupported archs(arm and 32bit machines) will use npm anyway. so we dont have to run npm twice
    fallback_command = (
        get_package_manager(on_failure_return_none=True)
        if (
            not constants.IS_WINDOWS
            or (
                constants.IS_WINDOWS
                and (
                    is_windows_bun_supported() and not windows_check_onedrive_in_path()
                )
            )
        )
        else None
    )

    install_package_manager = (
        get_install_package_manager(on_failure_return_none=True) or fallback_command
    )

    if install_package_manager is None:
        raise FileNotFoundError(
            "Could not find a package manager to install frontend packages. You may need to run `reflex init`."
        )

    fallback_command = (
        fallback_command if fallback_command is not install_package_manager else None
    )

    processes.run_process_with_fallback(
        [install_package_manager, "install"],  # type: ignore
        fallback=fallback_command,
        analytics_enabled=True,
        show_status_message="Installing base frontend packages",
        cwd=get_web_dir(),
        shell=constants.IS_WINDOWS,
    )

    if config.tailwind is not None:
        processes.run_process_with_fallback(
            [
                install_package_manager,
                "add",
                "-d",
                constants.Tailwind.VERSION,
                *((config.tailwind or {}).get("plugins", [])),
            ],
            fallback=fallback_command,
            analytics_enabled=True,
            show_status_message="Installing tailwind",
            cwd=get_web_dir(),
            shell=constants.IS_WINDOWS,
        )

    # Install custom packages defined in frontend_packages
    if len(packages) > 0:
        processes.run_process_with_fallback(
            [install_package_manager, "add", *packages],
            fallback=fallback_command,
            analytics_enabled=True,
            show_status_message="Installing frontend packages from config and components",
            cwd=get_web_dir(),
            shell=constants.IS_WINDOWS,
        )


def needs_reinit(frontend: bool = True) -> bool:
    """Check if an app needs to be reinitialized.

    Args:
        frontend: Whether to check if the frontend is initialized.

    Returns:
        Whether the app needs to be reinitialized.

    Raises:
        Exit: If the app is not initialized.
    """
    if not constants.Config.FILE.exists():
        console.error(
            f"[cyan]{constants.Config.FILE}[/cyan] not found. Move to the root folder of your project, or run [bold]{constants.Reflex.MODULE_NAME} init[/bold] to start a new project."
        )
        raise typer.Exit(1)

    # Don't need to reinit if not running in frontend mode.
    if not frontend:
        return False

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


def validate_bun():
    """Validate bun if a custom bun path is specified to ensure the bun version meets requirements.

    Raises:
        Exit: If custom specified bun does not exist or does not meet requirements.
    """
    # if a custom bun path is provided, make sure its valid
    # This is specific to non-FHS OS
    bun_path = get_config().bun_path
    if path_ops.use_system_bun():
        bun_path = path_ops.which("bun")
    if bun_path != constants.Bun.DEFAULT_PATH:
        console.info(f"Using custom Bun path: {bun_path}")
        bun_version = get_bun_version()
        if not bun_version:
            console.error(
                "Failed to obtain bun version. Make sure the specified bun path in your config is correct."
            )
            raise typer.Exit(1)
        elif bun_version < version.parse(constants.Bun.MIN_VERSION):
            console.error(
                f"Reflex requires bun version {constants.Bun.VERSION} or higher to run, but the detected version is "
                f"{bun_version}. If you have specified a custom bun path in your config, make sure to provide one "
                f"that satisfies the minimum version requirement."
            )

            raise typer.Exit(1)


def validate_frontend_dependencies(init=True):
    """Validate frontend dependencies to ensure they meet requirements.

    Args:
        init: whether running `reflex init`

    Raises:
        Exit: If the package manager is invalid.
    """
    if not init:
        # we only need to validate the package manager when running app.
        # `reflex init` will install the deps anyway(if applied).
        package_manager = get_package_manager()
        if not package_manager:
            console.error(
                "Could not find NPM package manager. Make sure you have node installed."
            )
            raise typer.Exit(1)

        if not check_node_version():
            node_version = get_node_version()
            console.error(
                f"Reflex requires node version {constants.Node.MIN_VERSION} or higher to run, but the detected version is {node_version}",
            )
            raise typer.Exit(1)

    if init:
        # we only need bun for package install on `reflex init`.
        validate_bun()


def ensure_reflex_installation_id() -> Optional[int]:
    """Ensures that a reflex distinct id has been generated and stored in the reflex directory.

    Returns:
        Distinct id.
    """
    try:
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
        # If we get here, installation_id is definitely set
        return installation_id
    except Exception as e:
        console.debug(f"Failed to ensure reflex installation id: {e}")
        return None


def initialize_reflex_user_directory():
    """Initialize the reflex user directory."""
    # Create the reflex directory.
    path_ops.mkdir(environment.REFLEX_DIR.get())


def initialize_frontend_dependencies():
    """Initialize all the frontend dependencies."""
    # validate dependencies before install
    validate_frontend_dependencies()
    # Avoid warning about Node installation while we're trying to install it.
    global CURRENTLY_INSTALLING_NODE
    CURRENTLY_INSTALLING_NODE = True
    # Install the frontend dependencies.
    processes.run_concurrently(install_node, install_bun)
    CURRENTLY_INSTALLING_NODE = False
    # Set up the web directory.
    initialize_web_directory()


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
    """
    # Show the user the URLs of each template to preview.
    console.print("\nGet started with a template:")

    def format_demo_url_str(url: str) -> str:
        return f" ({url})" if url else ""

    # Prompt the user to select a template.
    id_to_name = {
        str(
            idx
        ): f"{template.name.replace('_', ' ').replace('-', ' ')}{format_demo_url_str(template.demo_url)} - {template.description}"
        for idx, template in enumerate(templates)
    }
    for id in range(len(id_to_name)):
        console.print(f"({id}) {id_to_name[str(id)]}")

    template = console.ask(
        "Which template would you like to use?",
        choices=[str(i) for i in range(len(id_to_name))],
        show_choices=False,
        default="0",
    )

    # Return the template.
    return templates[int(template)].name


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
    else:
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
        raise typer.Exit(1) from ose

    # Use httpx GET with redirects to download the zip file.
    zip_file_path: Path = Path(temp_dir) / "template.zip"
    try:
        # Note: following redirects can be risky. We only allow this for reflex built templates at the moment.
        response = net.get(template_url, follow_redirects=True)
        console.debug(f"Server responded download request: {response}")
        response.raise_for_status()
    except httpx.HTTPError as he:
        console.error(f"Failed to download the template: {he}")
        raise typer.Exit(1) from he
    try:
        zip_file_path.write_bytes(response.content)
        console.debug(f"Downloaded the zip to {zip_file_path}")
    except OSError as ose:
        console.error(f"Unable to write the downloaded zip to disk {ose}")
        raise typer.Exit(1) from ose

    # Create a temp directory for the zip extraction.
    try:
        unzip_dir = Path(tempfile.mkdtemp())
    except OSError as ose:
        console.error(f"Failed to create temp directory for extracting zip: {ose}")
        raise typer.Exit(1) from ose
    try:
        zipfile.ZipFile(zip_file_path).extractall(path=unzip_dir)
        # The zip file downloaded from github looks like:
        # repo-name-branch/**/*, so we need to remove the top level directory.
        if len(subdirs := os.listdir(unzip_dir)) != 1:
            console.error(f"Expected one directory in the zip, found {subdirs}")
            raise typer.Exit(1)
        template_dir = unzip_dir / subdirs[0]
        console.debug(f"Template folder is located at {template_dir}")
    except Exception as uze:
        console.error(f"Failed to unzip the template: {uze}")
        raise typer.Exit(1) from uze

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


def validate_and_create_app_using_remote_template(app_name, template, templates):
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
            raise typer.Exit(3)

        template_url = templates[template].code_url
    else:
        # Check if the template is a github repo.
        if template.startswith("https://github.com"):
            template_url = f"{template.strip('/').replace('.git', '')}/archive/main.zip"
        else:
            console.error(f"Template `{template}` not found or invalid.")
            raise typer.Exit(1)

    if template_url is None:
        return

    create_config_init_app_from_remote_template(
        app_name=app_name, template_url=template_url
    )


def generate_template_using_ai(template: str | None = None) -> str:
    """Generate a template using AI(Flexgen).

    Args:
        template: The name of the template.

    Returns:
        The generation hash.

    Raises:
        Exit: If the template and ai flags are used.
    """
    if template is None:
        # If AI is requested and no template specified, redirect the user to reflex.build.
        return redir.reflex_build_redirect()
    elif is_generation_hash(template):
        # Otherwise treat the template as a generation hash.
        return template
    else:
        console.error(
            "Cannot use `--template` option with `--ai` option. Please remove `--template` option."
        )
        raise typer.Exit(2)


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


def initialize_app(
    app_name: str, template: str | None = None, ai: bool = False
) -> str | None:
    """Initialize the app either from a remote template or a blank app. If the config file exists, it is considered as reinit.

    Args:
        app_name: The name of the app.
        template: The name of the template to use.
        ai: Whether to use AI to generate the template.

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
        return

    generation_hash = None
    if ai:
        generation_hash = generate_template_using_ai(template)
        template = constants.Templates.DEFAULT

    templates: dict[str, Template] = {}

    # Don't fetch app templates if the user directly asked for DEFAULT.
    if template is not None and (template not in (constants.Templates.DEFAULT,)):
        template, templates = fetch_remote_templates(template)

    if template is None:
        template = prompt_for_template_options(get_init_cli_prompt_options())
        if template == constants.Templates.AI:
            generation_hash = generate_template_using_ai()
            # change to the default to allow creation of default app
            template = constants.Templates.DEFAULT
        elif template == constants.Templates.CHOOSE_TEMPLATES:
            console.print(
                f"Go to the templates page ({constants.Templates.REFLEX_TEMPLATES_URL}) and copy the command to init with a template."
            )
            raise typer.Exit(0)

    # If the blank template is selected, create a blank app.
    if template in (constants.Templates.DEFAULT,):
        # Default app creation behavior: a blank app.
        initialize_default_app(app_name)
    else:
        validate_and_create_app_using_remote_template(
            app_name=app_name, template=template, templates=templates
        )

    # If a reflex.build generation hash is available, download the code and apply it to the main module.
    if generation_hash:
        initialize_main_module_index_from_generation(
            app_name, generation_hash=generation_hash
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
            demo_url=constants.Templates.DEFAULT_TEMPLATE_URL,
            code_url="",
        ),
        Template(
            name=constants.Templates.AI,
            description="Generate a template using AI [Experimental]",
            demo_url="",
            code_url="",
        ),
        Template(
            name=constants.Templates.CHOOSE_TEMPLATES,
            description="Choose an existing template.",
            demo_url="",
            code_url="",
        ),
    ]


def initialize_main_module_index_from_generation(app_name: str, generation_hash: str):
    """Overwrite the `index` function in the main module with reflex.build generated code.

    Args:
        app_name: The name of the app.
        generation_hash: The generation hash from reflex.build.

    Raises:
        GeneratedCodeHasNoFunctionDefs: If the fetched code has no function definitions
            (the refactored reflex code is expected to have at least one root function defined).
    """
    # Download the reflex code for the generation.
    url = constants.Templates.REFLEX_BUILD_CODE_URL.format(
        generation_hash=generation_hash
    )
    resp = net.get(url)
    while resp.status_code == httpx.codes.SERVICE_UNAVAILABLE:
        console.debug("Waiting for the code to be generated...")
        time.sleep(1)
        resp = net.get(url)
    resp.raise_for_status()

    # Determine the name of the last function, which renders the generated code.
    defined_funcs = re.findall(r"def ([a-zA-Z_]+)\(", resp.text)
    if not defined_funcs:
        raise GeneratedCodeHasNoFunctionDefs(
            f"No function definitions found in generated code from {url!r}."
        )
    render_func_name = defined_funcs[-1]

    def replace_content(_match):
        return "\n".join(
            [
                resp.text,
                "",
                "" "def index() -> rx.Component:",
                f"    return {render_func_name}()",
                "",
                "",
            ],
        )

    main_module_path = Path(app_name, app_name + constants.Ext.PY)
    main_module_code = main_module_path.read_text()

    main_module_code = re.sub(
        r"def index\(\).*:\n([^\n]\s+.*\n+)+",
        replace_content,
        main_module_code,
    )
    # Make the app use light mode until flexgen enforces the conversion of
    # tailwind colors to radix colors.
    main_module_code = re.sub(
        r"app\s*=\s*rx\.App\(\s*\)",
        'app = rx.App(theme=rx.theme(color_mode="light"))',
        main_module_code,
    )
    main_module_path.write_text(main_module_code)


def format_address_width(address_width) -> int | None:
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


@functools.lru_cache(maxsize=None)
def get_cpu_info() -> CpuInfo | None:
    """Get the CPU info of the underlining host.

    Returns:
         The CPU info.
    """
    platform_os = platform.system()
    cpuinfo = {}
    try:
        if platform_os == "Windows":
            cmd = "wmic cpu get addresswidth,caption,manufacturer /FORMAT:csv"
            output = processes.execute_command_and_return_output(cmd)
            if output:
                val = output.splitlines()[-1].split(",")[1:]
                cpuinfo["manufacturer_id"] = val[2]
                cpuinfo["model_name"] = val[1].split("Family")[0].strip()
                cpuinfo["address_width"] = format_address_width(val[0])
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


@functools.lru_cache(maxsize=None)
def is_windows_bun_supported() -> bool:
    """Check whether the underlining host running windows qualifies to run bun.
    We typically do not run bun on ARM or 32 bit devices that use windows.

    Returns:
        Whether the host is qualified to use bun.
    """
    cpu_info = get_cpu_info()
    return (
        constants.IS_WINDOWS
        and cpu_info is not None
        and cpu_info.address_width == 64
        and cpu_info.model_name is not None
        and "ARM" not in cpu_info.model_name
    )


def is_generation_hash(template: str) -> bool:
    """Check if the template looks like a generation hash.

    Args:
        template: The template name.

    Returns:
        True if the template is composed of 32 or more hex characters.
    """
    return re.match(r"^[0-9a-f]{32,}$", template) is not None
