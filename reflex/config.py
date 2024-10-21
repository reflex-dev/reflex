"""The Reflex config."""

from __future__ import annotations

import dataclasses
import importlib
import os
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from typing_extensions import get_type_hints

from reflex.utils.exceptions import ConfigError, EnvironmentVarValueError
from reflex.utils.types import value_inside_optional

try:
    import pydantic.v1 as pydantic
except ModuleNotFoundError:
    import pydantic

from reflex_cli.constants.hosting import Hosting

from reflex import constants
from reflex.base import Base
from reflex.utils import console


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
    def postgresql_psycopg2(
        cls,
        database: str,
        username: str,
        password: str | None = None,
        host: str | None = None,
        port: int | None = 5432,
    ) -> DBConfig:
        """Create an instance with postgresql+psycopg2 engine.

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
            engine="postgresql+psycopg2",
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


def interpret_boolean_env(value: str) -> bool:
    """Interpret a boolean environment variable value.

    Args:
        value: The environment variable value.

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
    raise EnvironmentVarValueError(f"Invalid boolean value: {value}")


def interpret_int_env(value: str) -> int:
    """Interpret an integer environment variable value.

    Args:
        value: The environment variable value.

    Returns:
        The interpreted value.

    Raises:
        EnvironmentVarValueError: If the value is invalid.
    """
    try:
        return int(value)
    except ValueError as ve:
        raise EnvironmentVarValueError(f"Invalid integer value: {value}") from ve


def interpret_path_env(value: str) -> Path:
    """Interpret a path environment variable value.

    Args:
        value: The environment variable value.

    Returns:
        The interpreted value.

    Raises:
        EnvironmentVarValueError: If the path does not exist.
    """
    path = Path(value)
    if not path.exists():
        raise EnvironmentVarValueError(f"Path does not exist: {path}")
    return path


def interpret_env_var_value(value: str, field: dataclasses.Field) -> Any:
    """Interpret an environment variable value based on the field type.

    Args:
        value: The environment variable value.
        field: The field.

    Returns:
        The interpreted value.

    Raises:
        ValueError: If the value is invalid.
    """
    field_type = value_inside_optional(field.type)

    if field_type is bool:
        return interpret_boolean_env(value)
    elif field_type is str:
        return value
    elif field_type is int:
        return interpret_int_env(value)
    elif field_type is Path:
        return interpret_path_env(value)

    else:
        raise ValueError(
            f"Invalid type for environment variable {field.name}: {field_type}. This is probably an issue in Reflex."
        )


@dataclasses.dataclass(init=False)
class EnvironmentVariables:
    """Environment variables class to instantiate environment variables."""

    # Whether to use npm over bun to install frontend packages.
    REFLEX_USE_NPM: bool = False

    # The npm registry to use.
    NPM_CONFIG_REGISTRY: Optional[str] = None

    # Whether to use Granian for the backend. Otherwise, use Uvicorn.
    REFLEX_USE_GRANIAN: bool = False

    # The username to use for authentication on python package repository. Username and password must both be provided.
    TWINE_USERNAME: Optional[str] = None

    # The password to use for authentication on python package repository. Username and password must both be provided.
    TWINE_PASSWORD: Optional[str] = None

    # Whether to use the system installed bun. If set to false, bun will be bundled with the app.
    REFLEX_USE_SYSTEM_BUN: bool = False

    # Whether to use the system installed node and npm. If set to false, node and npm will be bundled with the app.
    REFLEX_USE_SYSTEM_NODE: bool = False

    # The working directory for the next.js commands.
    REFLEX_WEB_WORKDIR: Path = Path(constants.Dirs.WEB)

    # Path to the alembic config file
    ALEMBIC_CONFIG: Path = Path(constants.ALEMBIC_CONFIG)

    # Disable SSL verification for HTTPX requests.
    SSL_NO_VERIFY: bool = False

    # The directory to store uploaded files.
    REFLEX_UPLOADED_FILES_DIR: Path = Path(constants.Dirs.UPLOADED_FILES)

    # Whether to use seperate processes to compile the frontend and how many. If not set, defaults to thread executor.
    REFLEX_COMPILE_PROCESSES: Optional[int] = None

    # Whether to use seperate threads to compile the frontend and how many. Defaults to `min(32, os.cpu_count() + 4)`.
    REFLEX_COMPILE_THREADS: Optional[int] = None

    # The directory to store reflex dependencies.
    REFLEX_DIR: Path = Path(constants.Reflex.DIR)

    # Whether to print the SQL queries if the log level is INFO or lower.
    SQLALCHEMY_ECHO: bool = False

    # Whether to ignore the redis config error. Some redis servers only allow out-of-band configuration.
    REFLEX_IGNORE_REDIS_CONFIG_ERROR: bool = False

    # Whether to skip purging the web directory in dev mode.
    REFLEX_PERSIST_WEB_DIR: bool = False

    # The reflex.build frontend host.
    REFLEX_BUILD_FRONTEND: str = constants.Templates.REFLEX_BUILD_FRONTEND

    # The reflex.build backend host.
    REFLEX_BUILD_BACKEND: str = constants.Templates.REFLEX_BUILD_BACKEND

    def __init__(self):
        """Initialize the environment variables."""
        type_hints = get_type_hints(type(self))

        for field in dataclasses.fields(self):
            raw_value = os.getenv(field.name, None)

            field.type = type_hints.get(field.name) or field.type

            value = (
                interpret_env_var_value(raw_value, field)
                if raw_value is not None
                else get_default_value_for_field(field)
            )

            setattr(self, field.name, value)


environment = EnvironmentVariables()


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

    class Config:
        """Pydantic config for the config."""

        validate_assignment = True

    # The name of the app (should match the name of the app directory).
    app_name: str

    # The log level to use.
    loglevel: constants.LogLevel = constants.LogLevel.DEFAULT

    # The port to run the frontend on. NOTE: When running in dev mode, the next available port will be used if this is taken.
    frontend_port: int = constants.DefaultPorts.FRONTEND_PORT

    # The path to run the frontend on. For example, "/app" will run the frontend on http://localhost:3000/app
    frontend_path: str = ""

    # The port to run the backend on. NOTE: When running in dev mode, the next available port will be used if this is taken.
    backend_port: int = constants.DefaultPorts.BACKEND_PORT

    # The backend url the frontend will connect to. This must be updated if the backend is hosted elsewhere, or in production.
    api_url: str = f"http://localhost:{backend_port}"

    # The url the frontend will be hosted on.
    deploy_url: Optional[str] = f"http://localhost:{frontend_port}"

    # The url the backend will be hosted on.
    backend_host: str = "0.0.0.0"

    # The database url used by rx.Model.
    db_url: Optional[str] = "sqlite:///reflex.db"

    # The redis url
    redis_url: Optional[str] = None

    # Telemetry opt-in.
    telemetry_enabled: bool = True

    # The bun path
    bun_path: Union[str, Path] = constants.Bun.DEFAULT_PATH

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
    cp_backend_url: str = Hosting.CP_BACKEND_URL
    # The hosting service frontend URL.
    cp_web_url: str = Hosting.CP_WEB_URL

    # The worker class used in production mode
    gunicorn_worker_class: str = "uvicorn.workers.UvicornH11Worker"

    # Number of gunicorn workers from user
    gunicorn_workers: Optional[int] = None

    # Indicate which type of state manager to use
    state_manager_mode: constants.StateManagerMode = constants.StateManagerMode.DISK

    # Maximum expiration lock time for redis state manager
    redis_lock_expiration: int = constants.Expiration.LOCK

    # Token expiration time for redis state manager
    redis_token_expiration: int = constants.Expiration.TOKEN

    # Attributes that were explicitly set by the user.
    _non_default_attributes: Set[str] = pydantic.PrivateAttr(set())

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

        if (
            self.state_manager_mode == constants.StateManagerMode.REDIS
            and not self.redis_url
        ):
            raise ConfigError(
                "REDIS_URL is required when using the redis state manager."
            )

    @property
    def module(self) -> str:
        """Get the module name of the app.

        Returns:
            The module name.
        """
        return ".".join([self.app_name, self.app_name])

    def update_from_env(self) -> dict[str, Any]:
        """Update the config values based on set environment variables.

        Returns:
            The updated config values.

        Raises:
            EnvVarValueError: If an environment variable is set to an invalid type.
        """
        from reflex.utils.exceptions import EnvVarValueError

        updated_values = {}
        # Iterate over the fields.
        for key, field in self.__fields__.items():
            # The env var name is the key in uppercase.
            env_var = os.environ.get(key.upper())

            # If the env var is set, override the config value.
            if env_var is not None:
                if key.upper() != "DB_URL":
                    console.info(
                        f"Overriding config value {key} with env var {key.upper()}={env_var}",
                        dedupe=True,
                    )

                # Convert the env var to the expected type.
                try:
                    if issubclass(field.type_, bool):
                        # special handling for bool values
                        env_var = env_var.lower() in ["true", "1", "yes"]
                    else:
                        env_var = field.type_(env_var)
                except ValueError as ve:
                    console.error(
                        f"Could not convert {key.upper()}={env_var} to type {field.type_}"
                    )
                    raise EnvVarValueError from ve

                # Set the value.
                updated_values[key] = env_var

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
            GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN = os.getenv(
                "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN"
            )
            # If running on Replit.com interactively, override API_URL to ensure we maintain the backend_port
            replit_dev_domain = os.getenv("REPLIT_DEV_DOMAIN")
            backend_port = kwargs.get("backend_port", self.backend_port)
            if codespace_name and GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:
                self.api_url = (
                    f"https://{codespace_name}-{kwargs.get('backend_port', self.backend_port)}"
                    f".{GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
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


def get_config(reload: bool = False) -> Config:
    """Get the app config.

    Args:
        reload: Re-import the rxconfig module from disk

    Returns:
        The app config.
    """
    sys.path.insert(0, os.getcwd())
    # only import the module if it exists. If a module spec exists then
    # the module exists.
    spec = importlib.util.find_spec(constants.Config.MODULE)  # type: ignore
    if not spec:
        # we need this condition to ensure that a ModuleNotFound error is not thrown when
        # running unit/integration tests.
        return Config(app_name="")
    rxconfig = importlib.import_module(constants.Config.MODULE)
    if reload:
        importlib.reload(rxconfig)
    return rxconfig.config
