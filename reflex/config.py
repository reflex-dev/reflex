"""The Reflex config."""

from __future__ import annotations

import functools
import importlib
import inspect
import os
import sys
import traceback
import urllib.parse
from typing import Any, Callable, Dict, List, Optional, Set, Union

try:
    import pydantic.v1 as pydantic
except ModuleNotFoundError:
    import pydantic

from reflex_cli.constants.hosting import Hosting

from reflex import constants
from reflex.base import Base
from reflex.event import EventSpec, window_alert
from reflex.utils import console


def default_frontend_exception_handler(exception: Exception) -> None:
    """Default frontend exception handler function.

    Args:
        exception: The exception.

    """
    console.error(f"[Reflex Frontend Exception]\n {exception}\n")


def default_backend_exception_handler(exception: Exception) -> EventSpec:
    """Default backend exception handler function.

    Args:
        exception: The exception.

    Returns:
        EventSpec: The window alert event.
    """
    error = traceback.format_exc()

    console.error(f"[Reflex Backend Exception]\n {error}\n")

    return window_alert("An error occurred. See logs for details.")


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
    loglevel: constants.LogLevel = constants.LogLevel.INFO

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
    bun_path: str = constants.Bun.DEFAULT_PATH

    # List of origins that are allowed to connect to the backend API.
    cors_allowed_origins: List[str] = ["*"]

    # Tailwind config.
    tailwind: Optional[Dict[str, Any]] = {}

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

    # Attributes that were explicitly set by the user.
    _non_default_attributes: Set[str] = pydantic.PrivateAttr(set())

    # Frontend Error Handler Function
    frontend_exception_handler: Callable[
        [Exception], None
    ] = default_frontend_exception_handler

    # Backend Error Handler Function
    backend_exception_handler: Callable[
        [Exception], Union[EventSpec, List[EventSpec], None]
    ] = default_backend_exception_handler

    def __init__(self, *args, **kwargs):
        """Initialize the config values.

        Args:
            *args: The args to pass to the Pydantic init method.
            **kwargs: The kwargs to pass to the Pydantic init method.
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

        # Check the exception handlers
        self._validate_exception_handlers()

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
                        f"Overriding config value {key} with env var {key.upper()}={env_var}"
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

    def _validate_exception_handlers(self):
        """Validate the custom event exception handlers for front- and backend.

        Raises:
            ValueError: If the custom exception handlers are invalid.

        """
        FRONTEND_ARG_SPEC = {
            "exception": Exception,
        }

        BACKEND_ARG_SPEC = {
            "exception": Exception,
        }

        for handler_domain, handler_fn, handler_spec in zip(
            ["frontend", "backend"],
            [self.frontend_exception_handler, self.backend_exception_handler],
            [
                FRONTEND_ARG_SPEC,
                BACKEND_ARG_SPEC,
            ],
        ):
            if hasattr(handler_fn, "__name__"):
                _fn_name = handler_fn.__name__
            else:
                _fn_name = handler_fn.__class__.__name__

            if isinstance(handler_fn, functools.partial):
                raise ValueError(
                    f"Provided custom {handler_domain} exception handler `{_fn_name}` is a partial function. Please provide a named function instead."
                )

            if not callable(handler_fn):
                raise ValueError(
                    f"Provided custom {handler_domain} exception handler `{_fn_name}` is not a function."
                )

            # Allow named functions only as lambda functions cannot be introspected
            if _fn_name == "<lambda>":
                raise ValueError(
                    f"Provided custom {handler_domain} exception handler `{_fn_name}` is a lambda function. Please use a named function instead."
                )

            # Check if the function has the necessary annotations and types in the right order
            argspec = inspect.getfullargspec(handler_fn)
            arg_annotations = {
                k: eval(v) if isinstance(v, str) else v
                for k, v in argspec.annotations.items()
                if k not in ["args", "kwargs", "return"]
            }

            for required_arg_index, required_arg in enumerate(handler_spec):
                if required_arg not in arg_annotations:
                    raise ValueError(
                        f"Provided custom {handler_domain} exception handler `{_fn_name}` does not take the required argument `{required_arg}`"
                    )
                elif (
                    not list(arg_annotations.keys())[required_arg_index] == required_arg
                ):
                    raise ValueError(
                        f"Provided custom {handler_domain} exception handler `{_fn_name}` has the wrong argument order."
                        f"Expected `{required_arg}` as the {required_arg_index+1} argument but got `{list(arg_annotations.keys())[required_arg_index]}`"
                    )

                if not issubclass(arg_annotations[required_arg], Exception):
                    raise ValueError(
                        f"Provided custom {handler_domain} exception handler `{_fn_name}` has the wrong type for {required_arg} argument."
                        f"Expected to be `Exception` but got `{arg_annotations[required_arg]}`"
                    )

            # Check if the return type is valid for backend exception handler
            if handler_domain == "backend":
                sig = inspect.signature(self.backend_exception_handler)
                return_type = (
                    eval(sig.return_annotation)
                    if isinstance(sig.return_annotation, str)
                    else sig.return_annotation
                )

                valid = bool(
                    return_type == EventSpec
                    or return_type == Optional[EventSpec]
                    or return_type == List[EventSpec]
                    or return_type == inspect.Signature.empty
                    or return_type is None
                )

                if not valid:
                    raise ValueError(
                        f"Provided custom {handler_domain} exception handler `{_fn_name}` has the wrong return type."
                        f"Expected `Union[EventSpec, List[EventSpec], None]` but got `{return_type}`"
                    )


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
