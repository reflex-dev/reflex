"""Config constants."""
import os
from types import SimpleNamespace

from nextpy.constants.base import Dirs, Nextpy

from .compiler import Ext

# Alembic migrations
ALEMBIC_CONFIG = os.environ.get("ALEMBIC_CONFIG", "alembic.ini")


class Config(SimpleNamespace):
    """Config constants."""

    # The name of the nextpy config module.
    MODULE = "xtconfig"
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
    # The partial text used to form requirement that pins a nextpy version
    DEFAULTS_STUB = f"{Nextpy.MODULE_NAME}=="


# The deployment URL.
PRODUCTION_BACKEND_URL = "https://{username}-{app_name}.api.dotagent.app"
