"""Everything related to fetching or initializing build prerequisites."""

from __future__ import annotations

import glob
import importlib
import inspect
import json
import os
import platform
import random
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from datetime import datetime
from fileinput import FileInput
from pathlib import Path
from types import ModuleType
from typing import Callable, List, Optional

import httpx
import pkg_resources
import typer
from alembic.util.exc import CommandError
from packaging import version
from redis import Redis as RedisSync
from redis.asyncio import Redis

import reflex
from reflex import constants, model
from reflex.base import Base
from reflex.compiler import templates
from reflex.config import Config, get_config
from reflex.utils import console, path_ops, processes
from reflex.utils.format import format_library_name

CURRENTLY_INSTALLING_NODE = False


class Template(Base):
    """A template for a Reflex app."""

    name: str
    description: str
    code_url: str
    demo_url: str


def check_latest_package_version(package_name: str):
    """Check if the latest version of the package is installed.

    Args:
        package_name: The name of the package.
    """
    try:
        # Get the latest version from PyPI
        current_version = pkg_resources.get_distribution(package_name).version
        url = f"https://pypi.org/pypi/{package_name}/json"
        response = httpx.get(url)
        latest_version = response.json()["info"]["version"]
        if (
            version.parse(current_version) < version.parse(latest_version)
            and not get_or_set_last_reflex_version_check_datetime()
        ):
            # only show a warning when the host version is outdated and
            # the last_version_check_datetime is not set in reflex.json
            console.warn(
                f"Your version ({current_version}) of {package_name} is out of date. Upgrade to {latest_version} with 'pip install {package_name} --upgrade'"
            )
    except Exception:
        pass


def get_or_set_last_reflex_version_check_datetime():
    """Get the last time a check was made for the latest reflex version.
    This is typically useful for cases where the host reflex version is
    less than that on Pypi.

    Returns:
        The last version check datetime.
    """
    if not os.path.exists(constants.Reflex.JSON):
        return None
    # Open and read the file
    with open(constants.Reflex.JSON, "r") as file:
        data: dict = json.load(file)
    last_version_check_datetime = data.get("last_version_check_datetime")
    if not last_version_check_datetime:
        data.update({"last_version_check_datetime": str(datetime.now())})
        path_ops.update_json_file(constants.Reflex.JSON, data)
    return last_version_check_datetime


def check_node_version() -> bool:
    """Check the version of Node.js.

    Returns:
        Whether the version of Node.js is valid.
    """
    current_version = get_node_version()
    if current_version:
        # Compare the version numbers
        return (
            current_version >= version.parse(constants.Node.MIN_VERSION)
            if constants.IS_WINDOWS
            else current_version == version.parse(constants.Node.VERSION)
        )
    return False


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
        result = processes.new_process([get_config().bun_path, "-v"], run=True)
        return version.parse(result.stdout)  # type: ignore
    except FileNotFoundError:
        return None
    except version.InvalidVersion as e:
        console.warn(
            f"The detected bun version ({e.args[0]}) is not valid. Defaulting to None."
        )
        return None


def get_install_package_manager() -> str | None:
    """Get the package manager executable for installation.
      Currently, bun is used for installation only.

    Returns:
        The path to the package manager.
    """
    if constants.IS_WINDOWS and not constants.IS_WINDOWS_BUN_SUPPORTED_MACHINE:
        return get_package_manager()
    return get_config().bun_path


def get_package_manager() -> str | None:
    """Get the package manager executable for running app.
      Currently on unix systems, npm is used for running the app only.

    Returns:
        The path to the package manager.
    """
    npm_path = path_ops.get_npm_path()
    if npm_path is not None:
        npm_path = str(Path(npm_path).resolve())
    return npm_path


def get_app(reload: bool = False) -> ModuleType:
    """Get the app module based on the default config.

    Args:
        reload: Re-import the app module from disk

    Returns:
        The app based on the default config.

    Raises:
        RuntimeError: If the app name is not set in the config.
    """
    os.environ[constants.RELOAD_CONFIG] = str(reload)
    config = get_config()
    if not config.app_name:
        raise RuntimeError(
            "Cannot get the app module because `app_name` is not set in rxconfig! "
            "If this error occurs in a reflex test case, ensure that `get_app` is mocked."
        )
    module = config.module
    sys.path.insert(0, os.getcwd())
    app = __import__(module, fromlist=(constants.CompileVars.APP,))

    if reload:
        from reflex.state import reload_state_module

        # Reset rx.State subclasses to avoid conflict when reloading.
        reload_state_module(module=module)

        # Reload the app module.
        importlib.reload(app)

    return app


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
    # For py3.8 and py3.9 compatibility when redis is used, we MUST add any decorator pages
    # before compiling the app in a thread to avoid event loop error (REF-2172).
    app._apply_decorated_pages()
    app.compile_(export=export)
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
        If redis-py syntax, return the URL as it is. Otherwise, return the host/port/db as a dict.
    """
    config = get_config()
    if not config.redis_url:
        return None
    if config.redis_url.startswith(("redis://", "rediss://", "unix://")):
        return config.redis_url
    console.deprecate(
        feature_name="host[:port] style redis urls",
        reason="redis-py url syntax is now being used",
        deprecation_version="0.3.6",
        removal_version="0.5.0",
    )
    redis_url, has_port, redis_port = config.redis_url.partition(":")
    if not has_port:
        redis_port = 6379
    console.info(f"Using redis at {config.redis_url}")
    return dict(host=redis_url, port=int(redis_port), db=0)


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
    app_name = (
        app_name if app_name else os.getcwd().split(os.path.sep)[-1].replace("-", "_")
    )
    # Make sure the app is not named "reflex".
    if app_name == constants.Reflex.MODULE_NAME:
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
    with open(constants.Config.FILE, "w") as f:
        console.debug(f"Creating {constants.Config.FILE}")
        f.write(templates.RXCONFIG.render(app_name=app_name, config_name=config_name))


def initialize_gitignore(
    gitignore_file: str = constants.GitIgnore.FILE,
    files_to_ignore: set[str] = constants.GitIgnore.DEFAULTS,
):
    """Initialize the template .gitignore file.

    Args:
        gitignore_file: The .gitignore file to create.
        files_to_ignore: The files to add to the .gitignore file.
    """
    # Combine with the current ignored files.
    if os.path.exists(gitignore_file):
        with open(gitignore_file, "r") as f:
            files_to_ignore |= set([line.strip() for line in f.readlines()])

    # Write files to the .gitignore file.
    with open(gitignore_file, "w", newline="\n") as f:
        console.debug(f"Creating {gitignore_file}")
        f.write(f"{(path_ops.join(sorted(files_to_ignore))).lstrip()}")


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
        with open(fp, "r", encoding=encoding) as f:
            for req in f.readlines():
                # Check if we have a package name that is reflex
                if re.match(r"^reflex[^a-zA-Z0-9]", req):
                    console.debug(f"{fp} already has reflex as dependency.")
                    return
                other_requirements_exist = True
        with open(fp, "a", encoding=encoding) as f:
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
        os.path.join(app_name, template_name + constants.Ext.PY),
        os.path.join(app_name, app_name + constants.Ext.PY),
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
    if not os.path.exists(constants.Reflex.JSON) and not raise_on_fail:
        return None
    # Open and read the file
    with open(constants.Reflex.JSON, "r") as file:
        data = json.load(file)
        return data.get("project_hash")


def initialize_web_directory():
    """Initialize the web directory on reflex init."""
    console.log("Initializing the web directory.")

    # Re-use the hash if one is already created, so we don't over-write it when running reflex init
    project_hash = get_project_hash()

    path_ops.cp(constants.Templates.Dirs.WEB_TEMPLATE, constants.Dirs.WEB)

    initialize_package_json()

    path_ops.mkdir(constants.Dirs.WEB_ASSETS)

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
    output_path = constants.PackageJson.PATH
    code = _compile_package_json()
    with open(output_path, "w") as file:
        file.write(code)


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
    path_ops.update_json_file(constants.Reflex.JSON, reflex_json)


def update_next_config(export=False, transpile_packages: Optional[List[str]] = None):
    """Update Next.js config from Reflex config.

    Args:
        export: if the method run during reflex export.
        transpile_packages: list of packages to transpile via next.config.js.
    """
    next_config_file = Path(constants.Dirs.WEB, constants.Next.CONFIG_FILE)

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
        "reactStrictMode": True,
        "trailingSlash": True,
    }
    if transpile_packages:
        next_config["transpilePackages"] = list(
            set((format_library_name(p) for p in transpile_packages))
        )
    if export:
        next_config["output"] = "export"
        next_config["distDir"] = constants.Dirs.STATIC

    next_config_json = re.sub(r'"([^"]+)"(?=:)', r"\1", json.dumps(next_config))
    return f"module.exports = {next_config_json};"


def remove_existing_bun_installation():
    """Remove existing bun installation."""
    console.debug("Removing existing bun installation.")
    if os.path.exists(get_config().bun_path):
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


def download_and_extract_fnm_zip():
    """Download and run a script.

    Raises:
        Exit: If an error occurs while downloading or extracting the FNM zip.
    """
    # Download the zip file
    url = constants.Fnm.INSTALL_URL
    console.debug(f"Downloading {url}")
    fnm_zip_file = os.path.join(constants.Fnm.DIR, f"{constants.Fnm.FILENAME}.zip")
    # Function to download and extract the FNM zip release.
    try:
        # Download the FNM zip release.
        # TODO: show progress to improve UX
        with httpx.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()
            with open(fnm_zip_file, "wb") as output_file:
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
    if not os.path.exists(constants.Fnm.EXE):
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
        os.chmod(constants.Fnm.EXE, stat.S_IXUSR)
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
    """Install bun onto the user's system.

    Raises:
        FileNotFoundError: If required packages are not found.
    """
    if constants.IS_WINDOWS and not constants.IS_WINDOWS_BUN_SUPPORTED_MACHINE:
        console.warn(
            "Bun for Windows is currently only available for x86 64-bit Windows. Installation will fall back on npm."
        )

    # Skip if bun is already installed.
    if os.path.exists(get_config().bun_path) and get_bun_version() == version.parse(
        constants.Bun.VERSION
    ):
        console.debug("Skipping bun installation as it is already installed.")
        return

    #  if unzip is installed
    if constants.IS_WINDOWS:
        processes.new_process(
            ["powershell", "-c", f"irm {constants.Bun.INSTALL_URL}.ps1|iex"],
            env={"BUN_INSTALL": constants.Bun.ROOT_PATH},
            shell=True,
            run=True,
            show_logs=console.is_debug(),
        )
    else:
        unzip_path = path_ops.which("unzip")
        if unzip_path is None:
            raise FileNotFoundError("Reflex requires unzip to be installed.")

        # Run the bun install script.
        download_and_run(
            constants.Bun.INSTALL_URL,
            f"bun-v{constants.Bun.VERSION}",
            BUN_INSTALL=constants.Bun.ROOT_PATH,
        )


def _write_cached_procedure_file(payload: str, cache_file: str):
    with open(cache_file, "w") as f:
        f.write(payload)


def _read_cached_procedure_file(cache_file: str) -> str | None:
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return f.read()
    return None


def _clear_cached_procedure_file(cache_file: str):
    if os.path.exists(cache_file):
        os.remove(cache_file)


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
    cache_file=os.path.join(
        constants.Dirs.WEB, "reflex.install_frontend_packages.cached"
    ),
    payload_fn=lambda p, c: f"{repr(sorted(list(p)))},{c.json()}",
)
def install_frontend_packages(packages: set[str], config: Config):
    """Installs the base and custom frontend packages.

    Args:
        packages: A list of package names to be installed.
        config: The config object.

    Example:
        >>> install_frontend_packages(["react", "react-dom"], get_config())
    """
    # unsupported archs will use npm anyway. so we dont have to run npm twice
    fallback_command = (
        get_package_manager()
        if constants.IS_WINDOWS and constants.IS_WINDOWS_BUN_SUPPORTED_MACHINE
        else None
    )
    processes.run_process_with_fallback(
        [get_install_package_manager(), "install", "--loglevel", "silly"],
        fallback=fallback_command,
        show_status_message="Installing base frontend packages",
        cwd=constants.Dirs.WEB,
        shell=constants.IS_WINDOWS,
    )

    if config.tailwind is not None:
        processes.run_process_with_fallback(
            [
                get_install_package_manager(),
                "add",
                "-d",
                constants.Tailwind.VERSION,
                *((config.tailwind or {}).get("plugins", [])),
            ],
            fallback=fallback_command,
            show_status_message="Installing tailwind",
            cwd=constants.Dirs.WEB,
            shell=constants.IS_WINDOWS,
        )

    # Install custom packages defined in frontend_packages
    if len(packages) > 0:
        processes.run_process_with_fallback(
            [get_install_package_manager(), "add", *packages],
            fallback=fallback_command,
            show_status_message="Installing frontend packages from config and components",
            cwd=constants.Dirs.WEB,
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
    if not os.path.exists(constants.Config.FILE):
        console.error(
            f"[cyan]{constants.Config.FILE}[/cyan] not found. Move to the root folder of your project, or run [bold]{constants.Reflex.MODULE_NAME} init[/bold] to start a new project."
        )
        raise typer.Exit(1)

    # Don't need to reinit if not running in frontend mode.
    if not frontend:
        return False

    # Make sure the .reflex directory exists.
    if not os.path.exists(constants.Reflex.DIR):
        return True

    # Make sure the .web directory exists in frontend mode.
    if not os.path.exists(constants.Dirs.WEB):
        return True

    if constants.IS_WINDOWS:
        console.warn(
            """Windows Subsystem for Linux (WSL) is recommended for improving initial install times."""
        )
    # No need to reinitialize if the app is already initialized.
    return False


def is_latest_template() -> bool:
    """Whether the app is using the latest template.

    Returns:
        Whether the app is using the latest template.
    """
    if not os.path.exists(constants.Reflex.JSON):
        return False
    with open(constants.Reflex.JSON) as f:  # type: ignore
        app_version = json.load(f)["version"]
    return app_version == constants.Reflex.VERSION


def validate_bun():
    """Validate bun if a custom bun path is specified to ensure the bun version meets requirements.

    Raises:
        Exit: If custom specified bun does not exist or does not meet requirements.
    """
    # if a custom bun path is provided, make sure its valid
    # This is specific to non-FHS OS
    bun_path = get_config().bun_path
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
        installation_id_file = os.path.join(constants.Reflex.DIR, "installation_id")

        installation_id = None
        if os.path.exists(installation_id_file):
            try:
                with open(installation_id_file, "r") as f:
                    installation_id = int(f.read())
            except Exception:
                # If anything goes wrong at all... just regenerate.
                # Like what? Examples:
                #     - file not exists
                #     - file not readable
                #     - content not parseable as an int
                pass

        if installation_id is None:
            installation_id = random.getrandbits(128)
            with open(installation_id_file, "w") as f:
                f.write(str(installation_id))
        # If we get here, installation_id is definitely set
        return installation_id
    except Exception as e:
        console.debug(f"Failed to ensure reflex installation id: {e}")
        return None


def initialize_reflex_user_directory():
    """Initialize the reflex user directory."""
    # Create the reflex directory.
    path_ops.mkdir(constants.Reflex.DIR)


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


def prompt_for_template(templates: list[Template]) -> str:
    """Prompt the user to specify a template.

    Args:
        templates: The templates to choose from.

    Returns:
        The template name the user selects.
    """
    # Show the user the URLs of each template to preview.
    console.print("\nGet started with a template:")

    # Prompt the user to select a template.
    id_to_name = {
        str(idx): f"{template.name} ({template.demo_url}) - {template.description}"
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


def should_show_rx_chakra_migration_instructions() -> bool:
    """Should we show the migration instructions for rx.chakra.* => rx.*?.

    Returns:
        bool: True if we should show the migration instructions.
    """
    if os.getenv("REFLEX_PROMPT_MIGRATE_TO_RX_CHAKRA") == "yes":
        return True

    if not Path(constants.Config.FILE).exists():
        # They are running reflex init for the first time.
        return False

    existing_init_reflex_version = None
    reflex_json = Path(constants.Dirs.REFLEX_JSON)
    if reflex_json.exists():
        with reflex_json.open("r") as f:
            data = json.load(f)
        existing_init_reflex_version = data.get("version", None)

    if existing_init_reflex_version is None:
        # They clone a reflex app from git for the first time.
        # That app may or may not be 0.4 compatible.
        # So let's just show these instructions THIS TIME.
        return True

    if constants.Reflex.VERSION < "0.4":
        return False
    else:
        return existing_init_reflex_version < "0.4"


def show_rx_chakra_migration_instructions():
    """Show the migration instructions for rx.chakra.* => rx.*."""
    console.log(
        "Prior to reflex 0.4.0, rx.* components are based on Chakra UI. They are now based on Radix UI. To stick to Chakra UI, use rx.chakra.*."
    )
    console.log("")
    console.log(
        "[bold]Run `reflex script keep-chakra` to automatically update your app."
    )
    console.log("")
    console.log(
        "For more details, please see https://reflex.dev/blog/2024-02-16-reflex-v0.4.0/"
    )


def migrate_to_rx_chakra():
    """Migrate rx.button => r.chakra.button, etc."""
    file_pattern = os.path.join(get_config().app_name, "**/*.py")
    file_list = glob.glob(file_pattern, recursive=True)

    # Populate with all rx.<x> components that have been moved to rx.chakra.<x>
    patterns = {
        rf"\brx\.{name}\b": f"rx.chakra.{name}"
        for name in _get_rx_chakra_component_to_migrate()
    }

    for file_path in file_list:
        with FileInput(file_path, inplace=True) as file:
            for _line_num, line in enumerate(file):
                for old, new in patterns.items():
                    line = re.sub(old, new, line)
                print(line, end="")


def _get_rx_chakra_component_to_migrate() -> set[str]:
    from reflex.components.chakra import ChakraComponent

    rx_chakra_names = set(dir(reflex.chakra))

    names_to_migrate = set()

    # whitelist names will always be rewritten as rx.chakra.<x>
    whitelist = {
        "ColorModeIcon",
        "MultiSelect",
        "MultiSelectOption",
        "color_mode_icon",
        "multi_select",
        "multi_select_option",
    }

    for rx_chakra_name in sorted(rx_chakra_names):
        if rx_chakra_name.startswith("_"):
            continue

        rx_chakra_object = getattr(reflex.chakra, rx_chakra_name)
        try:
            if (
                inspect.ismethod(rx_chakra_object)
                and inspect.isclass(rx_chakra_object.__self__)
                and issubclass(rx_chakra_object.__self__, ChakraComponent)
            ):
                names_to_migrate.add(rx_chakra_name)

            elif inspect.isclass(rx_chakra_object) and issubclass(
                rx_chakra_object, ChakraComponent
            ):
                names_to_migrate.add(rx_chakra_name)
            elif rx_chakra_name in whitelist:
                names_to_migrate.add(rx_chakra_name)

        except Exception:
            raise
    return names_to_migrate


def migrate_to_reflex():
    """Migration from Pynecone to Reflex."""
    # Check if the old config file exists.
    if not os.path.exists(constants.Config.PREVIOUS_FILE):
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
        f"[bold]Renaming {constants.Config.PREVIOUS_FILE} to {constants.Config.FILE}"
    )
    os.rename(constants.Config.PREVIOUS_FILE, constants.Config.FILE)

    # Find all python files in the app directory.
    file_pattern = os.path.join(get_config().app_name, "**/*.py")
    file_list = glob.glob(file_pattern, recursive=True)

    # Add the config file to the list of files to be migrated.
    file_list.append(constants.Config.FILE)

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


def fetch_app_templates() -> dict[str, Template]:
    """Fetch the list of app templates from the Reflex backend server.

    Returns:
        The name and download URL as a dictionary.
    """
    config = get_config()
    if not config.cp_backend_url:
        console.info(
            "Skip fetching App templates. No backend URL is specified in the config."
        )
        return {}
    try:
        response = httpx.get(
            f"{config.cp_backend_url}{constants.Templates.APP_TEMPLATES_ROUTE}"
        )
        response.raise_for_status()
        return {
            template["name"]: Template.parse_obj(template)
            for template in response.json()
        }
    except httpx.HTTPError as ex:
        console.info(f"Failed to fetch app templates: {ex}")
        return {}
    except (TypeError, KeyError, json.JSONDecodeError) as tkje:
        console.info(f"Unable to process server response for app templates: {tkje}")
        return {}


def create_config_init_app_from_remote_template(
    app_name: str,
    template_url: str,
):
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
    zip_file_path = Path(temp_dir) / "template.zip"
    try:
        # Note: following redirects can be risky. We only allow this for reflex built templates at the moment.
        response = httpx.get(template_url, follow_redirects=True)
        console.debug(f"Server responded download request: {response}")
        response.raise_for_status()
    except httpx.HTTPError as he:
        console.error(f"Failed to download the template: {he}")
        raise typer.Exit(1) from he
    try:
        with open(zip_file_path, "wb") as f:
            f.write(response.content)
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

    #  Clean up the temp directories.
    shutil.rmtree(temp_dir)
    shutil.rmtree(unzip_dir)


def initialize_app(app_name: str, template: str | None = None):
    """Initialize the app either from a remote template or a blank app. If the config file exists, it is considered as reinit.

    Args:
        app_name: The name of the app.
        template: The name of the template to use.

    Raises:
        Exit: If template is directly provided in the command flag and is invalid.
    """
    # Local imports to avoid circular imports.
    from reflex.utils import telemetry

    # Check if the app is already initialized.
    if os.path.exists(constants.Config.FILE):
        telemetry.send("reinit")
        return

    # Get the available templates
    templates: dict[str, Template] = fetch_app_templates()

    # Prompt for a template if not provided.
    if template is None and len(templates) > 0:
        template = prompt_for_template(list(templates.values()))
    elif template is None:
        template = constants.Templates.DEFAULT
    assert template is not None

    # If the blank template is selected, create a blank app.
    if template == constants.Templates.DEFAULT:
        # Default app creation behavior: a blank app.
        create_config(app_name)
        initialize_app_directory(app_name)
    else:
        # Fetch App templates from the backend server.
        console.debug(f"Available templates: {templates}")

        # If user selects a template, it needs to exist.
        if template in templates:
            template_url = templates[template].code_url
        else:
            # Check if the template is a github repo.
            if template.startswith("https://github.com"):
                template_url = (
                    f"{template.strip('/').replace('.git', '')}/archive/main.zip"
                )
            else:
                console.error(f"Template `{template}` not found.")
                raise typer.Exit(1)
        create_config_init_app_from_remote_template(
            app_name=app_name,
            template_url=template_url,
        )

    telemetry.send("init")
