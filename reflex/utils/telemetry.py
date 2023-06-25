"""Anonymous telemetry for Reflex."""

import json
import multiprocessing
import platform
from datetime import datetime

import httpx
import psutil

from reflex import constants
from reflex.base import Base


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
    return constants.VERSION


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
    """Anonymous telemetry for Reflex."""

    user_os: str = get_os()
    cpu_count: int = get_cpu_count()
    memory: int = get_memory()
    reflex_version: str = get_reflex_version()
    python_version: str = get_python_version()


def send(event: str, telemetry_enabled: bool) -> None:
    """Send anonymous telemetry for Reflex.

    Args:
        event: The event name.
        telemetry_enabled: Whether to send the telemetry.
    """
    try:
        if telemetry_enabled:
            telemetry = Telemetry()
            with open(constants.REFLEX_JSON) as f:  # type: ignore
                reflex_json = json.load(f)
                distinct_id = reflex_json["project_hash"]
            post_hog = {
                "api_key": "phc_JoMo0fOyi0GQAooY3UyO9k0hebGkMyFJrrCw1Gt5SGb",
                "event": event,
                "properties": {
                    "distinct_id": distinct_id,
                    "user_os": telemetry.user_os,
                    "reflex_version": telemetry.reflex_version,
                    "python_version": telemetry.python_version,
                    "cpu_count": telemetry.cpu_count,
                    "memory": telemetry.memory,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
            httpx.post("https://app.posthog.com/capture/", json=post_hog)
    except Exception:
        pass
