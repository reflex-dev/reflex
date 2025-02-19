"""The Reflex config."""

from __future__ import annotations

import concurrent.futures
import dataclasses
import enum
import importlib
import inspect
import multiprocessing
import os
import platform
import sys
import threading
import urllib.parse
from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
    get_args,
    get_origin,
    get_type_hints,
)

import pydantic.v1 as pydantic
from reflex_cli.constants.hosting import Hosting

from reflex import constants
from reflex.base import Base
from reflex.utils import console
from reflex.utils.exceptions import ConfigError, EnvironmentVarValueError
from reflex.utils.types import GenericType, is_union, value_inside_optional

try:
    from dotenv import load_dotenv  # pyright: ignore [reportMissingImports]
except ImportError:
    load_dotenv = None


class DBConfig(Base):
    """Database config."""

    engine: str
    username: Optional[str] = ""
    password: Optional[str] = ""
    host: Optional[str] = ""
    port: Optional[int] = None
    database: str

    @classmethod
    def postgresql(
        cls,
        database: str,
        username: str,
        password: str | None = None,
        host: str | None = None,
        port: int | None = 5432,
    ) -> DBConfig:
        """Create an instance with postgresql engine.

        Args:
            database: Database name.
            username: Database username.
            password: Database password.
            host: Database host.
            port: Database port.

        Returns:
            DBConfig instance.
        """
        return cls(
            engine="postgresql",
            username=username,
            password=password,
            host=host,
            port=port,
            database=database,
        )

    @classmethod
    def postgresql_psycopg(
        cls,
        database: str,
        username: str,
        password: str | None = None,
        host: str | None = None,
        port: int | None = 5432,
    ) -> DBConfig:
        """Create an instance with postgresql+psycopg engine.

        Args:
            database: Database name.
            username: Database username.
            password: Database password.
            host: Database host.
            port: Database port.

        Returns:
            DBConfig instance.
        """
        return cls(
            engine="postgresql+psycopg",
            username=username,
            password=password,
            host=host,
            port=port,
            database=database,
        )

    @classmethod
    def sqlite(
        cls,
        database: str,
    ) -> DBConfig:
        """Create an instance with sqlite engine.

        Args:
            database: Database name.

        Returns:
            DBConfig instance.
        """
        return cls(
            engine="sqlite",
            database=database,
        )

    def get_url(self) -> str:
        """Get database URL.

        Returns:
            The database URL.
        """
        host = (
            f"{self.host}:{self.port}" if self.host and self.port else self.host or ""
        )
        username = urllib.parse.quote_plus(self.username) if self.username else ""
        password = urllib.parse.quote_plus(self.password) if self.password else ""

        if username:
            path = f"{username}:{password}@{host}" if password else f"{username}@{host}"
        else:
            path = f"{host}"

        return f"{self.engine}://{path}/{self.database}"


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
    elif field.default_factory != dataclasses.MISSING:
        return field.default_factory()
    else:
        raise ValueError(
            f"Missing value for environment variable {field.name} and no default value found"
        )


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
    elif value.lower() in false_values:
        return False
    raise EnvironmentVarValueError(f"Invalid boolean value: {value} for {field_name}")


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
        raise EnvironmentVarValueError(
            f"Invalid integer value: {value} for {field_name}"
        ) from ve


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
        raise EnvironmentVarValueError(f"Path does not exist: {path} for {field_name}")
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
        raise EnvironmentVarValueError(
            f"Invalid enum value: {value} for {field_name}"
        ) from ve


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
    """
    field_type = value_inside_optional(field_type)

    if is_union(field_type):
        raise ValueError(
            f"Union types are not supported for environment variables: {field_name}."
        )

    if field_type is bool:
        return interpret_boolean_env(value, field_name)
    elif field_type is str:
        return value
    elif field_type is int:
        return interpret_int_env(value, field_name)
    elif field_type is Path:
        return interpret_path_env(value, field_name)
    elif field_type is ExistingPath:
        return interpret_existing_path_env(value, field_name)
    elif get_origin(field_type) is list:
        return [
            interpret_env_var_value(
                v,
                get_args(field_type)[0],
                f"{field_name}[{i}]",
            )
            for i, v in enumerate(value.split(":"))
        ]
    elif inspect.isclass(field_type) and issubclass(field_type, enum.Enum):
        return interpret_enum_env(value, field_type, field_name)

    else:
        raise ValueError(
            f"Invalid type for environment variable {field_name}: {field_type}. This is probably an issue in Reflex."
        )


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

    def getenv(self) -> Optional[T]:
        """Get the interpreted environment variable value.

        Returns:
            The environment variable value.
        """
        env_value = os.getenv(self.name, None)
        if env_value is not None:
            return self.interpret(env_value)
        return None

    def is_set(self) -> bool:
        """Check if the environment variable is set.

        Returns:
            True if the environment variable is set.
        """
        return self.name in os.environ

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


@lru_cache()
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

    # Whether to use npm over bun to install frontend packages.
    REFLEX_USE_NPM: EnvVar[bool] = env_var(False)

    # The npm registry to use.
    NPM_CONFIG_REGISTRY: EnvVar[Optional[str]] = env_var(None)

    # Whether to use Granian for the backend. Otherwise, use Uvicorn.
    REFLEX_USE_GRANIAN: EnvVar[bool] = env_var(False)

    # The username to use for authentication on python package repository. Username and password must both be provided.
    TWINE_USERNAME: EnvVar[Optional[str]] = env_var(None)

    # The password to use for authentication on python package repository. Username and password must both be provided.
    TWINE_PASSWORD: EnvVar[Optional[str]] = env_var(None)

    # Whether to use the system installed bun. If set to false, bun will be bundled with the app.
    REFLEX_USE_SYSTEM_BUN: EnvVar[bool] = env_var(False)

    # Whether to use the system installed node and npm. If set to false, node and npm will be bundled with the app.
    REFLEX_USE_SYSTEM_NODE: EnvVar[bool] = env_var(False)

    # The working directory for the next.js commands.
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

    REFLEX_COMPILE_EXECUTOR: EnvVar[Optional[ExecutorType]] = env_var(None)

    # Whether to use separate processes to compile the frontend and how many. If not set, defaults to thread executor.
    REFLEX_COMPILE_PROCESSES: EnvVar[Optional[int]] = env_var(None)

    # Whether to use separate threads to compile the frontend and how many. Defaults to `min(32, os.cpu_count() + 4)`.
    REFLEX_COMPILE_THREADS: EnvVar[Optional[int]] = env_var(None)

    # The directory to store reflex dependencies.
    REFLEX_DIR: EnvVar[Path] = env_var(constants.Reflex.DIR)

    # Whether to print the SQL queries if the log level is INFO or lower.
    SQLALCHEMY_ECHO: EnvVar[bool] = env_var(False)

    # Whether to check db connections before using them.
    SQLALCHEMY_POOL_PRE_PING: EnvVar[bool] = env_var(True)

    # Whether to ignore the redis config error. Some redis servers only allow out-of-band configuration.
    REFLEX_IGNORE_REDIS_CONFIG_ERROR: EnvVar[bool] = env_var(False)

    # Whether to skip purging the web directory in dev mode.
    REFLEX_PERSIST_WEB_DIR: EnvVar[bool] = env_var(False)

    # The reflex.build frontend host.
    REFLEX_BUILD_FRONTEND: EnvVar[str] = env_var(
        constants.Templates.REFLEX_BUILD_FRONTEND
    )

    # The reflex.build backend host.
    REFLEX_BUILD_BACKEND: EnvVar[str] = env_var(
        constants.Templates.REFLEX_BUILD_BACKEND
    )

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

    # Reflex internal env to reload the config.
    RELOAD_CONFIG: EnvVar[bool] = env_var(False, internal=True)

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
    REFLEX_USE_TURBOPACK: EnvVar[bool] = env_var(True)

    # Additional paths to include in the hot reload. Separated by a colon.
    REFLEX_HOT_RELOAD_INCLUDE_PATHS: EnvVar[List[Path]] = env_var([])

    # Paths to exclude from the hot reload. Takes precedence over include paths. Separated by a colon.
    REFLEX_HOT_RELOAD_EXCLUDE_PATHS: EnvVar[List[Path]] = env_var([])

    # Enables different behavior for when the backend would do a cold start if it was inactive.
    REFLEX_DOES_BACKEND_COLD_START: EnvVar[bool] = env_var(False)

    # The timeout for the backend to do a cold start in seconds.
    REFLEX_BACKEND_COLD_START_TIMEOUT: EnvVar[int] = env_var(10)

    # Used by flexgen to enumerate the pages.
    REFLEX_ADD_ALL_ROUTES_ENDPOINT: EnvVar[bool] = env_var(False)


environment = EnvironmentVariables()


# These vars are not logged because they may contain sensitive information.
_sensitive_env_vars = {"DB_URL", "ASYNC_DB_URL", "REDIS_URL"}


class Config(Base):
    """The config defines runtime settings for the app.

    By default, the config is defined in an `rxconfig.py` file in the root of the app.

    ```python
    # rxconfig.py
    import reflex as rx

    config = rx.Config(
        app_name="myapp",
        api_url="http://localhost:8000",
    )
    ```

    Every config value can be overridden by an environment variable with the same name in uppercase.
    For example, `db_url` can be overridden by setting the `DB_URL` environment variable.

    See the [configuration](https://reflex.dev/docs/getting-started/configuration/) docs for more info.
    """

    class Config:  # pyright: ignore [reportIncompatibleVariableOverride]
        """Pydantic config for the config."""

        validate_assignment = True
        use_enum_values = False

    # The name of the app (should match the name of the app directory).
    app_name: str

    # The path to the app module.
    app_module_import: Optional[str] = None

    # The log level to use.
    loglevel: constants.LogLevel = constants.LogLevel.DEFAULT

    # The port to run the frontend on. NOTE: When running in dev mode, the next available port will be used if this is taken.
    frontend_port: int | None = None

    # The path to run the frontend on. For example, "/app" will run the frontend on http://localhost:3000/app
    frontend_path: str = ""

    # The port to run the backend on. NOTE: When running in dev mode, the next available port will be used if this is taken.
    backend_port: int | None = None

    # The backend url the frontend will connect to. This must be updated if the backend is hosted elsewhere, or in production.
    api_url: str = f"http://localhost:{constants.DefaultPorts.BACKEND_PORT}"

    # The url the frontend will be hosted on.
    deploy_url: Optional[str] = (
        f"http://localhost:{constants.DefaultPorts.FRONTEND_PORT}"
    )

    # The url the backend will be hosted on.
    backend_host: str = "0.0.0.0"

    # The database url used by rx.Model.
    db_url: Optional[str] = "sqlite:///reflex.db"

    # The async database url used by rx.Model.
    async_db_url: Optional[str] = None

    # The redis url
    redis_url: Optional[str] = None

    # Telemetry opt-in.
    telemetry_enabled: bool = True

    # The bun path
    bun_path: ExistingPath = constants.Bun.DEFAULT_PATH

    # Timeout to do a production build of a frontend page.
    static_page_generation_timeout: int = 60

    # List of origins that are allowed to connect to the backend API.
    cors_allowed_origins: List[str] = ["*"]

    # Tailwind config.
    tailwind: Optional[Dict[str, Any]] = {"plugins": ["@tailwindcss/typography"]}

    # Timeout when launching the gunicorn server. TODO(rename this to backend_timeout?)
    timeout: int = 120

    # Whether to enable or disable nextJS gzip compression.
    next_compression: bool = True

    # Whether to use React strict mode in nextJS
    react_strict_mode: bool = True

    # Additional frontend packages to install.
    frontend_packages: List[str] = []

    # The hosting service backend URL.
    cp_backend_url: str = Hosting.HOSTING_SERVICE
    # The hosting service frontend URL.
    cp_web_url: str = Hosting.HOSTING_SERVICE_UI

    # The worker class used in production mode
    gunicorn_worker_class: str = "uvicorn.workers.UvicornH11Worker"

    # Number of gunicorn workers from user
    gunicorn_workers: Optional[int] = None

    # Number of requests before a worker is restarted; set to 0 to disable
    gunicorn_max_requests: int = 100

    # Variance limit for max requests; gunicorn only
    gunicorn_max_requests_jitter: int = 25

    # Indicate which type of state manager to use
    state_manager_mode: constants.StateManagerMode = constants.StateManagerMode.DISK

    # Maximum expiration lock time for redis state manager
    redis_lock_expiration: int = constants.Expiration.LOCK

    # Maximum lock time before warning for redis state manager.
    redis_lock_warning_threshold: int = constants.Expiration.LOCK_WARNING_THRESHOLD

    # Token expiration time for redis state manager
    redis_token_expiration: int = constants.Expiration.TOKEN

    # Attributes that were explicitly set by the user.
    _non_default_attributes: Set[str] = pydantic.PrivateAttr(set())

    # Path to file containing key-values pairs to override in the environment; Dotenv format.
    env_file: Optional[str] = None

    # Whether to display the sticky "Built with Reflex" badge on all pages.
    show_built_with_reflex: Optional[bool] = None

    # Whether the app is running in the reflex cloud environment.
    is_reflex_cloud: bool = False

    # Extra overlay function to run after the app is built. Formatted such that `from path_0.path_1... import path[-1]`, and calling it with no arguments would work. For example, "reflex.components.moment.momnet".
    extra_overlay_function: Optional[str] = None

    def __init__(self, *args, **kwargs):
        """Initialize the config values.

        Args:
            *args: The args to pass to the Pydantic init method.
            **kwargs: The kwargs to pass to the Pydantic init method.

        Raises:
            ConfigError: If some values in the config are invalid.
        """
        super().__init__(*args, **kwargs)

        # Update the config from environment variables.
        env_kwargs = self.update_from_env()
        for key, env_value in env_kwargs.items():
            setattr(self, key, env_value)

        # Update default URLs if ports were set
        kwargs.update(env_kwargs)
        self._non_default_attributes.update(kwargs)
        self._replace_defaults(**kwargs)

        # Set the log level for this process
        console.set_log_level(self.loglevel)

        if (
            self.state_manager_mode == constants.StateManagerMode.REDIS
            and not self.redis_url
        ):
            raise ConfigError(
                "REDIS_URL is required when using the redis state manager."
            )

    @property
    def app_module(self) -> ModuleType | None:
        """Return the app module if `app_module_import` is set.

        Returns:
            The app module.
        """
        return (
            importlib.import_module(self.app_module_import)
            if self.app_module_import
            else None
        )

    @property
    def module(self) -> str:
        """Get the module name of the app.

        Returns:
            The module name.
        """
        if self.app_module is not None:
            return self.app_module.__name__
        return ".".join([self.app_name, self.app_name])

    def update_from_env(self) -> dict[str, Any]:
        """Update the config values based on set environment variables.
        If there is a set env_file, it is loaded first.

        Returns:
            The updated config values.
        """
        env_file = self.env_file or os.environ.get("ENV_FILE", None)
        if env_file:
            if load_dotenv is None:
                console.error(
                    """The `python-dotenv` package is required to load environment variables from a file. Run `pip install "python-dotenv>=1.0.1"`."""
                )
            else:
                # load env file if exists
                load_dotenv(env_file, override=True)

        updated_values = {}
        # Iterate over the fields.
        for key, field in self.__fields__.items():
            # The env var name is the key in uppercase.
            env_var = os.environ.get(key.upper())

            # If the env var is set, override the config value.
            if env_var is not None:
                # Interpret the value.
                value = interpret_env_var_value(env_var, field.outer_type_, field.name)

                # Set the value.
                updated_values[key] = value

                if key.upper() in _sensitive_env_vars:
                    env_var = "***"

                console.info(
                    f"Overriding config value {key} with env var {key.upper()}={env_var}",
                    dedupe=True,
                )

        return updated_values

    def get_event_namespace(self) -> str:
        """Get the path that the backend Websocket server lists on.

        Returns:
            The namespace for websocket.
        """
        event_url = constants.Endpoint.EVENT.get_url()
        return urllib.parse.urlsplit(event_url).path

    def _replace_defaults(self, **kwargs):
        """Replace formatted defaults when the caller provides updates.

        Args:
            **kwargs: The kwargs passed to the config or from the env.
        """
        if "api_url" not in self._non_default_attributes and "backend_port" in kwargs:
            self.api_url = f"http://localhost:{kwargs['backend_port']}"

        if (
            "deploy_url" not in self._non_default_attributes
            and "frontend_port" in kwargs
        ):
            self.deploy_url = f"http://localhost:{kwargs['frontend_port']}"

        if "api_url" not in self._non_default_attributes:
            # If running in Github Codespaces, override API_URL
            codespace_name = os.getenv("CODESPACE_NAME")
            github_codespaces_port_forwarding_domain = os.getenv(
                "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN"
            )
            # If running on Replit.com interactively, override API_URL to ensure we maintain the backend_port
            replit_dev_domain = os.getenv("REPLIT_DEV_DOMAIN")
            backend_port = kwargs.get("backend_port", self.backend_port)
            if codespace_name and github_codespaces_port_forwarding_domain:
                self.api_url = (
                    f"https://{codespace_name}-{kwargs.get('backend_port', self.backend_port)}"
                    f".{github_codespaces_port_forwarding_domain}"
                )
            elif replit_dev_domain and backend_port:
                self.api_url = f"https://{replit_dev_domain}:{backend_port}"

    def _set_persistent(self, **kwargs):
        """Set values in this config and in the environment so they persist into subprocess.

        Args:
            **kwargs: The kwargs passed to the config.
        """
        for key, value in kwargs.items():
            if value is not None:
                os.environ[key.upper()] = str(value)
            setattr(self, key, value)
        self._non_default_attributes.update(kwargs)
        self._replace_defaults(**kwargs)


def _get_config() -> Config:
    """Get the app config.

    Returns:
        The app config.
    """
    # only import the module if it exists. If a module spec exists then
    # the module exists.
    spec = find_spec(constants.Config.MODULE)
    if not spec:
        # we need this condition to ensure that a ModuleNotFound error is not thrown when
        # running unit/integration tests or during `reflex init`.
        return Config(app_name="")
    rxconfig = importlib.import_module(constants.Config.MODULE)
    return rxconfig.config


# Protect sys.path from concurrent modification
_config_lock = threading.RLock()


def get_config(reload: bool = False) -> Config:
    """Get the app config.

    Args:
        reload: Re-import the rxconfig module from disk

    Returns:
        The app config.
    """
    cached_rxconfig = sys.modules.get(constants.Config.MODULE, None)
    if cached_rxconfig is not None:
        if reload:
            # Remove any cached module when `reload` is requested.
            del sys.modules[constants.Config.MODULE]
        else:
            return cached_rxconfig.config

    with _config_lock:
        orig_sys_path = sys.path.copy()
        sys.path.clear()
        sys.path.append(str(Path.cwd()))
        try:
            # Try to import the module with only the current directory in the path.
            return _get_config()
        except Exception:
            # If the module import fails, try to import with the original sys.path.
            sys.path.extend(orig_sys_path)
            return _get_config()
        finally:
            # Find any entries added to sys.path by rxconfig.py itself.
            extra_paths = [
                p for p in sys.path if p not in orig_sys_path and p != str(Path.cwd())
            ]
            # Restore the original sys.path.
            sys.path.clear()
            sys.path.extend(extra_paths)
            sys.path.extend(orig_sys_path)
