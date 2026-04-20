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
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Literal

from reflex_base import constants
from reflex_base.constants.base import LogLevel
from reflex_base.environment import EnvironmentVariables as EnvironmentVariables
from reflex_base.environment import EnvVar as EnvVar
from reflex_base.environment import (
    ExistingPath,
    SequenceOptions,
    _load_dotenv_from_files,
    _paths_from_env_files,
    interpret_env_var_value,
)
from reflex_base.environment import env_var as env_var
from reflex_base.environment import environment as environment
from reflex_base.plugins import Plugin
from reflex_base.plugins.sitemap import SitemapPlugin
from reflex_base.utils import console
from reflex_base.utils.exceptions import ConfigError


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
    """Base config for the Reflex app.

    Attributes:
        app_name: The name of the app (should match the name of the app directory).
        app_module_import: The path to the app module.
        loglevel: The log level to use.
        frontend_port: The port to run the frontend on. NOTE: When running in dev mode, the next available port will be used if this is taken.
        frontend_path: The path to run the frontend on. For example, "/app" will run the frontend on http://localhost:3000/app
        backend_port: The port to run the backend on. NOTE: When running in dev mode, the next available port will be used if this is taken.
        backend_path: The path prefix for backend routes. For example, "/api" mounts the event websocket, /ping, /_upload, /_health, and /_all_routes under /api, and is automatically included in URLs baked into the frontend. Changing this requires a full `reflex run` restart — routes are registered at startup.
        api_url: The backend url the frontend will connect to. This must be updated if the backend is hosted elsewhere, or in production.
        deploy_url: The url the frontend will be hosted on.
        backend_host: The url the backend will be hosted on.
        db_url: The database url used by rx.Model.
        async_db_url: The async database url used by rx.Model.
        redis_url: The redis url.
        telemetry_enabled: Telemetry opt-in.
        bun_path: The bun path.
        static_page_generation_timeout: Timeout to do a production build of a frontend page.
        cors_allowed_origins: Comma separated list of origins that are allowed to connect to the backend API.
        vite_allowed_hosts: Allowed hosts for the Vite dev server. Set to True to allow all hosts, or provide a list of hostnames (e.g. ["myservice.local"]) to allow specific ones. Prevents 403 errors in Docker, Codespaces, reverse proxies, etc.
        react_strict_mode: Whether to use React strict mode.
        frontend_packages: Additional frontend packages to install.
        state_manager_mode: Indicate which type of state manager to use.
        redis_lock_expiration: Maximum expiration lock time for redis state manager.
        redis_lock_warning_threshold: Maximum lock time before warning for redis state manager.
        redis_token_expiration: Token expiration time for redis state manager.
        env_file: Path to file containing key-values pairs to override in the environment; Dotenv format.
        state_auto_setters: Whether to automatically create setters for state base vars.
        show_built_with_reflex: Whether to display the sticky "Built with Reflex" badge on all pages.
        is_reflex_cloud: Whether the app is running in the reflex cloud environment.
        extra_overlay_function: Extra overlay function to run after the app is built. Formatted such that `from path_0.path_1... import path[-1]`, and calling it with no arguments would work. For example, "reflex_components_moment.moment".
        plugins: List of plugins to use in the app.
        disable_plugins: List of plugin types to disable in the app.
        transport: The transport method for client-server communication.
    """

    app_name: str

    app_module_import: str | None = None

    loglevel: constants.LogLevel = constants.LogLevel.DEFAULT

    frontend_port: int | None = None

    frontend_path: str = ""

    backend_port: int | None = None

    backend_path: str = ""

    api_url: str = f"http://localhost:{constants.DefaultPorts.BACKEND_PORT}"

    deploy_url: str | None = f"http://localhost:{constants.DefaultPorts.FRONTEND_PORT}"

    backend_host: str = "0.0.0.0"

    db_url: str | None = None

    async_db_url: str | None = None

    redis_url: str | None = None

    telemetry_enabled: bool = True

    bun_path: ExistingPath = constants.Bun.DEFAULT_PATH

    static_page_generation_timeout: int = 60

    cors_allowed_origins: Annotated[
        Sequence[str],
        SequenceOptions(delimiter=","),
    ] = dataclasses.field(default=("*",))

    vite_allowed_hosts: bool | list[str] = False

    react_strict_mode: bool = True

    frontend_packages: list[str] = dataclasses.field(default_factory=list)

    state_manager_mode: constants.StateManagerMode = constants.StateManagerMode.DISK

    redis_lock_expiration: int = constants.Expiration.LOCK

    redis_lock_warning_threshold: int = constants.Expiration.LOCK_WARNING_THRESHOLD

    redis_token_expiration: int = constants.Expiration.TOKEN

    # Attributes that were explicitly set by the user.
    _non_default_attributes: set[str] = dataclasses.field(
        default_factory=set, init=False
    )

    env_file: str | None = None

    state_auto_setters: bool = False

    show_built_with_reflex: bool | None = None

    is_reflex_cloud: bool = False

    extra_overlay_function: str | None = None

    plugins: list[Plugin] = dataclasses.field(default_factory=list)

    disable_plugins: list[type[Plugin]] = dataclasses.field(default_factory=list)

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

        # Normalize disable_plugins: convert strings and Plugin subclasses to instances.
        self._normalize_disable_plugins()

        # Add builtin plugins if not disabled.
        if not self._skip_plugins_checks:
            self._add_builtin_plugins()

        # Warn if state_auto_setters is explicitly set.
        if "state_auto_setters" in kwargs:
            if kwargs["state_auto_setters"]:
                reason = (
                    "auto setters will be removed; use explicit event handlers instead"
                )
            else:
                reason = "state_auto_setters=False is already the default and the option will be removed"
            console.deprecate(
                feature_name="state_auto_setters",
                reason=reason,
                deprecation_version="0.9.0",
                removal_version="1.0",
            )

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

    def _normalize_disable_plugins(self):
        """Normalize disable_plugins list entries to Plugin subclasses.

        Handles backward compatibility by converting strings (fully qualified
        import paths) and Plugin instances to their associated classes.
        """
        normalized: list[type[Plugin]] = []
        for entry in self.disable_plugins:
            if isinstance(entry, type) and issubclass(entry, Plugin):
                normalized.append(entry)
            elif isinstance(entry, Plugin):
                normalized.append(type(entry))
            elif isinstance(entry, str):
                console.deprecate(
                    feature_name="Passing strings to disable_plugins",
                    reason="pass Plugin classes directly instead, e.g. disable_plugins=[SitemapPlugin]",
                    deprecation_version="0.8.28",
                    removal_version="1.0",
                )
                try:
                    from reflex_base.environment import interpret_plugin_class_env

                    normalized.append(
                        interpret_plugin_class_env(entry, "disable_plugins")
                    )
                except Exception:
                    console.warn(
                        f"Failed to import plugin from string {entry!r} in disable_plugins. "
                        "Please pass Plugin subclasses directly.",
                    )
            else:
                console.warn(
                    f"reflex.Config.disable_plugins should contain Plugin subclasses, but got {entry!r}.",
                )
        self.disable_plugins = normalized

    def _add_builtin_plugins(self):
        """Add the builtin plugins to the config."""
        for plugin in _PLUGINS_ENABLED_BY_DEFAULT:
            plugin_name = plugin.__module__ + "." + plugin.__qualname__
            if plugin not in self.disable_plugins:
                if not any(isinstance(p, plugin) for p in self.plugins):
                    console.warn(
                        f"`{plugin_name}` plugin is enabled by default, but not explicitly added to the config. "
                        "If you want to use it, please add it to the `plugins` list in your config inside of `rxconfig.py`. "
                        f"To disable this plugin, add `{plugin.__name__}` to the `disable_plugins` list.",
                    )
                    self.plugins.append(plugin())
            else:
                if any(isinstance(p, plugin) for p in self.plugins):
                    console.warn(
                        f"`{plugin_name}` is disabled in the config, but it is still present in the `plugins` list. "
                        "Please remove it from the `plugins` list in your config inside of `rxconfig.py`.",
                    )

        for disabled_plugin in self.disable_plugins:
            if disabled_plugin not in _PLUGINS_ENABLED_BY_DEFAULT:
                console.warn(
                    f"`{disabled_plugin!r}` is disabled in the config, but it is not a built-in plugin. "
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

        from reflex_base.utils.serializers import serialize

        return json.dumps(self, default=serialize)

    @staticmethod
    def _prepend_path(path: str, prefix: str) -> str:
        """Prepend ``prefix`` (normalized to ``/prefix``) to ``path`` when both are non-empty.

        Args:
            path: The path to prepend the prefix to.
            prefix: The configured prefix (e.g. ``frontend_path`` or ``backend_path``).

        Returns:
            The path with the prefix prepended if it begins with a slash, otherwise the original path.
        """
        if prefix and path.startswith("/"):
            return f"/{prefix.strip('/')}{path}"
        return path

    def prepend_frontend_path(self, path: str) -> str:
        """Prepend the frontend path to a given path.

        Args:
            path: The path to prepend the frontend path to.

        Returns:
            The path with the frontend path prepended if it begins with a slash, otherwise the original path.
        """
        return self._prepend_path(path, self.frontend_path)

    def prepend_backend_path(self, path: str) -> str:
        """Prepend the backend path to a given path.

        Args:
            path: The path to prepend the backend path to.

        Returns:
            The path with the backend path prepended if it begins with a slash, otherwise the original path.
        """
        return self._prepend_path(path, self.backend_path)

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
