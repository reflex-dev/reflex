"""Environment variable management."""

from __future__ import annotations

import concurrent.futures
import dataclasses
import enum
import importlib
import multiprocessing
import os
import platform
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Generic,
    Literal,
    TypeVar,
    get_args,
    get_origin,
    get_type_hints,
)

from reflex import constants
from reflex.constants.base import LogLevel
from reflex.plugins import Plugin
from reflex.utils.exceptions import EnvironmentVarValueError
from reflex.utils.types import GenericType, is_union, value_inside_optional


def get_default_value_for_field(field: dataclasses.Field) -> Any:
    """Get the default value for a field.

    Args:
        field: The field.

    Returns:
        The default value.

    Raises:
        ValueError: If no default value is found.
    """
    if field.default != dataclasses.MISSING:
        return field.default
    if field.default_factory != dataclasses.MISSING:
        return field.default_factory()
    msg = f"Missing value for environment variable {field.name} and no default value found"
    raise ValueError(msg)


# TODO: Change all interpret_.* signatures to value: str, field: dataclasses.Field once we migrate rx.Config to dataclasses
def interpret_boolean_env(value: str, field_name: str) -> bool:
    """Interpret a boolean environment variable value.

    Args:
        value: The environment variable value.
        field_name: The field name.

    Returns:
        The interpreted value.

    Raises:
        EnvironmentVarValueError: If the value is invalid.
    """
    true_values = ["true", "1", "yes", "y"]
    false_values = ["false", "0", "no", "n"]

    if value.lower() in true_values:
        return True
    if value.lower() in false_values:
        return False
    msg = f"Invalid boolean value: {value!r} for {field_name}"
    raise EnvironmentVarValueError(msg)


def interpret_int_env(value: str, field_name: str) -> int:
    """Interpret an integer environment variable value.

    Args:
        value: The environment variable value.
        field_name: The field name.

    Returns:
        The interpreted value.

    Raises:
        EnvironmentVarValueError: If the value is invalid.
    """
    try:
        return int(value)
    except ValueError as ve:
        msg = f"Invalid integer value: {value!r} for {field_name}"
        raise EnvironmentVarValueError(msg) from ve


def interpret_float_env(value: str, field_name: str) -> float:
    """Interpret a float environment variable value.

    Args:
        value: The environment variable value.
        field_name: The field name.

    Returns:
        The interpreted value.

    Raises:
        EnvironmentVarValueError: If the value is invalid.
    """
    try:
        return float(value)
    except ValueError as ve:
        msg = f"Invalid float value: {value!r} for {field_name}"
        raise EnvironmentVarValueError(msg) from ve


def interpret_existing_path_env(value: str, field_name: str) -> ExistingPath:
    """Interpret a path environment variable value as an existing path.

    Args:
        value: The environment variable value.
        field_name: The field name.

    Returns:
        The interpreted value.

    Raises:
        EnvironmentVarValueError: If the path does not exist.
    """
    path = Path(value)
    if not path.exists():
        msg = f"Path does not exist: {path!r} for {field_name}"
        raise EnvironmentVarValueError(msg)
    return path


def interpret_path_env(value: str, field_name: str) -> Path:
    """Interpret a path environment variable value.

    Args:
        value: The environment variable value.
        field_name: The field name.

    Returns:
        The interpreted value.
    """
    return Path(value)


def interpret_plugin_env(value: str, field_name: str) -> Plugin:
    """Interpret a plugin environment variable value.

    Args:
        value: The environment variable value.
        field_name: The field name.

    Returns:
        The interpreted value.

    Raises:
        EnvironmentVarValueError: If the value is invalid.
    """
    if "." not in value:
        msg = f"Invalid plugin value: {value!r} for {field_name}. Plugin name must be in the format 'package.module.PluginName'."
        raise EnvironmentVarValueError(msg)

    import_path, plugin_name = value.rsplit(".", 1)

    try:
        module = importlib.import_module(import_path)
    except ImportError as e:
        msg = f"Failed to import module {import_path!r} for {field_name}: {e}"
        raise EnvironmentVarValueError(msg) from e

    try:
        plugin_class = getattr(module, plugin_name, None)
    except Exception as e:
        msg = f"Failed to get plugin class {plugin_name!r} from module {import_path!r} for {field_name}: {e}"
        raise EnvironmentVarValueError(msg) from e

    if not isinstance(plugin_class, type) or not issubclass(plugin_class, Plugin):
        msg = f"Invalid plugin class: {plugin_name!r} for {field_name}. Must be a subclass of Plugin."
        raise EnvironmentVarValueError(msg)

    try:
        return plugin_class()
    except Exception as e:
        msg = f"Failed to instantiate plugin {plugin_name!r} for {field_name}: {e}"
        raise EnvironmentVarValueError(msg) from e


def interpret_enum_env(value: str, field_type: GenericType, field_name: str) -> Any:
    """Interpret an enum environment variable value.

    Args:
        value: The environment variable value.
        field_type: The field type.
        field_name: The field name.

    Returns:
        The interpreted value.

    Raises:
        EnvironmentVarValueError: If the value is invalid.
    """
    try:
        return field_type(value)
    except ValueError as ve:
        msg = f"Invalid enum value: {value!r} for {field_name}"
        raise EnvironmentVarValueError(msg) from ve


def interpret_env_var_value(
    value: str, field_type: GenericType, field_name: str
) -> Any:
    """Interpret an environment variable value based on the field type.

    Args:
        value: The environment variable value.
        field_type: The field type.
        field_name: The field name.

    Returns:
        The interpreted value.

    Raises:
        ValueError: If the value is invalid.
        EnvironmentVarValueError: If the value is invalid for the specific type.
    """
    field_type = value_inside_optional(field_type)

    if is_union(field_type):
        msg = f"Union types are not supported for environment variables: {field_name}."
        raise ValueError(msg)

    value = value.strip()

    if field_type is bool:
        return interpret_boolean_env(value, field_name)
    if field_type is str:
        return value
    if field_type is LogLevel:
        loglevel = LogLevel.from_string(value)
        if loglevel is None:
            msg = f"Invalid log level value: {value} for {field_name}"
            raise EnvironmentVarValueError(msg)
        return loglevel
    if field_type is int:
        return interpret_int_env(value, field_name)
    if field_type is float:
        return interpret_float_env(value, field_name)
    if field_type is Path:
        return interpret_path_env(value, field_name)
    if field_type is ExistingPath:
        return interpret_existing_path_env(value, field_name)
    if field_type is Plugin:
        return interpret_plugin_env(value, field_name)
    if get_origin(field_type) is Literal:
        literal_values = get_args(field_type)
        for literal_value in literal_values:
            if isinstance(literal_value, str) and literal_value == value:
                return literal_value
            if isinstance(literal_value, bool):
                try:
                    interpreted_bool = interpret_boolean_env(value, field_name)
                    if interpreted_bool == literal_value:
                        return interpreted_bool
                except EnvironmentVarValueError:
                    continue
            if isinstance(literal_value, int):
                try:
                    interpreted_int = interpret_int_env(value, field_name)
                    if interpreted_int == literal_value:
                        return interpreted_int
                except EnvironmentVarValueError:
                    continue
        msg = f"Invalid literal value: {value!r} for {field_name}, expected one of {literal_values}"
        raise EnvironmentVarValueError(msg)
    if get_origin(field_type) in (list, Sequence):
        return [
            interpret_env_var_value(
                v,
                get_args(field_type)[0],
                f"{field_name}[{i}]",
            )
            for i, v in enumerate(value.split(":"))
        ]
    if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
        return interpret_enum_env(value, field_type, field_name)

    msg = f"Invalid type for environment variable {field_name}: {field_type}. This is probably an issue in Reflex."
    raise ValueError(msg)


T = TypeVar("T")


class EnvVar(Generic[T]):
    """Environment variable."""

    name: str
    default: Any
    type_: T

    def __init__(self, name: str, default: Any, type_: T) -> None:
        """Initialize the environment variable.

        Args:
            name: The environment variable name.
            default: The default value.
            type_: The type of the value.
        """
        self.name = name
        self.default = default
        self.type_ = type_

    def interpret(self, value: str) -> T:
        """Interpret the environment variable value.

        Args:
            value: The environment variable value.

        Returns:
            The interpreted value.
        """
        return interpret_env_var_value(value, self.type_, self.name)

    def getenv(self) -> T | None:
        """Get the interpreted environment variable value.

        Returns:
            The environment variable value.
        """
        env_value = os.getenv(self.name, None)
        if env_value and env_value.strip():
            return self.interpret(env_value)
        return None

    def is_set(self) -> bool:
        """Check if the environment variable is set.

        Returns:
            True if the environment variable is set.
        """
        return bool(os.getenv(self.name, "").strip())

    def get(self) -> T:
        """Get the interpreted environment variable value or the default value if not set.

        Returns:
            The interpreted value.
        """
        env_value = self.getenv()
        if env_value is not None:
            return env_value
        return self.default

    def set(self, value: T | None) -> None:
        """Set the environment variable. None unsets the variable.

        Args:
            value: The value to set.
        """
        if value is None:
            _ = os.environ.pop(self.name, None)
        else:
            if isinstance(value, enum.Enum):
                value = value.value
            if isinstance(value, list):
                str_value = ":".join(str(v) for v in value)
            else:
                str_value = str(value)
            os.environ[self.name] = str_value


@lru_cache
def get_type_hints_environment(cls: type) -> dict[str, Any]:
    """Get the type hints for the environment variables.

    Args:
        cls: The class.

    Returns:
        The type hints.
    """
    return get_type_hints(cls)


class env_var:  # noqa: N801 # pyright: ignore [reportRedeclaration]
    """Descriptor for environment variables."""

    name: str
    default: Any
    internal: bool = False

    def __init__(self, default: Any, internal: bool = False) -> None:
        """Initialize the descriptor.

        Args:
            default: The default value.
            internal: Whether the environment variable is reflex internal.
        """
        self.default = default
        self.internal = internal

    def __set_name__(self, owner: Any, name: str):
        """Set the name of the descriptor.

        Args:
            owner: The owner class.
            name: The name of the descriptor.
        """
        self.name = name

    def __get__(
        self, instance: EnvironmentVariables, owner: type[EnvironmentVariables]
    ):
        """Get the EnvVar instance.

        Args:
            instance: The instance.
            owner: The owner class.

        Returns:
            The EnvVar instance.
        """
        type_ = get_args(get_type_hints_environment(owner)[self.name])[0]
        env_name = self.name
        if self.internal:
            env_name = f"__{env_name}"
        return EnvVar(name=env_name, default=self.default, type_=type_)


if TYPE_CHECKING:

    def env_var(default: Any, internal: bool = False) -> EnvVar:
        """Typing helper for the env_var descriptor.

        Args:
            default: The default value.
            internal: Whether the environment variable is reflex internal.

        Returns:
            The EnvVar instance.
        """
        return default


class PathExistsFlag:
    """Flag to indicate that a path must exist."""


ExistingPath = Annotated[Path, PathExistsFlag]


class PerformanceMode(enum.Enum):
    """Performance mode for the app."""

    WARN = "warn"
    RAISE = "raise"
    OFF = "off"


class ExecutorType(enum.Enum):
    """Executor for compiling the frontend."""

    THREAD = "thread"
    PROCESS = "process"
    MAIN_THREAD = "main_thread"

    @classmethod
    def get_executor_from_environment(cls):
        """Get the executor based on the environment variables.

        Returns:
            The executor.
        """
        from reflex.utils import console

        executor_type = environment.REFLEX_COMPILE_EXECUTOR.get()

        reflex_compile_processes = environment.REFLEX_COMPILE_PROCESSES.get()
        reflex_compile_threads = environment.REFLEX_COMPILE_THREADS.get()
        # By default, use the main thread. Unless the user has specified a different executor.
        # Using a process pool is much faster, but not supported on all platforms. It's gated behind a flag.
        if executor_type is None:
            if (
                platform.system() not in ("Linux", "Darwin")
                and reflex_compile_processes is not None
            ):
                console.warn("Multiprocessing is only supported on Linux and MacOS.")

            if (
                platform.system() in ("Linux", "Darwin")
                and reflex_compile_processes is not None
            ):
                if reflex_compile_processes == 0:
                    console.warn(
                        "Number of processes must be greater than 0. If you want to use the default number of processes, set REFLEX_COMPILE_EXECUTOR to 'process'. Defaulting to None."
                    )
                    reflex_compile_processes = None
                elif reflex_compile_processes < 0:
                    console.warn(
                        "Number of processes must be greater than 0. Defaulting to None."
                    )
                    reflex_compile_processes = None
                executor_type = ExecutorType.PROCESS
            elif reflex_compile_threads is not None:
                if reflex_compile_threads == 0:
                    console.warn(
                        "Number of threads must be greater than 0. If you want to use the default number of threads, set REFLEX_COMPILE_EXECUTOR to 'thread'. Defaulting to None."
                    )
                    reflex_compile_threads = None
                elif reflex_compile_threads < 0:
                    console.warn(
                        "Number of threads must be greater than 0. Defaulting to None."
                    )
                    reflex_compile_threads = None
                executor_type = ExecutorType.THREAD
            else:
                executor_type = ExecutorType.MAIN_THREAD

        match executor_type:
            case ExecutorType.PROCESS:
                executor = concurrent.futures.ProcessPoolExecutor(
                    max_workers=reflex_compile_processes,
                    mp_context=multiprocessing.get_context("fork"),
                )
            case ExecutorType.THREAD:
                executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=reflex_compile_threads
                )
            case ExecutorType.MAIN_THREAD:
                FUTURE_RESULT_TYPE = TypeVar("FUTURE_RESULT_TYPE")

                class MainThreadExecutor:
                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        pass

                    def submit(
                        self, fn: Callable[..., FUTURE_RESULT_TYPE], *args, **kwargs
                    ) -> concurrent.futures.Future[FUTURE_RESULT_TYPE]:
                        future_job = concurrent.futures.Future()
                        future_job.set_result(fn(*args, **kwargs))
                        return future_job

                executor = MainThreadExecutor()

        return executor


class EnvironmentVariables:
    """Environment variables class to instantiate environment variables."""

    # Indicate the current command that was invoked in the reflex CLI.
    REFLEX_COMPILE_CONTEXT: EnvVar[constants.CompileContext] = env_var(
        constants.CompileContext.UNDEFINED, internal=True
    )

    # Whether to use npm over bun to install and run the frontend.
    REFLEX_USE_NPM: EnvVar[bool] = env_var(False)

    # The npm registry to use.
    NPM_CONFIG_REGISTRY: EnvVar[str | None] = env_var(None)

    # Whether to use Granian for the backend. By default, the backend uses Uvicorn if available.
    REFLEX_USE_GRANIAN: EnvVar[bool] = env_var(False)

    # Whether to use the system installed bun. If set to false, bun will be bundled with the app.
    REFLEX_USE_SYSTEM_BUN: EnvVar[bool] = env_var(False)

    # The working directory for the frontend directory.
    REFLEX_WEB_WORKDIR: EnvVar[Path] = env_var(Path(constants.Dirs.WEB))

    # The working directory for the states directory.
    REFLEX_STATES_WORKDIR: EnvVar[Path] = env_var(Path(constants.Dirs.STATES))

    # Path to the alembic config file
    ALEMBIC_CONFIG: EnvVar[ExistingPath] = env_var(Path(constants.ALEMBIC_CONFIG))

    # Disable SSL verification for HTTPX requests.
    SSL_NO_VERIFY: EnvVar[bool] = env_var(False)

    # The directory to store uploaded files.
    REFLEX_UPLOADED_FILES_DIR: EnvVar[Path] = env_var(
        Path(constants.Dirs.UPLOADED_FILES)
    )

    REFLEX_COMPILE_EXECUTOR: EnvVar[ExecutorType | None] = env_var(None)

    # Whether to use separate processes to compile the frontend and how many. If not set, defaults to thread executor.
    REFLEX_COMPILE_PROCESSES: EnvVar[int | None] = env_var(None)

    # Whether to use separate threads to compile the frontend and how many. Defaults to `min(32, os.cpu_count() + 4)`.
    REFLEX_COMPILE_THREADS: EnvVar[int | None] = env_var(None)

    # The directory to store reflex dependencies.
    REFLEX_DIR: EnvVar[Path] = env_var(constants.Reflex.DIR)

    # Whether to print the SQL queries if the log level is INFO or lower.
    SQLALCHEMY_ECHO: EnvVar[bool] = env_var(False)

    # Whether to check db connections before using them.
    SQLALCHEMY_POOL_PRE_PING: EnvVar[bool] = env_var(True)

    # The size of the database connection pool.
    SQLALCHEMY_POOL_SIZE: EnvVar[int] = env_var(5)

    # The maximum overflow size of the database connection pool.
    SQLALCHEMY_MAX_OVERFLOW: EnvVar[int] = env_var(10)

    # Recycle connections after this many seconds.
    SQLALCHEMY_POOL_RECYCLE: EnvVar[int] = env_var(-1)

    # The timeout for acquiring a connection from the pool.
    SQLALCHEMY_POOL_TIMEOUT: EnvVar[int] = env_var(30)

    # Whether to ignore the redis config error. Some redis servers only allow out-of-band configuration.
    REFLEX_IGNORE_REDIS_CONFIG_ERROR: EnvVar[bool] = env_var(False)

    # Whether to skip purging the web directory in dev mode.
    REFLEX_PERSIST_WEB_DIR: EnvVar[bool] = env_var(False)

    # This env var stores the execution mode of the app
    REFLEX_ENV_MODE: EnvVar[constants.Env] = env_var(constants.Env.DEV)

    # Whether to run the backend only. Exclusive with REFLEX_FRONTEND_ONLY.
    REFLEX_BACKEND_ONLY: EnvVar[bool] = env_var(False)

    # Whether to run the frontend only. Exclusive with REFLEX_BACKEND_ONLY.
    REFLEX_FRONTEND_ONLY: EnvVar[bool] = env_var(False)

    # The port to run the frontend on.
    REFLEX_FRONTEND_PORT: EnvVar[int | None] = env_var(None)

    # The port to run the backend on.
    REFLEX_BACKEND_PORT: EnvVar[int | None] = env_var(None)

    # If this env var is set to "yes", App.compile will be a no-op
    REFLEX_SKIP_COMPILE: EnvVar[bool] = env_var(False, internal=True)

    # Whether to run app harness tests in headless mode.
    APP_HARNESS_HEADLESS: EnvVar[bool] = env_var(False)

    # Which app harness driver to use.
    APP_HARNESS_DRIVER: EnvVar[str] = env_var("Chrome")

    # Arguments to pass to the app harness driver.
    APP_HARNESS_DRIVER_ARGS: EnvVar[str] = env_var("")

    # Whether to check for outdated package versions.
    REFLEX_CHECK_LATEST_VERSION: EnvVar[bool] = env_var(True)

    # In which performance mode to run the app.
    REFLEX_PERF_MODE: EnvVar[PerformanceMode] = env_var(PerformanceMode.WARN)

    # The maximum size of the reflex state in kilobytes.
    REFLEX_STATE_SIZE_LIMIT: EnvVar[int] = env_var(1000)

    # Whether to use the turbopack bundler.
    REFLEX_USE_TURBOPACK: EnvVar[bool] = env_var(False)

    # Additional paths to include in the hot reload. Separated by a colon.
    REFLEX_HOT_RELOAD_INCLUDE_PATHS: EnvVar[list[Path]] = env_var([])

    # Paths to exclude from the hot reload. Takes precedence over include paths. Separated by a colon.
    REFLEX_HOT_RELOAD_EXCLUDE_PATHS: EnvVar[list[Path]] = env_var([])

    # Enables different behavior for when the backend would do a cold start if it was inactive.
    REFLEX_DOES_BACKEND_COLD_START: EnvVar[bool] = env_var(False)

    # The timeout for the backend to do a cold start in seconds.
    REFLEX_BACKEND_COLD_START_TIMEOUT: EnvVar[int] = env_var(10)

    # Used by flexgen to enumerate the pages.
    REFLEX_ADD_ALL_ROUTES_ENDPOINT: EnvVar[bool] = env_var(False)

    # The address to bind the HTTP client to. You can set this to "::" to enable IPv6.
    REFLEX_HTTP_CLIENT_BIND_ADDRESS: EnvVar[str | None] = env_var(None)

    # Maximum size of the message in the websocket server in bytes.
    REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE: EnvVar[int] = env_var(
        constants.POLLING_MAX_HTTP_BUFFER_SIZE
    )

    # The interval to send a ping to the websocket server in seconds.
    REFLEX_SOCKET_INTERVAL: EnvVar[int] = env_var(constants.Ping.INTERVAL)

    # The timeout to wait for a pong from the websocket server in seconds.
    REFLEX_SOCKET_TIMEOUT: EnvVar[int] = env_var(constants.Ping.TIMEOUT)

    # Whether to run Granian in a spawn process. This enables Reflex to pick up on environment variable changes between hot reloads.
    REFLEX_STRICT_HOT_RELOAD: EnvVar[bool] = env_var(False)

    # The path to the reflex log file. If not set, the log file will be stored in the reflex user directory.
    REFLEX_LOG_FILE: EnvVar[Path | None] = env_var(None)

    # Enable full logging of debug messages to reflex user directory.
    REFLEX_ENABLE_FULL_LOGGING: EnvVar[bool] = env_var(False)

    # Whether to enable hot module replacement
    VITE_HMR: EnvVar[bool] = env_var(True)

    # Whether to force a full reload on changes.
    VITE_FORCE_FULL_RELOAD: EnvVar[bool] = env_var(False)

    # Whether to enable Rolldown's experimental HMR.
    VITE_EXPERIMENTAL_HMR: EnvVar[bool] = env_var(False)

    # Whether to generate sourcemaps for the frontend.
    VITE_SOURCEMAP: EnvVar[Literal[False, True, "inline", "hidden"]] = env_var(False)  # noqa: RUF038

    # Whether to enable SSR for the frontend.
    REFLEX_SSR: EnvVar[bool] = env_var(True)

    # Whether to mount the compiled frontend app in the backend server in production.
    REFLEX_MOUNT_FRONTEND_COMPILED_APP: EnvVar[bool] = env_var(False, internal=True)

    # How long to delay writing updated states to disk. (Higher values mean less writes, but more chance of lost data.)
    REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS: EnvVar[float] = env_var(2.0)

    # How long to wait between automatic reload on frontend error to avoid reload loops.
    REFLEX_AUTO_RELOAD_COOLDOWN_TIME_MS: EnvVar[int] = env_var(10_000)

    # Whether to enable debug logging for the redis state manager.
    REFLEX_STATE_MANAGER_REDIS_DEBUG: EnvVar[bool] = env_var(False)

    # Whether to opportunistically hold the redis lock to allow fast in-memory access while uncontended.
    REFLEX_OPLOCK_ENABLED: EnvVar[bool] = env_var(False)

    # How long to opportunistically hold the redis lock in milliseconds (must be less than the token expiration).
    REFLEX_OPLOCK_HOLD_TIME_MS: EnvVar[int] = env_var(0)


environment = EnvironmentVariables()

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _paths_from_env_files(env_files: str) -> list[Path]:
    """Convert a string of paths separated by os.pathsep into a list of Path objects.

    Args:
        env_files: The string of paths.

    Returns:
        A list of Path objects.
    """
    # load env files in reverse order
    return list(
        reversed([
            Path(path)
            for path_element in env_files.split(os.pathsep)
            if (path := path_element.strip())
        ])
    )


def _load_dotenv_from_files(files: list[Path]):
    """Load environment variables from a list of files.

    Args:
        files: A list of Path objects representing the environment variable files.
    """
    from reflex.utils import console

    if not files:
        return

    if load_dotenv is None:
        console.error(
            """The `python-dotenv` package is required to load environment variables from a file. Run `pip install "python-dotenv>=1.1.0"`."""
        )
        return

    for env_file in files:
        if env_file.exists():
            load_dotenv(env_file, override=True)


def _paths_from_environment() -> list[Path]:
    """Get the paths from the REFLEX_ENV_FILE environment variable.

    Returns:
        A list of Path objects.
    """
    env_files = os.environ.get("REFLEX_ENV_FILE")
    if not env_files:
        return []

    return _paths_from_env_files(env_files)


def _load_dotenv_from_env():
    """Load environment variables from paths specified in REFLEX_ENV_FILE."""
    _load_dotenv_from_files(_paths_from_environment())


# Load the env files at import time if they are set in the ENV_FILE environment variable.
_load_dotenv_from_env()
