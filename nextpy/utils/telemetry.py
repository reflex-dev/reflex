"""Anonymous telemetry for Nextpy."""

from __future__ import annotations

import json
import multiprocessing
import platform
from datetime import datetime

import httpx
import psutil

from nextpy import constants
from nextpy.core.base import Base
from nextpy.core.config import get_config


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


def get_nextpy_version() -> str:
    """Get the Nextpy version.

    Returns:
        The Nextpy version.
    """
    return constants.Nextpy.VERSION


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


class Telemetry(Base):
    """Anonymous telemetry for Nextpy."""

    user_os: str = get_os()
    cpu_count: int = get_cpu_count()
    memory: int = get_memory()
    nextpy_version: str = get_nextpy_version()
    python_version: str = get_python_version()


def send(event: str, telemetry_enabled: bool | None = None) -> bool:
    """Send anonymous telemetry for Nextpy.

    Args:
        event: The event name.
        telemetry_enabled: Whether to send the telemetry (If None, get from config).

    Returns:
        Whether the telemetry was sent successfully.
    """
    # Get the telemetry_enabled from the config if it is not specified.
    if telemetry_enabled is None:
        telemetry_enabled = get_config().telemetry_enabled

    # Return if telemetry is disabled.
    if not telemetry_enabled:
        return False

    try:
        telemetry = Telemetry()
        with open(constants.Dirs.NEXTPY_JSON) as f:
            nextpy_json = json.load(f)
            distinct_id = nextpy_json["project_hash"]
        post_hog = {
            "api_key": "",
            "event": event,
            "properties": {
                "distinct_id": distinct_id,
                "user_os": telemetry.user_os,
                "nextpy_version": telemetry.nextpy_version,
                "python_version": telemetry.python_version,
                "cpu_count": telemetry.cpu_count,
                "memory": telemetry.memory,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        httpx.post("https://app.posthog.com/capture/", json=post_hog)
        return True
    except Exception:
        return False
