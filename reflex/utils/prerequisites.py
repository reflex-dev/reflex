"""Everything related to fetching or initializing build prerequisites."""

from __future__ import annotations

import contextlib
import importlib
import importlib.metadata
import inspect
import json
import random
import re
import sys
import typing
from datetime import datetime
from os import getcwd
from pathlib import Path
from types import ModuleType
from typing import NamedTuple

from packaging import version

from reflex import constants, model
from reflex.config import Config, get_config
from reflex.environment import environment
from reflex.utils import console, net, path_ops
from reflex.utils.decorator import once
from reflex.utils.misc import get_module_path

if typing.TYPE_CHECKING:
    from redis import Redis as RedisSync
    from redis.asyncio import Redis

    from reflex.app import App


class AppInfo(NamedTuple):
    """A tuple containing the app instance and module."""

    app: App
    module: ModuleType


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


@once
def windows_check_onedrive_in_path() -> bool:
    """For windows, check if oneDrive is present in the project dir path.

    Returns:
        If oneDrive is in the path of the project directory.
    """
    return "onedrive" in str(Path.cwd()).lower()


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

    from reflex.utils.misc import with_cwd_in_syspath

    with with_cwd_in_syspath():
        module_path = get_module_path(config.module)
        if module_path is None:
            msg = f"Module {config.module} not found. "
            if config.app_module_import is not None:
                msg += f"Ensure app_module_import='{config.app_module_import}' in rxconfig.py matches your folder structure."
            else:
                msg += f"Ensure app_name='{config.app_name}' in rxconfig.py matches your folder structure."
            raise ModuleNotFoundError(msg)
    config._app_name_is_valid = True


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

        # Avoid hitting disk when the app name has already been validated in this process.
        if not config._app_name_is_valid:
            _check_app_name(config)

        module = config.module
        sys.path.insert(0, getcwd())  # noqa: PTH109
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


def get_compiled_app(
    reload: bool = False,
    prerender_routes: bool = False,
    dry_run: bool = False,
    check_if_schema_up_to_date: bool = False,
    use_rich: bool = True,
) -> ModuleType:
    """Get the app module based on the default config after first compiling it.

    Args:
        reload: Re-import the app module from disk
        prerender_routes: Whether to prerender routes.
        dry_run: If True, do not write the compiled app to disk.
        check_if_schema_up_to_date: If True, check if the schema is up to date.
        use_rich: Whether to use rich progress bars.

    Returns:
        The compiled app based on the default config.
    """
    app, app_module = get_and_validate_app(
        reload=reload, check_if_schema_up_to_date=check_if_schema_up_to_date
    )
    app._compile(prerender_routes=prerender_routes, dry_run=dry_run, use_rich=use_rich)
    return app_module


def _can_colorize() -> bool:
    """Check if the output can be colorized.

    Copied from _colorize.can_colorize.

    https://raw.githubusercontent.com/python/cpython/refs/heads/main/Lib/_colorize.py

    Returns:
        If the output can be colorized
    """
    import io
    import os

    def _safe_getenv(k: str, fallback: str | None = None) -> str | None:
        """Exception-safe environment retrieval. See gh-128636.

        Args:
            k: The environment variable key.
            fallback: The fallback value if the environment variable is not set.

        Returns:
            The value of the environment variable or the fallback value.
        """
        try:
            return os.environ.get(k, fallback)
        except Exception:
            return fallback

    file = sys.stdout

    if not sys.flags.ignore_environment:
        if _safe_getenv("PYTHON_COLORS") == "0":
            return False
        if _safe_getenv("PYTHON_COLORS") == "1":
            return True
    if _safe_getenv("NO_COLOR"):
        return False
    if _safe_getenv("FORCE_COLOR"):
        return True
    if _safe_getenv("TERM") == "dumb":
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
        return hasattr(file, "isatty") and file.isatty()


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
        True if the app was successfully compiled or validated, False otherwise.
    """
    try:
        if compile:
            get_compiled_app(
                check_if_schema_up_to_date=check_if_schema_up_to_date,
                prerender_routes=prerender_routes,
            )
        else:
            get_and_validate_app(check_if_schema_up_to_date=check_if_schema_up_to_date)
    except Exception as e:
        import traceback

        try:
            colorize = _can_colorize()
            traceback.print_exception(e, colorize=colorize)  # pyright: ignore[reportCallIssue]
        except Exception:
            traceback.print_exception(e)
        return False
    else:
        return True


def get_redis() -> Redis | None:
    """Get the asynchronous redis client.

    Returns:
        The asynchronous redis client.
    """
    try:
        from redis.asyncio import Redis
        from redis.exceptions import RedisError
    except ImportError:
        console.debug("Redis package not installed.")
        return None
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
    try:
        from redis import Redis as RedisSync
        from redis.exceptions import RedisError
    except ImportError:
        console.debug("Redis package not installed.")
        return None
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
    from redis.exceptions import RedisError

    try:
        status = True
        redis_client = get_redis()
        if redis_client is not None:
            ping_command = redis_client.ping()
            if inspect.isawaitable(ping_command):
                await ping_command
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
        SystemExit: if the app directory name is reflex or if the name is not standard for a python package name.
    """
    app_name = app_name or Path.cwd().name.replace("-", "_")
    # Make sure the app is not named "reflex".
    if app_name.lower() == constants.Reflex.MODULE_NAME:
        console.error(
            f"The app directory cannot be named [bold]{constants.Reflex.MODULE_NAME}[/bold]."
        )
        raise SystemExit(1)

    # Make sure the app name is standard for a python package name.
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", app_name):
        console.error(
            "The app directory name must start with a letter and can contain letters, numbers, and underscores."
        )
        raise SystemExit(1)

    return app_name


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
        SystemExit: If the current working directory is not the reflex directory.
    """
    if not constants.Config.FILE.exists():
        console.error(
            f"[cyan]{constants.Config.FILE}[/cyan] not found. Move to the root folder of your project, or run [bold]{constants.Reflex.MODULE_NAME} init[/bold] to start a new project."
        )
        raise SystemExit(1)


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

    if not _is_app_compiled_with_same_reflex_version():
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


def _is_app_compiled_with_same_reflex_version() -> bool:
    json_file = get_web_dir() / constants.Reflex.JSON
    if not json_file.exists():
        return False
    app_version = json.loads(json_file.read_text()).get("version")
    return app_version == constants.Reflex.VERSION


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
    from reflex.utils.frontend_skeleton import initialize_web_directory
    from reflex.utils.js_runtimes import install_bun, validate_frontend_dependencies

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
        from alembic.util.exc import CommandError

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


@once
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
