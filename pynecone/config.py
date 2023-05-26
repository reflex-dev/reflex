"""The Pynecone config."""

from __future__ import annotations

import importlib
import os
import sys
import urllib.parse
from typing import List, Optional

from dotenv import load_dotenv

from pynecone import constants
from pynecone.base import Base


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
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = 5432,
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
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = 5432,
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
    """A Pynecone config."""

    # The name of the app.
    app_name: str

    # The username.
    username: Optional[str] = None

    @property
    def port(self) -> Optional[str]:
        """The frontend port."""
        return constants.FRONTEND_PORT

    @property
    def backend_host(self) -> str:
        """The backend host."""
        return constants.BACKEND_HOST

    @property
    def backend_port(self) -> Optional[str]:
        """The backend port."""
        return constants.BACKEND_PORT

    @property
    def api_url(self) -> Optional[str]:
        """The backend API url."""
        return constants.API_URL

    @property
    def deploy_url(self) -> Optional[str]:
        """The deploy url."""
        return constants.DEPLOY_URL

    @property
    def db_url(self) -> Optional[str]:
        """the database url."""
        return constants.DB_URL

    # The database config.
    db_config: Optional[DBConfig] = None

    @property
    def redis_url(self) -> Optional[str]:
        """The redis url."""
        return constants.REDIS_URL

    # Telemetry opt-in.
    telemetry_enabled: bool = True

    # The pcdeploy url.
    pcdeploy_url: Optional[str] = None

    # The environment mode.
    env: constants.Env = constants.Env.DEV

    # The path to the bun executable.
    bun_path: str = constants.BUN_PATH

    # Disable bun.
    disable_bun: bool = False

    # Additional frontend packages to install.
    frontend_packages: List[str] = []

    # Backend transport methods.
    backend_transports: Optional[
        constants.Transports
    ] = constants.Transports.WEBSOCKET_POLLING

    # List of origins that are allowed to connect to the backend API.
    cors_allowed_origins: Optional[list] = [constants.CORS_ALLOWED_ORIGINS]

    # Whether credentials (cookies, authentication) are allowed in requests to the backend API.
    cors_credentials: Optional[bool] = True

    # The maximum size of a message when using the polling backend transport.
    polling_max_http_buffer_size: Optional[int] = constants.POLLING_MAX_HTTP_BUFFER_SIZE

    # dotenv file path
    env_path: Optional[str] = constants.DOT_ENV_FILE

    # Whether to override OS environment variables
    override_os_envs: Optional[bool] = True

    def __init__(self, *args, **kwargs):
        """Initialize the config values.

        If db_url is not provided gets it from db_config.

        Args:
            *args: The args to pass to the Pydantic init method.
            **kwargs: The kwargs to pass to the Pydantic init method.
        """
        if "db_url" not in kwargs and "db_config" in kwargs:
            kwargs["db_url"] = kwargs["db_config"].get_url()
        super().__init__(*args, **kwargs)

        # load env variables from env file
        load_dotenv(self.env_path, override=self.override_os_envs)

        # recompute constants after load env variables
        importlib.reload(constants)


def get_config() -> Config:
    """Get the app config.

    Returns:
        The app config.
    """
    from pynecone.config import Config

    sys.path.append(os.getcwd())
    try:
        const_imports = __import__(constants.CONFIG_MODULE).config

        return const_imports
    except ImportError:
        return Config(app_name="")  # type: ignore
