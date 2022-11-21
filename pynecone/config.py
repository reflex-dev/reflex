from typing import Optional

from pynecone import constants
from pynecone.base import Base


class Config(Base):
    """A Pynecone config."""

    # The name of the app.
    app_name: str

    # The backend API url.
    api_url: str = "http://localhost:8000"

    # The database url.
    db_url: str = f"sqlite:///{constants.DB_NAME}"

    # The redis url.
    redis_url: Optional[str] = None

    # The deploy url.
    deploy_url: Optional[str] = None

    # The environment mode.
    env: constants.Env = constants.Env.DEV

    # The path to the bun executable.
    bun_path: str = "$HOME/.bun/bin/bun"
