"""Anonymous telemetry for Reflex."""

from __future__ import annotations

import json
import multiprocessing
import platform
from datetime import datetime

import psutil

from reflex import constants
from reflex.utils.prerequisites import ensure_reflex_installation_id

POSTHOG_API_URL: str = "https://app.posthog.com/capture/"


def get_os() -> str:
    """Get the operating system.

    Returns:
        The operating system.
    """
    return platform.system()


def get_python_version() -> str:
    """Get the Python version.

    Returns:
        The Python version.
    """
    return platform.python_version()


def get_reflex_version() -> str:
    """Get the Reflex version.

    Returns:
        The Reflex version.
    """
    return constants.Reflex.VERSION


def get_cpu_count() -> int:
    """Get the number of CPUs.

    Returns:
        The number of CPUs.
    """
    return multiprocessing.cpu_count()


def get_memory() -> int:
    """Get the total memory in MB.

    Returns:
        The total memory in MB.
    """
    return psutil.virtual_memory().total >> 20


def send(event: str, telemetry_enabled: bool | None = None) -> bool:
    """Send anonymous telemetry for Reflex.

    Args:
        event: The event name.
        telemetry_enabled: Whether to send the telemetry (If None, get from config).

    Returns:
        Whether the telemetry was sent successfully.
    """
    import httpx

    from reflex.config import get_config

    # Get the telemetry_enabled from the config if it is not specified.
    if telemetry_enabled is None:
        telemetry_enabled = get_config().telemetry_enabled

    # Return if telemetry is disabled.
    if not telemetry_enabled:
        return False

    installation_id = ensure_reflex_installation_id()
    if installation_id is None:
        return False

    try:
        with open(constants.Dirs.REFLEX_JSON) as f:
            reflex_json = json.load(f)
            project_hash = reflex_json["project_hash"]
        post_hog = {
            "api_key": "phc_JoMo0fOyi0GQAooY3UyO9k0hebGkMyFJrrCw1Gt5SGb",
            "event": event,
            "properties": {
                "distinct_id": installation_id,
                "distinct_app_id": project_hash,
                "user_os": get_os(),
                "reflex_version": get_reflex_version(),
                "python_version": get_python_version(),
                "cpu_count": get_cpu_count(),
                "memory": get_memory(),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        httpx.post(POSTHOG_API_URL, json=post_hog)
        return True
    except Exception:
        return False
