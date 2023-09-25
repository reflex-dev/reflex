"""Config constants."""
import os
from types import SimpleNamespace

from reflex.constants.base import DIRS

from .compiler import EXT

# Alembic migrations
ALEMBIC_CONFIG = os.environ.get("ALEMBIC_CONFIG", "alembic.ini")


class CONFIG(SimpleNamespace):
    """Config constants."""

    # The name of the reflex config module.
    MODULE = "rxconfig"
    # The python config file.
    FILE = f"{MODULE}{EXT.PY}"
    # The previous config file.
    PREVIOUS_FILE = f"pcconfig{EXT.PY}"


class EXPIRATION(SimpleNamespace):
    """Expiration constants."""

    # Token expiration time in seconds
    TOKEN = 60 * 60
    # Maximum time in milliseconds that a state can be locked for exclusive access.
    LOCK = 10000
    # The PING timeout
    PING = 120


class GITIGNORE(SimpleNamespace):
    """Gitignore constants."""

    # The gitignore file.
    FILE = ".gitignore"
    # Files to gitignore.
    DEFAULTS = {DIRS.WEB, "*.db", "__pycache__/", "*.py[cod]"}


# The deployment URL.
PRODUCTION_BACKEND_URL = "https://{username}-{app_name}.api.pynecone.app"
