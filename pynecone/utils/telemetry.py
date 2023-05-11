"""Anonymous telemetry for Pynecone."""

import json
import multiprocessing
import platform
from datetime import datetime

import httpx
import psutil

from pynecone import constants
from pynecone.base import Base


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


def get_pynecone_version() -> str:
    """Get the Pynecone version.

    Returns:
        The Pynecone version.
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
    """Anonymous telemetry for Pynecone."""

    user_os: str = get_os()
    cpu_count: int = get_cpu_count()
    memory: int = get_memory()
    pynecone_version: str = get_pynecone_version()
    python_version: str = get_python_version()


def send(event: str, telemetry_enabled: bool) -> None:
    """Send anonymous telemetry for Pynecone.

    Args:
        event: The event name.
        telemetry_enabled: Whether to send the telemetry.
    """
    try:
        if telemetry_enabled:
            telemetry = Telemetry()
            with open(constants.PCVERSION_APP_FILE) as f:  # type: ignore
                pynecone_json = json.load(f)
                distinct_id = pynecone_json["project_hash"]
            post_hog = {
                "api_key": "phc_JoMo0fOyi0GQAooY3UyO9k0hebGkMyFJrrCw1Gt5SGb",
                "event": event,
                "properties": {
                    "distinct_id": distinct_id,
                    "user_os": telemetry.user_os,
                    "pynecone_version": telemetry.pynecone_version,
                    "python_version": telemetry.python_version,
                    "cpu_count": telemetry.cpu_count,
                    "memory": telemetry.memory,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
            httpx.post("https://app.posthog.com/capture/", json=post_hog)
    except Exception:
        pass
