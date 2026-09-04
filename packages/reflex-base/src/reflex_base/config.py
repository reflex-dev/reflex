"""The Reflex config."""

import dataclasses
import importlib
import logging
import os
import sys
import threading
import urllib.parse
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Literal

from reflex_base import constants
from reflex_base.constants.base import LiteralColorMode, LogLevel
from reflex_base.environment import EnvironmentVariables as EnvironmentVariables
from reflex_base.environment import EnvVar as EnvVar
from reflex_base.environment import (
    ExistingPath,
    SequenceOptions,
    _InvalidPlugin,
    _load_dotenv_from_files,
    _paths_from_env_files,
    interpret_env_var_value,
)
from reflex_base.environment import env_var as env_var
from reflex_base.environment import environment as environment
from reflex_base.plugins import Plugin
from reflex_base.plugins.sitemap import SitemapPlugin
from reflex_base.registry import RegistrationContext
from reflex_base.utils import console, log
from reflex_base.utils.exceptions import ConfigError, InvalidPluginConfigError

logger = logging.getLogger(__name__)


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
        api_url: The backend url the frontend will connect to. Only needs to be set when the backend is listening on a different address than the frontend.
        deploy_url: The url the frontend will be hosted on. Used to build absolute frontend URLs, e.g. links in the generated sitemap.xml.
        backend_host: The url the backend will be hosted on.
        db_url: The database url used by rx.Model.
        async_db_url: The async database url used by rx.Model.
        redis_url: The redis url.
        telemetry_enabled: Telemetry opt-in.
        bun_path: The bun path.
        frozen_lockfile: Run frontend package manager in lockfile-enforcing mode (only honored by bun).
        static_page_generation_timeout: Timeout to do a production build of a frontend page.
        cors_allowed_origins: Comma separated list of origins that are allowed to connect to the backend API.
        vite_allowed_hosts: Allowed hosts for the Vite dev server. Set to True to allow all hosts, or provide a list of hostnames (e.g. ["myservice.local"]) to allow specific ones. Prevents 403 errors in Docker, Codespaces, reverse proxies, etc.
        react_strict_mode: Whether to use React strict mode.
        frontend_compression_formats: Pre-compressed frontend asset formats to generate for production builds. Supported values are "gzip", "brotli", and "zstd". Use an empty list to disable build-time pre-compression.
        frontend_packages: Additional frontend packages to install.
        state_manager_mode: Indicate which type of state manager to use.
        redis_lock_expiration: Maximum expiration lock time for redis state manager.
        redis_lock_warning_threshold: Maximum lock time before warning for redis state manager.
        redis_token_expiration: Token expiration time for redis state manager.
        env_file: Path to file containing key-values pairs to load into the environment; Dotenv format. Multiple files may be separated by os.pathsep. Requires the python-dotenv package.
        state_auto_setters: Whether to automatically create setters for state base vars.
        default_color_mode: The default color mode for the app: "system" (follow the OS preference), "light", or "dark". Applies to the built-in color mode switcher and `color_mode_cond` without requiring a radix theme.
        show_built_with_reflex: Whether to display the sticky "Built with Reflex" badge on all pages.
        is_reflex_cloud: Whether the app is running in the reflex cloud environment.
        extra_overlay_function: Extra overlay function to run after the app is built. Formatted such that `from path_0.path_1... import path[-1]`, and calling it with no arguments would work. For example, "reflex_components_moment.moment".
        hydrate_fallback: Function returning the component shown while the page is hydrating (React Router's HydrateFallback), used when App.hydrate_fallback is not set. Formatted such that `from path_0.path_1... import path[-1]`, and calling it with no arguments would work. For example, "my_app.components.loading".
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

    frozen_lockfile: bool = True

    static_page_generation_timeout: int = 60

    cors_allowed_origins: Annotated[
        Sequence[str],
        SequenceOptions(delimiter=","),
    ] = dataclasses.field(default=("*",))

    vite_allowed_hosts: bool | list[str] = False

    react_strict_mode: bool = True

    frontend_compression_formats: Annotated[
        list[str],
        SequenceOptions(delimiter=",", strip=True),
    ] = dataclasses.field(default_factory=lambda: ["gzip"])

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

    default_color_mode: LiteralColorMode = "system"

    show_built_with_reflex: bool | None = None

    is_reflex_cloud: bool = False

    extra_overlay_function: str | None = None

    hydrate_fallback: str | None = None

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

    See the [configuration docs](https://reflex.dev/docs/advanced-onboarding/configuration) for a guided overview of the most commonly tweaked settings.
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
        else:
            # In managed (CLI) mode, make sure backend workers render records;
            # outside the CLI this is a no-op and handlers stay untouched.
            log.ensure_configured()

        # Update the config from environment variables.
        env_kwargs = self.update_from_env()
        for key, env_value in env_kwargs.items():
            setattr(self, key, env_value)

        self._normalize_frontend_compression_formats()

        # Normalize route prefixes to ensure they start with a slash.
        self._normalize_paths()

        # Normalize plugins: auto-instantiate Plugin subclasses, reject bad values.
        self._normalize_plugins()

        # Normalize disable_plugins: convert strings and Plugin subclasses to instances.
        self._normalize_disable_plugins()

        # Append any plugins declared via the REFLEX_EXTRA_PLUGINS env var (honoring
        # disable_plugins, which is normalized above).
        self._add_extra_plugins()

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

        # Publish for State-class creation so it never re-enters get_config()
        # (which AttributeErrors if a State is defined while rxconfig.py is mid-import).
        global _state_auto_setters
        _state_auto_setters = self.state_auto_setters

        if (
            self.state_manager_mode == constants.StateManagerMode.REDIS
            and not self.redis_url
        ):
            msg = f"{self._prefixes[0]}REDIS_URL is required when using the redis state manager."
            raise ConfigError(msg)

        allowed_color_modes = constants.LiteralColorMode.__args__
        if self.default_color_mode not in allowed_color_modes:
            msg = (
                f"default_color_mode must be one of "
                f"{allowed_color_modes}, but got {self.default_color_mode!r}."
            )
            raise ConfigError(msg)

    def _normalize_plugins(self):
        """Normalize ``plugins`` entries to Plugin instances.

        Auto-instantiates Plugin subclasses passed without parentheses (e.g.
        ``plugins=[SitemapPlugin]``) so they behave the same as
        ``plugins=[SitemapPlugin()]``. Any entry that is neither a Plugin
        subclass nor a Plugin instance raises ``ConfigError`` with a message
        that names the offending value, instead of failing later in the
        compiler with a confusing ``TypeError`` about a missing ``self``.

        An ``_InvalidPlugin`` (produced when a ``REFLEX_PLUGINS`` import path
        cannot be resolved) is fatal here: ``plugins`` is an explicit list of
        plugins the app needs, so a bad entry raises ``InvalidPluginConfigError``
        and the app cannot start.

        Raises:
            ConfigError: If an entry is neither a Plugin instance nor subclass.
            InvalidPluginConfigError: If an entry could not be loaded.
        """
        normalized: list[Plugin] = []
        invalid: list[_InvalidPlugin] = []
        for entry in self.plugins:
            if isinstance(entry, _InvalidPlugin):
                invalid.append(entry)
            elif isinstance(entry, Plugin):
                normalized.append(entry)
            elif isinstance(entry, type) and issubclass(entry, Plugin):
                try:
                    normalized.append(entry())
                except TypeError as exc:
                    msg = (
                        f"reflex.Config.plugins entry {entry.__name__!r} could not be "
                        f"instantiated and may require arguments; pass an instance "
                        f"instead, e.g. plugins=[{entry.__name__}(...)]."
                    )
                    raise InvalidPluginConfigError(msg) from exc
            else:
                msg = (
                    f"reflex.Config.plugins must contain Plugin instances, but got "
                    f"{entry!r} of type {type(entry).__name__}. "
                    f"Pass an instance, e.g. plugins=[SitemapPlugin()]."
                )
                raise InvalidPluginConfigError(msg)
        if invalid:
            details = ", ".join(p.describe() for p in invalid)
            msg = (
                f"reflex.Config.plugins contains plugin(s) that could not be loaded "
                f"(check REFLEX_PLUGINS import paths): {details}."
            )
            raise InvalidPluginConfigError(msg)
        self.plugins = normalized

    def _add_extra_plugins(self):
        """Append plugins declared via the ``REFLEX_EXTRA_PLUGINS`` env var.

        Unlike ``REFLEX_PLUGINS``, which *replaces* ``plugins`` entirely, this env
        var appends to the existing list so plugins configured in ``rxconfig.py``
        are preserved. Each entry is a fully qualified import path resolved to a
        Plugin *subclass* (not instantiated by the env machinery). For each class:

        - An invalid import path is warned about and skipped (a bad env entry is
          never fatal, since the app still has its configured plugins).
        - A type listed in ``disable_plugins`` is skipped *without* instantiating
          it, so a disabled plugin never runs its constructor.
        - A type already present in ``plugins`` is skipped, so a plugin is never
          run twice.
        - Otherwise the class is instantiated and appended; a constructor failure
          is warned about and skipped.
        """
        for plugin_class in environment.REFLEX_EXTRA_PLUGINS.get():
            if isinstance(plugin_class, _InvalidPlugin):
                logger.warning(
                    f"Ignoring invalid REFLEX_EXTRA_PLUGINS entry {plugin_class.describe()}."
                )
                continue
            if any(
                issubclass(plugin_class, disabled) for disabled in self.disable_plugins
            ):
                logger.debug(
                    f"Skipping REFLEX_EXTRA_PLUGINS entry {plugin_class.__name__!r} "
                    "because its type is listed in disable_plugins.",
                )
                continue
            if any(isinstance(existing, plugin_class) for existing in self.plugins):
                continue
            try:
                self.plugins.append(plugin_class())
            except Exception as exc:
                logger.warning(
                    f"Ignoring REFLEX_EXTRA_PLUGINS entry {plugin_class.__name__!r} "
                    f"that could not be instantiated: {exc}"
                )

    def _normalize_disable_plugins(self):
        """Normalize disable_plugins list entries to Plugin subclasses.

        Handles backward compatibility by converting strings (fully qualified
        import paths) and Plugin instances to their associated classes. An
        ``_InvalidPlugin`` (from an unresolvable ``REFLEX_DISABLE_PLUGINS`` import
        path) is warned about and dropped rather than crashing config load.
        """
        normalized: list[type[Plugin]] = []
        for entry in self.disable_plugins:
            if isinstance(entry, _InvalidPlugin):
                logger.warning(
                    f"Ignoring invalid disable_plugins entry {entry.describe()}. "
                    "Check the REFLEX_DISABLE_PLUGINS import path(s)."
                )
            elif isinstance(entry, type) and issubclass(entry, Plugin):
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
                    logger.warning(
                        f"Failed to import plugin from string {entry!r} in disable_plugins. "
                        "Please pass Plugin subclasses directly.",
                    )
            else:
                logger.warning(
                    f"reflex.Config.disable_plugins should contain Plugin subclasses, but got {entry!r}.",
                )
        self.disable_plugins = normalized

    def _normalize_frontend_compression_formats(self):
        """Normalize and validate configured frontend compression formats.

        Raises:
            ConfigError: If an unsupported format name is configured.
        """
        supported = {"brotli", "gzip", "zstd"}
        normalized: list[str] = []
        seen: set[str] = set()
        for format_name in self.frontend_compression_formats:
            name = format_name.strip().lower()
            if not name or name in seen:
                continue
            if name not in supported:
                msg = (
                    f"frontend_compression_formats contains unsupported format "
                    f"{format_name!r}. Expected one of: {', '.join(sorted(supported))}."
                )
                raise ConfigError(msg)
            normalized.append(name)
            seen.add(name)
        self.frontend_compression_formats = normalized

    def _normalize_paths(self):
        """Ensure frontend and backend paths start with a slash if provided."""
        if self.frontend_path and not self.frontend_path.startswith("/"):
            self.frontend_path = f"/{self.frontend_path}"

        if self.backend_path and not self.backend_path.startswith("/"):
            self.backend_path = f"/{self.backend_path}"

    def _add_builtin_plugins(self):
        """Add the builtin plugins to the config."""
        for plugin in _PLUGINS_ENABLED_BY_DEFAULT:
            plugin_name = plugin.__module__ + "." + plugin.__qualname__
            if plugin not in self.disable_plugins:
                if not any(isinstance(p, plugin) for p in self.plugins):
                    logger.warning(
                        f"`{plugin_name}` plugin is enabled by default, but not explicitly added to the config. "
                        "If you want to use it, please add it to the `plugins` list in your config inside of `rxconfig.py`. "
                        f"To disable this plugin, add `{plugin.__name__}` to the `disable_plugins` list.",
                    )
                    self.plugins.append(plugin())
            else:
                if any(isinstance(p, plugin) for p in self.plugins):
                    logger.warning(
                        f"`{plugin_name}` is disabled in the config, but it is still present in the `plugins` list. "
                        "Please remove it from the `plugins` list in your config inside of `rxconfig.py`.",
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
        """The app module if `app_module_import` is set.

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
        """The module name of the app.

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
                    logger.debug(
                        f"Overriding config value {field.name} with env var {field.name.upper()}={environment_variable}",
                        extra={"dedupe": True},
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


# Project-local modules first imported while loading rxconfig.py; evicted
# before the next load so projects don't reuse each other's dependencies.
# Only mutated under _load_config_lock.
_config_module_deps: set[str] = set()


class _ImportRecorder:
    """Meta-path finder that records import attempts made on one thread.

    Never resolves anything. Recording per thread keeps imports other threads
    happen to make during the window out of the rxconfig dep set, which a plain
    sys.modules diff cannot tell apart from rxconfig's own imports.
    """

    def __init__(self) -> None:
        """Initialize the recorder as inactive."""
        self._thread: int | None = None
        self.names: set[str] = set()

    def start(self) -> None:
        """Start recording imports made on the current thread."""
        self.names.clear()
        self._thread = threading.get_ident()

    def stop(self) -> None:
        """Stop recording; names stay readable."""
        self._thread = None

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> None:
        """Record the import attempt without resolving it.

        Args:
            fullname: The module being imported.
            path: Unused.
            target: Unused.
        """
        if self._thread is not None and self._thread == threading.get_ident():
            self.names.add(fullname)


_import_recorder = _ImportRecorder()


@contextmanager
def _record_imports() -> Iterator[_ImportRecorder]:
    """Record imports made on the current thread while rxconfig loads.

    Yields:
        The recorder, readable after the block.
    """
    # Installed in place and never removed. Both ways of taking it back out are
    # unsafe: importlib._find_spec iterates the list object it read from
    # sys.meta_path (it only copies it since 3.14), so an in-place removal can
    # make a concurrent lookup skip a real finder, and rebinding the list drops
    # whatever another thread inserted meanwhile — reflex.components installs a
    # redirect finder on first import, and losing it is permanent.
    if _import_recorder not in sys.meta_path:
        sys.meta_path.insert(0, _import_recorder)
    _import_recorder.start()
    try:
        yield _import_recorder
    finally:
        _import_recorder.stop()


# Protect sys.path from concurrent modification during config loading.
_load_config_lock = threading.RLock()

# Cached state_auto_setters so State-class creation never re-enters get_config().
_state_auto_setters: bool | None = None


def get_state_auto_setters() -> bool:
    """Return whether state auto-setters are enabled, without importing rxconfig.

    Reads the value cached when the Config was built. Before any Config exists
    (e.g. a State defined inside rxconfig.py during its import), falls back to the
    REFLEX_STATE_AUTO_SETTERS env var, then the default (False). This never calls
    get_config() or imports rxconfig, so it cannot re-enter config loading.

    Returns:
        Whether state auto-setters are enabled.
    """
    if _state_auto_setters is not None:
        return _state_auto_setters
    env_val = os.environ.get(Config._prefixes[0] + "STATE_AUTO_SETTERS")
    if env_val and env_val.strip():
        return interpret_env_var_value(env_val, bool, "state_auto_setters")
    return False


def _get_config(project_root: Path | None = None) -> Config:
    """Import rxconfig.py fresh from the project root and return its config.

    The project root is prepended to sys.path for the duration of the import so
    rxconfig.py and its project-local imports resolve ahead of installed
    packages. Prepending (not replacing sys.path) keeps concurrent imports in
    other threads working.

    Args:
        project_root: Directory to load the config from. Defaults to the
            current working directory, resolved once up front so an rxconfig.py
            that changes the cwd cannot move the root that the sys.path entry
            and the dependency classification below are based on.

    Returns:
        The app config.
    """
    project_root = (project_root or Path.cwd()).resolve()
    with _load_config_lock:
        # A fresh str object, so the exact inserted entry can be removed by
        # identity: rxconfig.py may itself add or remove equal cwd entries,
        # which removal by value could confuse with caller-owned ones.
        cwd = str(project_root)
        sys.path.insert(0, cwd)
        try:
            # Never cache rxconfig or its project-local dependencies — each load
            # goes to disk so different RegistrationContexts hold independent
            # Config instances resolved against the current project. Evict
            # before probing: find_spec answers from sys.modules, so modules
            # left behind by another project directory would fake the existence
            # check below.
            sys.modules.pop(constants.Config.MODULE, None)
            for dep in _config_module_deps:
                sys.modules.pop(dep, None)
            _config_module_deps.clear()
            # only import the module if it exists. If a module spec exists then
            # the module exists.
            if not find_spec(constants.Config.MODULE):
                # we need this condition to ensure that a ModuleNotFound error is not thrown when
                # running unit/integration tests or during `reflex init`.
                return Config(app_name="", _skip_plugins_checks=True)
            with _record_imports() as recorder:
                try:
                    rxconfig = importlib.import_module(constants.Config.MODULE)
                finally:
                    # Record even on failure so a retry evicts partially-imported deps.
                    for name in recorder.names:
                        origin = getattr(sys.modules.get(name), "__file__", None)
                        if (
                            origin
                            and (path := Path(origin)).is_relative_to(project_root)
                            and "site-packages" not in path.parts
                        ):
                            _config_module_deps.add(name)
            return rxconfig.config
        finally:
            for i, entry in enumerate(sys.path):
                if entry is cwd:
                    del sys.path[i]
                    break


if TYPE_CHECKING:
    from typing_extensions import deprecated

    @deprecated("Use _get_config() to load a config, or get_config() to read it")
    def _load_config() -> Config: ...

else:

    def _load_config() -> Config:
        """Load the config for the current working directory (deprecated).

        Returns:
            The app config.
        """
        console.deprecate(
            feature_name="_load_config()",
            reason="Use _get_config() to load a config from disk, or get_config() to read the config cached on the current RegistrationContext",
            deprecation_version="0.9.9.post1",
            removal_version="1.0",
        )
        return _get_config()


def get_config(reload: bool = False) -> Config:
    """Get the app config from the current RegistrationContext.

    The config is loaded from rxconfig.py once per RegistrationContext and
    cached on the context thereafter. If no context is currently attached,
    one is created and attached automatically.

    Args:
        reload: Deprecated; force a fresh load of the config. Use
            reload_config() instead.

    Returns:
        The app config.
    """
    if reload:
        console.deprecate(
            feature_name="get_config(reload=True)",
            reason="Use reload_config() to force a fresh load of the config",
            deprecation_version="0.9.9",
            removal_version="1.0",
        )
        with _load_config_lock:
            return reload_config()
    ctx = RegistrationContext.ensure_context()
    if ctx._config is None:
        # Serialize check/load/set so threads sharing a context load once.
        with _load_config_lock:
            if ctx._config is None:
                ctx._set_config(_get_config())
    return ctx.config


def reload_config() -> Config:
    """Force a fresh load of the config into the current RegistrationContext.

    Clears any cached config on the current context and reloads rxconfig.py
    from disk.

    Returns:
        The freshly loaded app config.
    """
    ctx = RegistrationContext.ensure_context()
    config = _get_config()
    ctx._set_config(config)
    return config
