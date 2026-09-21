"""The access token saved on this machine, shared with ``reflex login``.

``ReflexBuild`` and ``AsyncReflexBuild`` use the saved token when neither a
``token`` argument nor ``REFLEX_ACCESS_TOKEN`` gives one.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from platformdirs import PlatformDirs

logger = logging.getLogger(__name__)

_TOKEN_KEY = "access_token"


def credentials_path() -> Path:
    """Get the path of the file the access token is saved in.

    Returns:
        The ``hosting_v1.json`` file in the Reflex user data directory.
    """
    return Path(PlatformDirs("reflex", False).user_data_dir) / "hosting_v1.json"


def _read() -> dict[str, Any] | None:
    """Read the credentials file.

    Returns:
        Its contents, an empty dict if it does not exist, or None if it cannot be
        read as a JSON object.
    """
    path = credentials_path()
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as ex:
        logger.debug("Ignoring unreadable credentials file %s: %s", path, ex)
        return None
    return config if isinstance(config, dict) else None


def _write(config: dict[str, Any]) -> None:
    """Replace the credentials file atomically.

    The file is written beside the target and moved into place, so an interrupted
    write leaves the previous credentials intact.

    Args:
        config: The file contents.
    """
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    temp_path = Path(temp_name)
    try:
        # Closed before the rename: Windows cannot rename an open file.
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(config, file)
            file.flush()
            os.fsync(file.fileno())
        temp_path.replace(path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def load_token() -> str | None:
    """Read the saved access token.

    Returns:
        The token, or None when none is saved or the file cannot be read.
    """
    config = _read()
    token = None if config is None else config.get(_TOKEN_KEY)
    return token if isinstance(token, str) and token else None


def save_token(token: str) -> None:
    """Save an access token, keeping the file's other settings.

    Args:
        token: The access token.

    Raises:
        OSError: If the file cannot be written; the previous file is left intact.
    """
    # An unreadable file holds no usable token, so it is started over.
    config = _read() or {}
    config[_TOKEN_KEY] = token
    _write(config)


def delete_token() -> None:
    """Delete the saved access token, keeping the file's other settings.

    Raises:
        OSError: If the file cannot be written; the previous file is left intact.
    """
    config = _read()
    if config and _TOKEN_KEY in config:
        del config[_TOKEN_KEY]
        _write(config)
