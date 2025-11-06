"""The Reflex config."""

import dataclasses
import importlib
import os
import sys
import threading
import urllib.parse
from collections.abc import Sequence
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from reflex import constants
from reflex.constants.base import LogLevel
from reflex.environment import EnvironmentVariables as EnvironmentVariables
from reflex.environment import EnvVar as EnvVar
from reflex.environment import (
    ExistingPath,
    _load_dotenv_from_files,
    _paths_from_env_files,
    interpret_env_var_value,
)
from reflex.environment import env_var as env_var
from reflex.environment import environment as environment
from reflex.plugins import Plugin
from reflex.plugins.sitemap import SitemapPlugin
from reflex.utils import console
from reflex.utils.exceptions import ConfigError

if TYPE_CHECKING:
    from pyleak.base import LeakAction


@dataclasses.dataclass(kw_only=True)
class DBConfig:
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
    ) -> "DBConfig":
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
    ) -> "DBConfig":
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
    ) -> "DBConfig":
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


@dataclasses.dataclass(kw_only=True)
class BaseConfig:
    """Base config for the Reflex app."""

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

    # PyLeak monitoring configuration for detecting event loop blocking and resource leaks.
    enable_pyleak_monitoring: bool = False

    # Threshold in seconds for detecting event loop blocking operations.
    pyleak_blocking_threshold: float = 0.1

    # Grace period in seconds for thread leak detection cleanup.
    pyleak_thread_grace_period: float = 0.2

    # Action to take when PyLeak detects issues
    pyleak_action: "LeakAction | None" = None

    # The bun path
    bun_path: ExistingPath = constants.Bun.DEFAULT_PATH

    # Timeout to do a production build of a frontend page.
    static_page_generation_timeout: int = 60

    # List of origins that are allowed to connect to the backend API.
    cors_allowed_origins: Sequence[str] = dataclasses.field(default=("*",))

    # Whether to use React strict mode.
    react_strict_mode: bool = True

    # Additional frontend packages to install.
    frontend_packages: list[str] = dataclasses.field(default_factory=list)

    # Indicate which type of state manager to use
    state_manager_mode: constants.StateManagerMode = constants.StateManagerMode.DISK

    # Maximum expiration lock time for redis state manager
    redis_lock_expiration: int = constants.Expiration.LOCK

    # Maximum lock time before warning for redis state manager.
    redis_lock_warning_threshold: int = constants.Expiration.LOCK_WARNING_THRESHOLD

    # Token expiration time for redis state manager
    redis_token_expiration: int = constants.Expiration.TOKEN

    # Attributes that were explicitly set by the user.
    _non_default_attributes: set[str] = dataclasses.field(
        default_factory=set, init=False
    )

    # Path to file containing key-values pairs to override in the environment; Dotenv format.
    env_file: str | None = None

    # Whether to automatically create setters for state base vars
    state_auto_setters: bool | None = None

    # Whether to display the sticky "Built with Reflex" badge on all pages.
    show_built_with_reflex: bool | None = None

    # Whether the app is running in the reflex cloud environment.
    is_reflex_cloud: bool = False

    # Extra overlay function to run after the app is built. Formatted such that `from path_0.path_1... import path[-1]`, and calling it with no arguments would work. For example, "reflex.components.moment.moment".
    extra_overlay_function: str | None = None

    # List of plugins to use in the app.
    plugins: list[Plugin] = dataclasses.field(default_factory=list)

    # List of fully qualified import paths of plugins to disable in the app (e.g. reflex.plugins.sitemap.SitemapPlugin).
    disable_plugins: list[str] = dataclasses.field(default_factory=list)

    # The transport method for client-server communication.
    transport: Literal["websocket", "polling"] = "websocket"

    # Whether to skip plugin checks.
    _skip_plugins_checks: bool = dataclasses.field(default=False, repr=False)

    _prefixes: ClassVar[list[str]] = ["REFLEX_"]


_PLUGINS_ENABLED_BY_DEFAULT = [
    SitemapPlugin,
]


@dataclasses.dataclass(kw_only=True, init=False)
class Config(BaseConfig):
    """Configuration class for Reflex applications.

    The config defines runtime settings for your app including server ports, database connections,
    frontend packages, and deployment settings.

    By default, the config is defined in an `rxconfig.py` file in the root of your app:

    ```python
    # rxconfig.py
    import reflex as rx

    config = rx.Config(
        app_name="myapp",
        # Server configuration
        frontend_port=3000,
        backend_port=8000,
        # Database
        db_url="postgresql://user:pass@localhost:5432/mydb",
        # Additional frontend packages
        frontend_packages=["react-icons"],
        # CORS settings for production
        cors_allowed_origins=["https://mydomain.com"],
    )
    ```

    ## Environment Variable Overrides

    Any config value can be overridden by setting an environment variable with the `REFLEX_`
    prefix and the parameter name in uppercase:

    ```bash
    REFLEX_DB_URL="postgresql://user:pass@localhost/db" reflex run
    REFLEX_FRONTEND_PORT=3001 reflex run
    ```

    ## Key Configuration Areas

    - **App Settings**: `app_name`, `loglevel`, `telemetry_enabled`
    - **Server**: `frontend_port`, `backend_port`, `api_url`, `cors_allowed_origins`
    - **Database**: `db_url`, `async_db_url`, `redis_url`
    - **Frontend**: `frontend_packages`, `react_strict_mode`
    - **State Management**: `state_manager_mode`, `state_auto_setters`
    - **Plugins**: `plugins`, `disable_plugins`

    See the [configuration docs](https://reflex.dev/docs/advanced-onboarding/configuration) for complete details on all available options.
    """

    # Track whether the app name has already been validated for this Config instance.
    _app_name_is_valid: bool = dataclasses.field(default=False, repr=False)

    def _post_init(self, **kwargs):
        """Post-initialization method to set up the config.

        This method is called after the config is initialized. It sets up the
        environment variables, updates the config from the environment, and
        replaces default URLs if ports were set.

        Args:
            **kwargs: The kwargs passed to the Pydantic init method.

        Raises:
            ConfigError: If some values in the config are invalid.
        """
        class_fields = self.class_fields()
        for key, value in kwargs.items():
            if key not in class_fields:
                setattr(self, key, value)

        # Clean up this code when we remove plain envvar in 0.8.0
        env_loglevel = os.environ.get("REFLEX_LOGLEVEL")
        if env_loglevel is not None:
            env_loglevel = LogLevel(env_loglevel.lower())
        if env_loglevel or self.loglevel != LogLevel.DEFAULT:
            console.set_log_level(env_loglevel or self.loglevel)

        # Update the config from environment variables.
        env_kwargs = self.update_from_env()
        for key, env_value in env_kwargs.items():
            setattr(self, key, env_value)

        # Add builtin plugins if not disabled.
        if not self._skip_plugins_checks:
            self._add_builtin_plugins()

        #   Update default URLs if ports were set
        kwargs.update(env_kwargs)
        self._non_default_attributes = set(kwargs.keys())
        self._replace_defaults(**kwargs)

        if (
            self.state_manager_mode == constants.StateManagerMode.REDIS
            and not self.redis_url
        ):
            msg = f"{self._prefixes[0]}REDIS_URL is required when using the redis state manager."
            raise ConfigError(msg)

    def _add_builtin_plugins(self):
        """Add the builtin plugins to the config."""
        for plugin in _PLUGINS_ENABLED_BY_DEFAULT:
            plugin_name = plugin.__module__ + "." + plugin.__qualname__
            if plugin_name not in self.disable_plugins:
                if not any(isinstance(p, plugin) for p in self.plugins):
                    console.warn(
                        f"`{plugin_name}` plugin is enabled by default, but not explicitly added to the config. "
                        "If you want to use it, please add it to the `plugins` list in your config inside of `rxconfig.py`. "
                        f"To disable this plugin, set `disable_plugins` to `{[plugin_name, *self.disable_plugins]!r}`.",
                    )
                    self.plugins.append(plugin())
            else:
                if any(isinstance(p, plugin) for p in self.plugins):
                    console.warn(
                        f"`{plugin_name}` is disabled in the config, but it is still present in the `plugins` list. "
                        "Please remove it from the `plugins` list in your config inside of `rxconfig.py`.",
                    )

        for disabled_plugin in self.disable_plugins:
            if not isinstance(disabled_plugin, str):
                console.warn(
                    f"reflex.Config.disable_plugins should only contain strings, but got {disabled_plugin!r}. "
                )
            if not any(
                plugin.__module__ + "." + plugin.__qualname__ == disabled_plugin
                for plugin in _PLUGINS_ENABLED_BY_DEFAULT
            ):
                console.warn(
                    f"`{disabled_plugin}` is disabled in the config, but it is not a built-in plugin. "
                    "Please remove it from the `disable_plugins` list in your config inside of `rxconfig.py`.",
                )

    @classmethod
    def class_fields(cls) -> set[str]:
        """Get the fields of the config class.

        Returns:
            The fields of the config class.
        """
        return {field.name for field in dataclasses.fields(cls)}

    if not TYPE_CHECKING:

        def __init__(self, **kwargs):
            """Initialize the config values.

            Args:
                **kwargs: The kwargs to pass to the Pydantic init method.

            # noqa: DAR101 self
            """
            class_fields = self.class_fields()
            super().__init__(**{k: v for k, v in kwargs.items() if k in class_fields})
            self._post_init(**kwargs)

    def json(self) -> str:
        """Get the config as a JSON string.

        Returns:
            The config as a JSON string.
        """
        import json

        from reflex.utils.serializers import serialize

        return json.dumps(self, default=serialize)

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
            _load_dotenv_from_files(_paths_from_env_files(self.env_file))

        updated_values = {}
        # Iterate over the fields.
        for field in dataclasses.fields(self):
            # The env var name is the key in uppercase.
            environment_variable = None
            for prefix in self._prefixes:
                if environment_variable := os.environ.get(
                    f"{prefix}{field.name.upper()}"
                ):
                    break

            # If the env var is set, override the config value.
            if environment_variable and environment_variable.strip():
                # Interpret the value.
                value = interpret_env_var_value(
                    environment_variable,
                    field.type,
                    field.name,
                )

                # Set the value.
                updated_values[field.name] = value

                if field.name.upper() in _sensitive_env_vars:
                    environment_variable = "***"

                if value != getattr(self, field.name):
                    console.debug(
                        f"Overriding config value {field.name} with env var {field.name.upper()}={environment_variable}",
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
        return Config(app_name="", _skip_plugins_checks=True)
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
