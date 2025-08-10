"""Anonymous telemetry for Reflex."""

from __future__ import annotations

import asyncio
import dataclasses
import importlib.metadata
import multiprocessing
import platform
import warnings
from contextlib import suppress
from datetime import datetime, timezone
from typing import TypedDict

from reflex import constants
from reflex.environment import environment
from reflex.utils import console
from reflex.utils.decorator import once_unless_none
from reflex.utils.exceptions import ReflexError
from reflex.utils.prerequisites import (
    ensure_reflex_installation_id,
    get_bun_version,
    get_node_version,
    get_project_hash,
)

UTC = timezone.utc
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
    # Remove the "+" from the version string in case user is using a pre-release version.
    return platform.python_version().rstrip("+")


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


def get_reflex_enterprise_version() -> str | None:
    """Get the version of reflex-enterprise if installed.

    Returns:
        The version string if installed, None if not installed.
    """
    try:
        return importlib.metadata.version("reflex-enterprise")
    except importlib.metadata.PackageNotFoundError:
        return None


def _raise_on_missing_project_hash() -> bool:
    """Check if an error should be raised when project hash is missing.

    When running reflex with --backend-only, or doing database migration
    operations, there is no requirement for a .web directory, so the reflex.json
    file may not exist, and this should not be considered an error.

    Returns:
        False when compilation should be skipped (i.e. no .web directory is required).
        Otherwise return True.
    """
    return not environment.REFLEX_SKIP_COMPILE.get()


class _Properties(TypedDict):
    """Properties type for telemetry."""

    distinct_id: int
    distinct_app_id: int
    user_os: str
    user_os_detail: str
    reflex_version: str
    python_version: str
    node_version: str | None
    bun_version: str | None
    reflex_enterprise_version: str | None
    cpu_count: int
    cpu_info: dict


class _DefaultEvent(TypedDict):
    """Default event type for telemetry."""

    api_key: str
    properties: _Properties


class _Event(_DefaultEvent):
    """Event type for telemetry."""

    event: str
    timestamp: str


def _get_event_defaults() -> _DefaultEvent | None:
    """Get the default event data.

    Returns:
        The default event data.
    """
    from reflex.utils.prerequisites import get_cpu_info

    installation_id = ensure_reflex_installation_id()
    project_hash = get_project_hash(raise_on_fail=_raise_on_missing_project_hash())

    if installation_id is None or project_hash is None:
        console.debug(
            f"Could not get installation_id or project_hash: {installation_id}, {project_hash}"
        )
        return None

    cpuinfo = get_cpu_info()

    return {
        "api_key": "phc_JoMo0fOyi0GQAooY3UyO9k0hebGkMyFJrrCw1Gt5SGb",
        "properties": {
            "distinct_id": installation_id,
            "distinct_app_id": project_hash,
            "user_os": get_os(),
            "user_os_detail": get_detailed_platform_str(),
            "reflex_version": get_reflex_version(),
            "python_version": get_python_version(),
            "node_version": (
                str(node_version) if (node_version := get_node_version()) else None
            ),
            "bun_version": (
                str(bun_version) if (bun_version := get_bun_version()) else None
            ),
            "reflex_enterprise_version": get_reflex_enterprise_version(),
            "cpu_count": get_cpu_count(),
            "cpu_info": dataclasses.asdict(cpuinfo) if cpuinfo else {},
        },
    }


@once_unless_none
def get_event_defaults() -> _DefaultEvent | None:
    """Get the default event data.

    Returns:
        The default event data.
    """
    return _get_event_defaults()


def _prepare_event(event: str, **kwargs) -> _Event | None:
    """Prepare the event to be sent to the PostHog server.

    Args:
        event: The event name.
        kwargs: Additional data to send with the event.

    Returns:
        The event data.
    """
    event_data = get_event_defaults()
    if not event_data:
        return None

    additional_keys = ["template", "context", "detail", "user_uuid"]

    properties = event_data["properties"]

    for key in additional_keys:
        if key in properties or key not in kwargs:
            continue

        properties[key] = kwargs[key]

    stamp = datetime.now(UTC).isoformat()

    return {
        "api_key": event_data["api_key"],
        "event": event,
        "properties": properties,
        "timestamp": stamp,
    }


def _send_event(event_data: _Event) -> bool:
    import httpx

    try:
        httpx.post(POSTHOG_API_URL, json=event_data)
    except Exception:
        return False
    else:
        return True


def _send(event: str, telemetry_enabled: bool | None, **kwargs) -> bool:
    from reflex.config import get_config

    # Get the telemetry_enabled from the config if it is not specified.
    if telemetry_enabled is None:
        telemetry_enabled = get_config().telemetry_enabled

    # Return if telemetry is disabled.
    if not telemetry_enabled:
        return False

    with suppress(Exception):
        event_data = _prepare_event(event, **kwargs)
        if not event_data:
            return False
        return _send_event(event_data)
    return False


background_tasks = set()


def send(event: str, telemetry_enabled: bool | None = None, **kwargs):
    """Send anonymous telemetry for Reflex.

    Args:
        event: The event name.
        telemetry_enabled: Whether to send the telemetry (If None, get from config).
        kwargs: Additional data to send with the event.
    """

    async def async_send(event: str, telemetry_enabled: bool | None, **kwargs):
        return _send(event, telemetry_enabled, **kwargs)

    try:
        # Within an event loop context, send the event asynchronously.
        task = asyncio.create_task(async_send(event, telemetry_enabled, **kwargs))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
    except RuntimeError:
        # If there is no event loop, send the event synchronously.
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        _send(event, telemetry_enabled, **kwargs)


def send_error(error: Exception, context: str):
    """Send an error event.

    Args:
        error: The error to send.
        context: The context of the error (e.g. "frontend" or "backend")
    """
    if isinstance(error, ReflexError):
        send("error", detail=type(error).__name__, context=context)
