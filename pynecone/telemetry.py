"""Anonymous telemetry for Pynecone."""

import platform
import psutil
import multiprocessing
from typing import Dict

from pynecone import constants

# Helper functions for telemetry.
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


def get_cpu_count() -> int:
    """Get the number of CPUs.

    Returns:
        The number of CPUs.
    """
    return multiprocessing.cpu_count()


def add_telemetry() -> Dict:
    """Add telemetry to an event.

    Returns:
        The payload with telemetry added.
    """
    payload = {}
    payload["os"] = get_os()
    payload["cpu_count"] = get_cpu_count()
    # Display memory in MB.
    payload["memory"] = psutil.virtual_memory().total >> 20
    payload["pynecone_version"] = constants.VERSION
    payload["python_version"] = get_python_version()
    return payload
