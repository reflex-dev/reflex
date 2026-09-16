"""Access to the credentials saved by ``reflex login``."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from platformdirs import PlatformDirs

logger = logging.getLogger(__name__)


def credentials_path() -> Path:
    """Get the path of the file ``reflex login`` saves the access token to.

    Returns:
        The path of the hosting config file in the Reflex user data directory.
    """
    return Path(PlatformDirs("reflex", False).user_data_dir) / "hosting_v1.json"


def load_stored_token() -> str | None:
    """Read the access token saved by ``reflex login``.

    Returns:
        The saved token, or None when there is no readable saved token.
    """
    path = credentials_path()
    try:
        config = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as ex:
        logger.debug("Ignoring unreadable credentials file %s: %s", path, ex)
        return None
    token = config.get("access_token") if isinstance(config, dict) else None
    return token if isinstance(token, str) and token else None
