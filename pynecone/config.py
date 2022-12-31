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
    db_url: str = constants.DB_URL

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
