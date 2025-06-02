"""The Reflex config."""

from __future__ import annotations

import importlib
import os
import sys
import threading
import urllib.parse
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar

import pydantic.v1 as pydantic

from reflex import constants
from reflex.base import Base
from reflex.constants.base import LogLevel
from reflex.environment import EnvironmentVariables as EnvironmentVariables
from reflex.environment import EnvVar as EnvVar
from reflex.environment import ExistingPath, interpret_env_var_value
from reflex.environment import env_var as env_var
from reflex.environment import environment as environment
from reflex.plugins import Plugin, TailwindV3Plugin, TailwindV4Plugin
from reflex.utils import console
from reflex.utils.exceptions import ConfigError
from reflex.utils.types import true_type_for_pydantic_field

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _load_dotenv_from_str(env_files: str) -> None:
    if not env_files:
        return

    if load_dotenv is None:
        console.error(
            """The `python-dotenv` package is required to load environment variables from a file. Run `pip install "python-dotenv>=1.1.0"`."""
        )
        return

    # load env files in reverse order if they exist
    for env_file_path in [
        Path(p) for s in reversed(env_files.split(os.pathsep)) if (p := s.strip())
    ]:
        if env_file_path.exists():
            load_dotenv(env_file_path, override=True)


def _load_dotenv_from_env():
    """Load environment variables from paths specified in REFLEX_ENV_FILE."""
    show_deprecation = False
    env_env_file = os.environ.get("REFLEX_ENV_FILE")
    if not env_env_file:
        env_env_file = os.environ.get("ENV_FILE")
        if env_env_file:
            show_deprecation = True
    if show_deprecation:
        console.deprecate(
            "Usage of deprecated ENV_FILE env var detected.",
            reason="Prefer `REFLEX_` prefix when setting env vars.",
            deprecation_version="0.7.13",
            removal_version="0.8.0",
        )
    if env_env_file:
        _load_dotenv_from_str(env_env_file)


# Load the env files at import time if they are set in the ENV_FILE environment variable.
_load_dotenv_from_env()


class DBConfig(Base):
    """Database config."""

    engine: str
    username: str | None = ""
    password: str | None = ""
    host: str | None = ""
    port: int | None = None
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
    app_module_import: str | None = None

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
    deploy_url: str | None = f"http://localhost:{constants.DefaultPorts.FRONTEND_PORT}"

    # The url the backend will be hosted on.
    backend_host: str = "0.0.0.0"

    # The database url used by rx.Model.
    db_url: str | None = "sqlite:///reflex.db"

    # The async database url used by rx.Model.
    async_db_url: str | None = None

    # The redis url
    redis_url: str | None = None

    # Telemetry opt-in.
    telemetry_enabled: bool = True

    # The bun path
    bun_path: ExistingPath = constants.Bun.DEFAULT_PATH

    # Timeout to do a production build of a frontend page.
    static_page_generation_timeout: int = 60

    # List of origins that are allowed to connect to the backend API.
    cors_allowed_origins: list[str] = ["*"]

    # Tailwind config.
    tailwind: dict[str, Any] | None = {"plugins": ["@tailwindcss/typography"]}

    # DEPRECATED. Timeout when launching the gunicorn server.
    timeout: int | None = None

    # Whether to enable or disable nextJS gzip compression.
    next_compression: bool = True

    # Whether to enable or disable NextJS dev indicator.
    next_dev_indicators: bool = False

    # Whether to use React strict mode in nextJS
    react_strict_mode: bool = True

    # Additional frontend packages to install.
    frontend_packages: list[str] = []

    # DEPRECATED. The worker class used in production mode
    gunicorn_worker_class: str = "uvicorn.workers.UvicornH11Worker"

    # DEPRECATED. Number of gunicorn workers from user
    gunicorn_workers: int | None = None

    # DEPRECATED. Number of requests before a worker is restarted; set to 0 to disable
    gunicorn_max_requests: int | None = None

    # DEPRECATED. Variance limit for max requests; gunicorn only
    gunicorn_max_requests_jitter: int | None = None

    # Indicate which type of state manager to use
    state_manager_mode: constants.StateManagerMode = constants.StateManagerMode.DISK

    # Maximum expiration lock time for redis state manager
    redis_lock_expiration: int = constants.Expiration.LOCK

    # Maximum lock time before warning for redis state manager.
    redis_lock_warning_threshold: int = constants.Expiration.LOCK_WARNING_THRESHOLD

    # Token expiration time for redis state manager
    redis_token_expiration: int = constants.Expiration.TOKEN

    # Attributes that were explicitly set by the user.
    _non_default_attributes: set[str] = pydantic.PrivateAttr(set())

    # Path to file containing key-values pairs to override in the environment; Dotenv format.
    env_file: str | None = None

    # Whether to automatically create setters for state base vars
    state_auto_setters: bool = True

    # Whether to display the sticky "Built with Reflex" badge on all pages.
    show_built_with_reflex: bool | None = None

    # Whether the app is running in the reflex cloud environment.
    is_reflex_cloud: bool = False

    # Extra overlay function to run after the app is built. Formatted such that `from path_0.path_1... import path[-1]`, and calling it with no arguments would work. For example, "reflex.components.moment.moment".
    extra_overlay_function: str | None = None

    # List of plugins to use in the app.
    plugins: list[Plugin] = []

    _prefixes: ClassVar[list[str]] = ["REFLEX_"]

    def __init__(self, *args, **kwargs):
        """Initialize the config values.

        Args:
            *args: The args to pass to the Pydantic init method.
            **kwargs: The kwargs to pass to the Pydantic init method.

        Raises:
            ConfigError: If some values in the config are invalid.
        """
        super().__init__(*args, **kwargs)

        # Clean up this code when we remove plain envvar in 0.8.0
        show_deprecation = False
        env_loglevel = os.environ.get("REFLEX_LOGLEVEL")
        if not env_loglevel:
            env_loglevel = os.environ.get("LOGLEVEL")
            if env_loglevel:
                show_deprecation = True
        if env_loglevel is not None:
            env_loglevel = LogLevel(env_loglevel.lower())
        if env_loglevel or self.loglevel != LogLevel.DEFAULT:
            console.set_log_level(env_loglevel or self.loglevel)

        if show_deprecation:
            console.deprecate(
                "Usage of deprecated LOGLEVEL env var detected.",
                reason="Prefer `REFLEX_` prefix when setting env vars.",
                deprecation_version="0.7.13",
                removal_version="0.8.0",
            )

        # Update the config from environment variables.
        env_kwargs = self.update_from_env()
        for key, env_value in env_kwargs.items():
            setattr(self, key, env_value)

        #   Update default URLs if ports were set
        kwargs.update(env_kwargs)
        self._non_default_attributes.update(kwargs)
        self._replace_defaults(**kwargs)

        if self.tailwind is not None and not any(
            isinstance(plugin, (TailwindV3Plugin, TailwindV4Plugin))
            for plugin in self.plugins
        ):
            console.deprecate(
                "Inferring tailwind usage",
                reason="""

If you are using tailwind, add `rx.plugins.TailwindV3Plugin()` to the `plugins=[]` in rxconfig.py.

If you are not using tailwind, set `tailwind` to `None` in rxconfig.py.""",
                deprecation_version="0.7.13",
                removal_version="0.8.0",
                dedupe=True,
            )
            self.plugins.append(TailwindV3Plugin())

        if (
            self.state_manager_mode == constants.StateManagerMode.REDIS
            and not self.redis_url
        ):
            msg = f"{self._prefixes[0]}REDIS_URL is required when using the redis state manager."
            raise ConfigError(msg)

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
        if self.app_module_import is not None:
            return self.app_module_import
        return self.app_name + "." + self.app_name

    def update_from_env(self) -> dict[str, Any]:
        """Update the config values based on set environment variables.
        If there is a set env_file, it is loaded first.

        Returns:
            The updated config values.
        """
        if self.env_file:
            _load_dotenv_from_str(self.env_file)

        updated_values = {}
        # Iterate over the fields.
        for key, field in self.__fields__.items():
            # The env var name is the key in uppercase.
            for prefix in self._prefixes:
                if environment_variable := os.environ.get(f"{prefix}{key.upper()}"):
                    break
            else:
                # Default to non-prefixed env var if other are not found.
                if environment_variable := os.environ.get(key.upper()):
                    console.deprecate(
                        f"Usage of deprecated {key.upper()} env var detected.",
                        reason=f"Prefer `{self._prefixes[0]}` prefix when setting env vars.",
                        deprecation_version="0.7.13",
                        removal_version="0.8.0",
                    )

            # If the env var is set, override the config value.
            if environment_variable and environment_variable.strip():
                # Interpret the value.
                value = interpret_env_var_value(
                    environment_variable,
                    true_type_for_pydantic_field(field),
                    field.name,
                )

                # Set the value.
                updated_values[key] = value

                if key.upper() in _sensitive_env_vars:
                    environment_variable = "***"

                if value != getattr(self, key):
                    console.debug(
                        f"Overriding config value {key} with env var {key.upper()}={environment_variable}",
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
                os.environ[self._prefixes[0] + key.upper()] = str(value)
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
