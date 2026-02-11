"""Config constants."""

import os
from pathlib import Path
from types import SimpleNamespace

from reflex.constants.base import Dirs, Reflex

from .compiler import Ext

# Alembic migrations
ALEMBIC_CONFIG = "alembic.ini"

# Default config module name.
_DEFAULT_CONFIG_MODULE = "rxconfig"


def _get_config_module() -> str:
    """Get the config module name from env or default.

    Returns:
        The config module name.
    """
    return os.environ.get("REFLEX_CONFIG_MODULE", _DEFAULT_CONFIG_MODULE)


def _get_config_file() -> Path:
    """Get the config file path from env or derive from module name.

    Returns:
        The config file path.
    """
    env_file = os.environ.get("REFLEX_CONFIG_FILE")
    if env_file:
        return Path(env_file)
    return Path(f"{_get_config_module()}{Ext.PY}")


class _ConfigMeta(type(SimpleNamespace)):
    """Metaclass for Config that makes MODULE and FILE dynamic class attributes."""

    @property
    def MODULE(cls) -> str:  # noqa: N802
        return _get_config_module()

    @property
    def FILE(cls) -> Path:  # noqa: N802
        return _get_config_file()


class Config(SimpleNamespace, metaclass=_ConfigMeta):
    """Config constants."""


class Expiration(SimpleNamespace):
    """Expiration constants."""

    # Token expiration time in seconds
    TOKEN = 60 * 60
    # Maximum time in milliseconds that a state can be locked for exclusive access.
    LOCK = 10000
    # The PING timeout
    PING = 120
    # The maximum time in milliseconds to hold a lock before throwing a warning.
    LOCK_WARNING_THRESHOLD = 1000


class GitIgnore(SimpleNamespace):
    """Gitignore constants."""

    # The gitignore file.
    FILE = Path(".gitignore")
    # Files to gitignore.
    DEFAULTS = {
        Dirs.WEB,
        Dirs.STATES,
        "*.db",
        "__pycache__/",
        "*.py[cod]",
        "assets/external/",
    }


class PyprojectToml(SimpleNamespace):
    """Pyproject.toml constants."""

    # The pyproject.toml file.
    FILE = "pyproject.toml"


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
