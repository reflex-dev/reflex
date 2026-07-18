"""Anonymous telemetry for Reflex."""

import dataclasses
import importlib.metadata
import json
import multiprocessing
import os
import platform
import sys
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict, cast

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.environment import environment
from reflex_base.utils.decorator import once, once_unless_none
from reflex_base.utils.exceptions import ReflexError
from typing_extensions import NotRequired

from reflex.utils import console, processes
from reflex.utils.js_runtimes import get_bun_version, get_node_version
from reflex.utils.prerequisites import (
    ensure_reflex_installation_id,
    get_project_hash,
    has_uuid_distinct_id_semantics,
    mark_uuid_distinct_id_semantics,
)

UTC = timezone.utc
POSTHOG_API_URL: str = "https://app.posthog.com/capture/"


@dataclasses.dataclass(frozen=True)
class CpuInfo:
    """Model to save cpu info."""

    manufacturer_id: str | None
    model_name: str | None
    address_width: int | None


def format_address_width(address_width: str | None) -> int | None:
    """Cast address width to an int.

    Args:
        address_width: The address width.

    Returns:
        Address width int
    """
    try:
        return int(address_width) if address_width else None
    except ValueError:
        return None


def _retrieve_cpu_info() -> CpuInfo | None:
    """Retrieve the CPU info of the host.

    Returns:
        The CPU info.
    """
    platform_os = platform.system()
    cpuinfo = {}
    try:
        if platform_os == "Windows":
            cmd = 'powershell -Command "Get-CimInstance Win32_Processor | Select-Object -First 1 | Select-Object AddressWidth,Manufacturer,Name | ConvertTo-Json"'
            output = processes.execute_command_and_return_output(cmd)
            if output:
                cpu_data = json.loads(output)
                cpuinfo["address_width"] = cpu_data["AddressWidth"]
                cpuinfo["manufacturer_id"] = cpu_data["Manufacturer"]
                cpuinfo["model_name"] = cpu_data["Name"]
        elif platform_os == "Linux":
            output = processes.execute_command_and_return_output("lscpu")
            if output:
                lines = output.split("\n")
                for line in lines:
                    if "Architecture" in line:
                        cpuinfo["address_width"] = (
                            64 if line.split(":")[1].strip() == "x86_64" else 32
                        )
                    if "Vendor ID:" in line:
                        cpuinfo["manufacturer_id"] = line.split(":")[1].strip()
                    if "Model name" in line:
                        cpuinfo["model_name"] = line.split(":")[1].strip()
        elif platform_os == "Darwin":
            cpuinfo["address_width"] = format_address_width(
                processes.execute_command_and_return_output("getconf LONG_BIT")
            )
            cpuinfo["manufacturer_id"] = processes.execute_command_and_return_output(
                "sysctl -n machdep.cpu.brand_string"
            )
            cpuinfo["model_name"] = processes.execute_command_and_return_output(
                "uname -m"
            )
    except Exception as err:
        console.error(f"Failed to retrieve CPU info. {err}")
        return None

    return (
        CpuInfo(
            manufacturer_id=cpuinfo.get("manufacturer_id"),
            model_name=cpuinfo.get("model_name"),
            address_width=cpuinfo.get("address_width"),
        )
        if cpuinfo
        else None
    )


@once
def get_cpu_info() -> CpuInfo | None:
    """Get the CPU info of the underlining host.

    Returns:
        The CPU info.
    """
    cpu_info_file = environment.REFLEX_DIR.get() / "cpu_info.json"
    if cpu_info_file.exists() and (cpu_info := json.loads(cpu_info_file.read_text())):
        return CpuInfo(**cpu_info)
    cpu_info = _retrieve_cpu_info()
    if cpu_info:
        cpu_info_file.parent.mkdir(parents=True, exist_ok=True)
        cpu_info_file.write_text(json.dumps(dataclasses.asdict(cpu_info)))
    return cpu_info


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


def is_in_virtualenv() -> bool:
    """Whether the current Python is running inside a virtual environment.

    Returns:
        True if a virtual environment appears to be active.
    """
    if sys.prefix != sys.base_prefix:
        return True
    return bool(os.environ.get("VIRTUAL_ENV"))


def get_init_environment() -> dict[str, bool]:
    """Return Python tooling flags for the current working directory.

    Returns:
        A dict with ``in_virtualenv``, ``has_pyproject_toml``,
        ``has_requirements_txt``, ``has_uv_lock`` and ``has_reflex_lock``
        boolean flags, or an empty dict when telemetry is disabled (so the
        filesystem stats are skipped when their results would be discarded).
    """
    if not get_config().telemetry_enabled:
        return {}

    return {
        "in_virtualenv": is_in_virtualenv(),
        "has_pyproject_toml": Path(constants.PyprojectToml.FILE).exists(),
        "has_requirements_txt": Path(constants.RequirementsTxt.FILE).exists(),
        "has_uv_lock": Path(constants.UvLock.FILE).exists(),
        "has_reflex_lock": Path(constants.Bun.ROOT_LOCKFILE_DIR).is_dir(),
    }


def get_reflex_enterprise_version() -> str | None:
    """Get the version of reflex-enterprise if installed.

    Returns:
        The version string if installed, None if not installed.
    """
    try:
        return importlib.metadata.version("reflex-enterprise")
    except importlib.metadata.PackageNotFoundError:
        return None


def get_reflex_package_versions() -> dict[str, str]:
    """Get the versions of the installed Reflex subpackages.

    Reports only the first-party subpackages distributed with Reflex from this
    repository (``reflex-base``, the ``reflex-components-*`` family and
    ``reflex-hosting-cli``). The set is derived from the ``reflex``
    distribution's own declared dependencies, so unrelated third-party
    ``reflex-*`` packages a user may have installed are never reported. The main
    ``reflex`` package is reported separately via ``get_reflex_version``.

    Returns:
        A mapping of Reflex subpackage name to installed version, sorted by name.
    """
    try:
        requirements = importlib.metadata.requires("reflex") or ()
    except importlib.metadata.PackageNotFoundError:
        return {}

    versions: dict[str, str] = {}
    for requirement in requirements:
        name = canonicalize_name(Requirement(requirement).name)
        if not name.startswith("reflex-"):
            continue
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return dict(sorted(versions.items()))


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

    distinct_id: str
    distinct_app_id: NotRequired[str]
    user_os: str
    user_os_detail: str
    reflex_version: str
    python_version: str
    node_version: str | None
    bun_version: str | None
    reflex_enterprise_version: str | None
    reflex_package_version: dict[str, str]
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


def _encode_distinct_id(value: int) -> str:
    """Encode a 128-bit telemetry identifier as a canonical UUID string.

    Historically ``distinct_id`` and ``distinct_app_id`` were sent as raw
    128-bit integers. PostHog coerces large JSON numbers to floats, silently
    discarding all but ~16 significant digits, so distinct installs or apps can
    collapse onto the same truncated value and have their events correlated.

    A UUID carries the same 128 bits, so the hex string is sent losslessly while
    remaining the *same value* as the legacy integer
    (``uuid.UUID(int=value).int == value``). Deriving the UUID from the existing
    identifier — rather than minting a fresh one — keeps an installation's new
    events linkable to its pre-migration history.

    Args:
        value: The stored 128-bit identifier.

    Returns:
        The identifier encoded as a UUID hex string.
    """
    return str(uuid.UUID(int=value))


def _get_event_defaults() -> _DefaultEvent | None:
    """Get the default event data.

    Returns:
        The default event data.
    """
    if (installation_id := ensure_reflex_installation_id()) is None:
        console.debug("Could not get installation_id")
        return None
    cpuinfo = get_cpu_info()
    properties: _Properties = {
        "distinct_id": _encode_distinct_id(installation_id),
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
        "reflex_package_version": get_reflex_package_versions(),
        "cpu_count": get_cpu_count(),
        "cpu_info": dataclasses.asdict(cpuinfo) if cpuinfo else {},
    }
    if (
        project_hash := get_project_hash(raise_on_fail=_raise_on_missing_project_hash())
    ) is not None:
        properties["distinct_app_id"] = _encode_distinct_id(project_hash)

    return {
        "api_key": "phc_JoMo0fOyi0GQAooY3UyO9k0hebGkMyFJrrCw1Gt5SGb",
        "properties": properties,
    }


@once_unless_none
def get_event_defaults() -> _DefaultEvent | None:
    """Get the default event data.

    Returns:
        The default event data.
    """
    return _get_event_defaults()


def _prepare_event(
    event: str,
    *,
    properties: dict[str, Any] | None = None,
    **kwargs,
) -> _Event | None:
    """Prepare the event to be sent to the PostHog server.

    Args:
        event: The event name.
        properties: Arbitrary structured payload merged into the event
            properties. Preferred over ``kwargs`` for new events.
        kwargs: Additional data to send with the event. Allow-listed keys
            kept for backward compatibility with existing call sites.

    Returns:
        The event data.
    """
    event_data = get_event_defaults()
    if not event_data:
        return None

    additional_keys = [
        "template",
        "context",
        "detail",
        "user_uuid",
        "status",
        "duration",
        "compile_duration",
        "setup_duration",
        "build_duration",
        "zip_duration",
    ]

    # Shallow-copy so we don't mutate the cached default properties dict.
    merged_properties = dict(event_data["properties"])

    for key in additional_keys:
        if key in merged_properties:
            continue
        if key in kwargs and kwargs[key] is not None:
            merged_properties[key] = kwargs[key]

    if properties:
        merged_properties.update(properties)

    stamp = datetime.now(UTC).isoformat()

    return cast(
        "_Event",
        {
            "api_key": event_data["api_key"],
            "event": event,
            "properties": merged_properties,
            "timestamp": stamp,
        },
    )


def _send_event(event_data: _Event) -> bool:
    import httpx

    try:
        httpx.post(POSTHOG_API_URL, json=event_data)
    except Exception:
        return False
    else:
        return True


def _send(
    event: str,
    telemetry_enabled: bool | None,
    *,
    properties: dict[str, Any] | None = None,
    **kwargs,
) -> bool:
    # Get the telemetry_enabled from the config if it is not specified.
    if telemetry_enabled is None:
        telemetry_enabled = get_config().telemetry_enabled

    # Return if telemetry is disabled.
    if not telemetry_enabled:
        return False

    with suppress(Exception):
        event_data = _prepare_event(event, properties=properties, **kwargs)
        if not event_data:
            return False
        return _send_event(event_data)
    return False


_executor_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None


def _get_telemetry_executor() -> ThreadPoolExecutor:
    """Return the process-wide, lazily-created telemetry executor.

    A single-worker thread pool runs all telemetry collection and delivery off
    the caller's thread — in particular the asyncio event loop, which the
    blocking syscalls, subprocess calls and synchronous HTTP request used to
    gather and post an event would otherwise stall. The pool's queue serializes
    events through the one worker, and the interpreter drains it at exit via
    ``concurrent.futures``' atexit handler.

    Returns:
        The shared single-worker telemetry executor.
    """
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="reflex-telemetry"
                )
    return _executor


def _run_suppressed(fn: Callable[..., Any], /, *args, **kwargs) -> None:
    """Run ``fn`` in the worker thread, never letting a failure escape.

    Telemetry must never break the app, so any error (including a failed send)
    is reported at debug level and otherwise discarded.

    Args:
        fn: The callable to run.
        args: Positional arguments forwarded to ``fn``.
        kwargs: Keyword arguments forwarded to ``fn``.
    """
    try:
        fn(*args, **kwargs)
    except Exception as err:
        console.debug(f"Failed to process telemetry event: {err}")


def _submit(fn: Callable[..., Any], /, *args, **kwargs) -> None:
    """Queue telemetry work on the background executor, swallowing all errors.

    Args:
        fn: The callable to run in the telemetry worker thread.
        args: Positional arguments forwarded to ``fn``.
        kwargs: Keyword arguments forwarded to ``fn``.
    """
    with suppress(Exception):
        _get_telemetry_executor().submit(_run_suppressed, fn, *args, **kwargs)


def _flush(timeout: float | None = None) -> bool:
    """Block until telemetry queued before this call has been processed.

    The executor has a single worker draining a FIFO queue, so waiting on a
    sentinel submitted now guarantees every previously-queued event has been
    handled. Intended for tests and best-effort shutdown; ordinary call sites
    fire and forget.

    Args:
        timeout: Maximum number of seconds to wait, or ``None`` to wait
            indefinitely.

    Returns:
        ``True`` if the queue drained (or no worker was ever started),
        ``False`` if the wait timed out before the queue emptied.
    """
    if _executor is None:
        return True
    try:
        _executor.submit(lambda: None).result(timeout)
    except Exception:
        return False
    return True


_legacy_alias_attempted = False


def _maybe_alias_legacy_distinct_id(telemetry_enabled: bool | None) -> None:
    """Link the legacy numeric distinct_id to its UUID form, once per install.

    Older Reflex versions reported ``distinct_id`` as a 128-bit integer, which
    PostHog stored as a lossy float. Now that the same value is sent as a UUID
    string (see ``_encode_distinct_id``), the two PostHog identities must be
    merged so an installation's history stays on a single person. PostHog does
    this through a one-time ``$create_alias`` event.

    A per-machine marker file (next to the installation id) records that the
    install uses the new semantics. The marker is written even when the alias
    does not match — the legacy id is lossy, so PostHog may silently drop it — to
    avoid resending on every run.

    Args:
        telemetry_enabled: Whether telemetry is enabled (resolved from the config
            when None).
    """
    global _legacy_alias_attempted
    if _legacy_alias_attempted:
        return

    with suppress(Exception):
        if telemetry_enabled is None:
            telemetry_enabled = get_config().telemetry_enabled
        if not telemetry_enabled:
            # Don't latch: a later enabled send in this process should retry.
            return

        # Latch before the alias send below (which re-enters send()) so it cannot
        # recurse and so the attempt happens at most once per process.
        _legacy_alias_attempted = True

        # Resolve the installation id first: a brand-new install is created and
        # marked UUID-native by this call, so the marker check then skips it.
        if (installation_id := ensure_reflex_installation_id()) is None:
            return
        if has_uuid_distinct_id_semantics():
            return

        # distinct_id is the UUID form (set by get_event_defaults); send the
        # legacy integer as ``alias`` so PostHog coerces it to the same float as
        # the historic events and merges the two persons.
        send("$create_alias", telemetry_enabled, properties={"alias": installation_id})

        # Record the new semantics regardless of outcome; we must not retry every
        # run even if the lossy legacy id failed to match.
        mark_uuid_distinct_id_semantics()


def send(
    event: str,
    telemetry_enabled: bool | None = None,
    *,
    properties: dict[str, Any] | None = None,
    **kwargs,
):
    """Send anonymous telemetry for Reflex.

    The event is collected and delivered on a dedicated single-worker thread
    pool, so neither the data gathering (blocking syscalls and subprocess calls)
    nor the synchronous HTTP request blocks the caller — in particular the
    asyncio event loop serving a running app. Delivery is best-effort: any
    failure is suppressed and never surfaces to the caller.

    Args:
        event: The event name.
        telemetry_enabled: Whether to send the telemetry (If None, get from config).
        properties: Arbitrary structured payload merged into the event
            properties. Preferred over ``kwargs`` for new events.
        kwargs: Additional data to send with the event.
    """
    with suppress(Exception):
        if telemetry_enabled is None:
            telemetry_enabled = get_config().telemetry_enabled
        # Only spin up the worker pool when there is actually something to send.
        if telemetry_enabled:
            _submit(
                _process_event,
                event,
                telemetry_enabled,
                properties=properties,
                **kwargs,
            )


def _process_event(
    event: str,
    telemetry_enabled: bool,
    *,
    properties: dict[str, Any] | None = None,
    **kwargs,
) -> None:
    """Collect and deliver a single telemetry event from the worker thread.

    Args:
        event: The event name.
        telemetry_enabled: Whether telemetry is enabled.
        properties: Structured payload merged into the event properties.
        kwargs: Additional allow-listed event data.
    """
    _maybe_alias_legacy_distinct_id(telemetry_enabled)
    _send(event, telemetry_enabled, properties=properties, **kwargs)


def send_error(error: Exception, context: str):
    """Send an error event.

    Args:
        error: The error to send.
        context: The context of the error (e.g. "frontend" or "backend")
    """
    if isinstance(error, ReflexError):
        send("error", detail=type(error).__name__, context=context)
