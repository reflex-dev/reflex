"""Config constants."""
import os
from types import SimpleNamespace

from reflex.constants.base import Dirs, Reflex

from .compiler import Ext

# Alembic migrations
ALEMBIC_CONFIG = os.environ.get("ALEMBIC_CONFIG", "alembic.ini")


class Config(SimpleNamespace):
    """Config constants."""

    # The name of the reflex config module.
    MODULE = "rxconfig"
    # The python config file.
    FILE = f"{MODULE}{Ext.PY}"
    # The previous config file.
    PREVIOUS_FILE = f"pcconfig{Ext.PY}"


class Expiration(SimpleNamespace):
    """Expiration constants."""

    # Token expiration time in seconds
    TOKEN = 60 * 60
    # Maximum time in milliseconds that a state can be locked for exclusive access.
    LOCK = 10000
    # The PING timeout
    PING = 120


class GitIgnore(SimpleNamespace):
    """Gitignore constants."""

    # The gitignore file.
    FILE = ".gitignore"
    # Files to gitignore.
    DEFAULTS = {Dirs.WEB, "*.db", "__pycache__/", "*.py[cod]"}


class RequirementsTxt(SimpleNamespace):
    """Requirements.txt constants."""

    # The requirements.txt file.
    FILE = "requirements.txt"
    # The partial text used to form requirement that pins a reflex version
    DEFAULTS_STUB = f"{Reflex.MODULE_NAME}=="


class DefaultPorts(SimpleNamespace):
    """Default port constants."""

    FRONTEND_PORT = 3000
    BACKEND_PORT = 8000


# The deployment URL.
PRODUCTION_BACKEND_URL = "https://{username}-{app_name}.api.pynecone.app"
