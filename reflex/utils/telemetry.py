"""Anonymous telemetry for Reflex."""

import asyncio
import dataclasses
import importlib.metadata
import json
import multiprocessing
import platform
import warnings
from contextlib import suppress
from datetime import datetime, timezone
from typing import TypedDict

from reflex import constants
from reflex.environment import environment
from reflex.utils import console, processes
from reflex.utils.decorator import once, once_unless_none
from reflex.utils.exceptions import ReflexError
from reflex.utils.js_runtimes import get_bun_version, get_node_version
from reflex.utils.prerequisites import ensure_reflex_installation_id, get_project_hash

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

    async def async_send(event: str, telemetry_enabled: bool | None, **kwargs):  # noqa: RUF029
        return _send(event, telemetry_enabled, **kwargs)

    try:
        # Within an event loop context, send the event asynchronously.
        task = asyncio.create_task(
            async_send(event, telemetry_enabled, **kwargs),
            name=f"reflex_send_telemetry_event|{event}",
        )
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
