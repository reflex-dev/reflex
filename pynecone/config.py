"""The Pynecone config."""

from typing import List, Optional

from pynecone import constants
from pynecone.base import Base


class Config(Base):
    """A Pynecone config."""

    # The name of the app.
    app_name: str

    # The username.
    username: Optional[str] = None

    # The frontend port.
    port: str = constants.FRONTEND_PORT

    # The backend API url.
    api_url: str = constants.API_URL

    # The database url.
    db_url: Optional[str] = constants.DB_URL

    # The redis url.
    redis_url: Optional[str] = None

    # The deploy url.
    deploy_url: Optional[str] = None

    # The environment mode.
    env: constants.Env = constants.Env.DEV

    # The path to the bun executable.
    bun_path: str = constants.BUN_PATH

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
