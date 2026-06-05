"""Config constants."""

from pathlib import Path
from types import SimpleNamespace

from reflex_base.constants.base import Dirs, Reflex

from .compiler import Ext

# Alembic migrations
ALEMBIC_CONFIG = "alembic.ini"


class Config(SimpleNamespace):
    """Config constants."""

    # The name of the reflex config module.
    MODULE = "rxconfig"
    # The python config file.
    FILE = Path(f"{MODULE}{Ext.PY}")


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


class AgentsMd(SimpleNamespace):
    """AGENTS.md constants."""

    # The AGENTS.md file written to the app root.
    FILE = Path("AGENTS.md")
    # The canonical AGENTS.md maintained in the reflex-dev/agent-skills repo.
    CANONICAL_URL = (
        "https://raw.githubusercontent.com/reflex-dev/agent-skills/main/AGENTS.md"
    )


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


class UvLock(SimpleNamespace):
    """uv.lock constants."""

    # The uv lockfile.
    FILE = "uv.lock"


class DefaultPorts(SimpleNamespace):
    """Default port constants."""

    FRONTEND_PORT = 3000
    BACKEND_PORT = 8000


# The deployment URL.
PRODUCTION_BACKEND_URL = "https://{username}-{app_name}.api.pynecone.app"
