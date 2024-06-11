"""Anonymous telemetry for Reflex."""

from __future__ import annotations

import asyncio
import multiprocessing
import platform
import warnings

try:
    from datetime import UTC, datetime
except ImportError:
    from datetime import datetime

    UTC = None

import httpx
import psutil

from reflex import constants
from reflex.utils import console
from reflex.utils.exec import should_skip_compile
from reflex.utils.prerequisites import ensure_reflex_installation_id, get_project_hash

POSTHOG_API_URL: str = "https://app.posthog.com/capture/"


def get_os() -> str:
    """Get the operating system.

    Returns:
        The operating system.
    """
    return platform.system()


def get_detailed_platform_str() -> str:
    """Get the detailed os/platform string.

    Returns:
        The platform string
    """
    return platform.platform()


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
    try:
        return psutil.virtual_memory().total >> 20
    except ValueError:  # needed to pass ubuntu test
        return 0


def _raise_on_missing_project_hash() -> bool:
    """Check if an error should be raised when project hash is missing.

    When running reflex with --backend-only, or doing database migration
    operations, there is no requirement for a .web directory, so the reflex.json
    file may not exist, and this should not be considered an error.

    Returns:
        False when compilation should be skipped (i.e. no .web directory is required).
        Otherwise return True.
    """
    if should_skip_compile():
        return False
    return True


def _prepare_event(event: str, **kwargs) -> dict:
    """Prepare the event to be sent to the PostHog server.

    Args:
        event: The event name.
        kwargs: Additional data to send with the event.

    Returns:
        The event data.
    """
    from reflex.utils.prerequisites import get_cpu_info

    installation_id = ensure_reflex_installation_id()
    project_hash = get_project_hash(raise_on_fail=_raise_on_missing_project_hash())

    if installation_id is None or project_hash is None:
        console.debug(
            f"Could not get installation_id or project_hash: {installation_id}, {project_hash}"
        )
        return {}

    if UTC is None:
        # for python 3.8, 3.9 & 3.10
        stamp = datetime.utcnow().isoformat()
    else:
        # for python 3.11 & 3.12
        stamp = datetime.now(UTC).isoformat()

    cpuinfo = get_cpu_info()

    additional_keys = ["template", "context", "detail"]
    additional_fields = {
        key: value for key in additional_keys if (value := kwargs.get(key)) is not None
    }
    return {
        "api_key": "phc_JoMo0fOyi0GQAooY3UyO9k0hebGkMyFJrrCw1Gt5SGb",
        "event": event,
        "properties": {
            "distinct_id": installation_id,
            "distinct_app_id": project_hash,
            "user_os": get_os(),
            "user_os_detail": get_detailed_platform_str(),
            "reflex_version": get_reflex_version(),
            "python_version": get_python_version(),
            "cpu_count": get_cpu_count(),
            "memory": get_memory(),
            "cpu_info": dict(cpuinfo) if cpuinfo else {},
            **additional_fields,
        },
        "timestamp": stamp,
    }


def _send_event(event_data: dict) -> bool:
    try:
        httpx.post(POSTHOG_API_URL, json=event_data)
        return True
    except Exception:
        return False


def _send(event, telemetry_enabled, **kwargs):
    from reflex.config import get_config

    # Get the telemetry_enabled from the config if it is not specified.
    if telemetry_enabled is None:
        telemetry_enabled = get_config().telemetry_enabled

    # Return if telemetry is disabled.
    if not telemetry_enabled:
        return False

    event_data = _prepare_event(event, **kwargs)
    if not event_data:
        return False
    return _send_event(event_data)


def send(event: str, telemetry_enabled: bool | None = None, **kwargs):
    """Send anonymous telemetry for Reflex.

    Args:
        event: The event name.
        telemetry_enabled: Whether to send the telemetry (If None, get from config).
        kwargs: Additional data to send with the event.
    """

    async def async_send(event, telemetry_enabled, **kwargs):
        return _send(event, telemetry_enabled, **kwargs)

    try:
        # Within an event loop context, send the event asynchronously.
        asyncio.create_task(async_send(event, telemetry_enabled, **kwargs))
    except RuntimeError:
        # If there is no event loop, send the event synchronously.
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        _send(event, telemetry_enabled, **kwargs)


def send_error(error: Exception, context: str):
    """Send an error event.

    Args:
        error: The error to send.
        context: The context of the error (e.g. "frontend" or "backend")

    Returns:
        Whether the telemetry was sent successfully.
    """
    return send("error", detail=type(error).__name__, context=context)
