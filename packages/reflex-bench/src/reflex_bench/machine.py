"""The machine profile recorded with every result, and the ``doctor`` checks.

Linux is read from ``/proc`` and ``/sys``; other systems report what is
available and ``None`` (unknown) for the rest. Results from different profiles
are never compared, so the profile id captures what makes numbers comparable:
operating system, architecture, CPU model and Python version.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import psutil

from reflex_bench.schema import MachineDoc

PROFILE_ENV = "REFLEX_BENCH_PROFILE"
LOAD_WARN = 1.0
_ARCH_ALIASES = {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}
_CONTAINER_MARKERS = ("docker", "kubepods", "containerd", "lxc", "libpod", "podman")
_CPU_NOISE = re.compile(
    r"\((?:r|tm|c)\)|\b(?:cpu|processor)\b|\b\d+-core\b|@\s*[\d.]+\s*[gm]hz",
    re.IGNORECASE,
)
_CPU_VENDORS = re.compile(r"\b(?:amd|intel|genuineintel|authenticamd)\b", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_PROFILE_PATTERN = re.compile(r"[A-Za-z0-9._-]+")

CheckStatus = Literal["ok", "warn", "info"]


@dataclass(frozen=True)
class Check:
    """One ``doctor`` finding.

    Attributes:
        name: What was checked.
        status: ``ok``, ``warn`` (adds measurement noise) or ``info``.
        value: What was found.
        hint: How to fix a warning.
    """

    name: str
    status: CheckStatus
    value: str
    hint: str | None = None


def _read(path: Path) -> str | None:
    """Read a small text file.

    Args:
        path: The file.

    Returns:
        Its stripped content, or ``None`` when it cannot be read.
    """
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _run(*cmd: str) -> str | None:
    """Run a small probing command.

    Args:
        *cmd: The command and its arguments.

    Returns:
        Its stripped stdout (even on a non-zero exit, which some probes use to
        answer "no"), or ``None`` when it cannot run.
    """
    if shutil.which(cmd[0]) is None:
        return None
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() or None


def normalize_arch(machine: str) -> str:
    """Use one name per architecture across operating systems.

    Args:
        machine: ``platform.machine()``.

    Returns:
        E.g. ``x86_64`` or ``arm64``.
    """
    lowered = machine.lower()
    return _ARCH_ALIASES.get(lowered, lowered or "unknown")


def short_cpu_model(model: str | None) -> str:
    """Drop trademarks, core counts and clock speeds from a CPU model name.

    Args:
        model: The raw model name.

    Returns:
        E.g. ``AMD Ryzen 9 7950X`` for ``AMD Ryzen 9 7950X 16-Core Processor``.
    """
    if not model:
        return "unknown CPU"
    return " ".join(_CPU_NOISE.sub(" ", model).split())


def cpu_slug(model: str | None) -> str:
    """Turn a CPU model into a profile id component.

    Args:
        model: The raw model name.

    Returns:
        E.g. ``ryzen-9-7950x``: lowercase, no vendor, non-alphanumerics as ``-``.
    """
    if not model:
        return "unknown-cpu"
    words = _CPU_VENDORS.sub(" ", short_cpu_model(model)).lower()
    return _NON_ALNUM.sub("-", words).strip("-") or "unknown-cpu"


def profile_id(
    system: str, arch: str, cpu_model: str | None, python_version: str
) -> str:
    """Build the machine profile id; ``REFLEX_BENCH_PROFILE`` overrides it.

    Args:
        system: ``platform.system()``.
        arch: The normalized architecture.
        cpu_model: The raw CPU model name.
        python_version: The subject's Python version.

    Returns:
        E.g. ``linux-x86_64-ryzen-9-7950x-py3.12``.
    """
    override = os.environ.get(PROFILE_ENV, "").strip()
    if override:
        # The id names a directory, so keep it to a safe character set.
        return (
            override
            if _PROFILE_PATTERN.fullmatch(override)
            else _NON_ALNUM.sub("-", override.lower()).strip("-")
        )
    major_minor = ".".join(python_version.split(".")[:2])
    return f"{system.lower()}-{arch}-{cpu_slug(cpu_model)}-py{major_minor}"


def _cpu_model(cpuinfo: str | None, system: str) -> str | None:
    """Find the CPU model name.

    Args:
        cpuinfo: The content of ``/proc/cpuinfo`` on Linux.
        system: ``platform.system()``.

    Returns:
        The model name, or ``None`` when unknown.
    """
    if cpuinfo:
        for line in cpuinfo.splitlines():
            key, _, value = line.partition(":")
            if key.strip() in {"model name", "Model", "Hardware"} and value.strip():
                return value.strip()
    if system == "Darwin":
        return _run("sysctl", "-n", "machdep.cpu.brand_string")
    return platform.processor() or None


def _governor(sysroot: Path) -> str | None:
    """Read the CPU frequency governor.

    Args:
        sysroot: The filesystem root.

    Returns:
        The governor, ``mixed(a,b)`` when CPUs differ, or ``None`` when unknown.
    """
    cpus = sysroot / "sys" / "devices" / "system" / "cpu"
    found = {
        value
        for path in cpus.glob("cpu[0-9]*/cpufreq/scaling_governor")
        if (value := _read(path))
    }
    if not found:
        return None
    return found.pop() if len(found) == 1 else f"mixed({','.join(sorted(found))})"


def _turbo(sysroot: Path) -> bool | None:
    """Read whether turbo/boost clocks are enabled.

    Args:
        sysroot: The filesystem root.

    Returns:
        Whether turbo is on, or ``None`` when unknown.
    """
    cpu = sysroot / "sys" / "devices" / "system" / "cpu"
    no_turbo = _read(cpu / "intel_pstate" / "no_turbo")
    if no_turbo in {"0", "1"}:
        return no_turbo == "0"
    boost = _read(cpu / "cpufreq" / "boost")
    if boost in {"0", "1"}:
        return boost == "1"
    return None


def _container(sysroot: Path) -> bool:
    """Detect a Linux container.

    Args:
        sysroot: The filesystem root.

    Returns:
        Whether the process runs in a container.
    """
    if (sysroot / ".dockerenv").exists() or (
        sysroot / "run" / ".containerenv"
    ).exists():
        return True
    cgroups = _read(sysroot / "proc" / "1" / "cgroup") or ""
    if any(marker in cgroups for marker in _CONTAINER_MARKERS):
        return True
    detected = _run("systemd-detect-virt", "--container")
    return detected is not None and detected != "none"


def _virtualized(cpuinfo: str | None, system: str) -> bool | None:
    """Detect a virtual machine.

    Args:
        cpuinfo: The content of ``/proc/cpuinfo`` on Linux.
        system: ``platform.system()``.

    Returns:
        Whether the machine is virtual, or ``None`` when unknown.
    """
    if system == "Linux":
        detected = _run("systemd-detect-virt", "--vm")
        if detected is not None:
            return detected != "none"
        if cpuinfo and re.search(r"^flags\s*:.*\bhypervisor\b", cpuinfo, re.MULTILINE):
            return True
        return None
    if system == "Darwin":
        present = _run("sysctl", "-n", "kern.hv_vmm_present")
        return None if present is None else present == "1"
    return None


def _ac_power() -> bool | None:
    """Read whether the machine runs on AC power.

    Returns:
        ``True`` on AC, ``False`` on battery, ``None`` without a battery or when
        unknown.
    """
    try:
        battery = psutil.sensors_battery()
    except (AttributeError, NotImplementedError, OSError, RuntimeError):
        return None
    if battery is None or battery.power_plugged is None:
        return None
    return bool(battery.power_plugged)


def _load_average() -> float | None:
    """Read the one-minute load average.

    Returns:
        The load average, or ``None`` where the system has none (Windows).
    """
    try:
        return round(os.getloadavg()[0], 2)
    except (AttributeError, OSError):
        return None


def _playwright_chromium() -> bool:
    """Check for a Playwright chromium download (never installs anything).

    Returns:
        Whether a chromium build is in the Playwright browsers directory.
    """
    configured = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if configured and configured != "0":
        root = Path(configured)
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Caches" / "ms-playwright"
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ms-playwright"
    else:
        root = Path.home() / ".cache" / "ms-playwright"
    try:
        return any(entry.name.startswith("chromium") for entry in root.iterdir())
    except OSError:
        return False


def collect(
    sysroot: Path | None = None,
    system: str | None = None,
    python_version: str | None = None,
) -> MachineDoc:
    """Describe the machine.

    Args:
        sysroot: The filesystem root to read Linux information from.
        system: ``platform.system()``, overridable for tests.
        python_version: The subject's Python version; defaults to the harness's.

    Returns:
        The machine entry of the result document.
    """
    root = sysroot or Path("/")
    system = system or platform.system()
    linux = system == "Linux"
    cpuinfo = _read(root / "proc" / "cpuinfo") if linux else None
    cpu_model = _cpu_model(cpuinfo, system)
    arch = normalize_arch(platform.machine())
    memory = psutil.virtual_memory()
    return {
        "profile_id": profile_id(
            system, arch, cpu_model, python_version or platform.python_version()
        ),
        "os": system,
        "kernel": platform.release(),
        "arch": arch,
        "cpu_model": cpu_model,
        "cpu_count": psutil.cpu_count(logical=True),
        "ram_bytes": int(memory.total),
        "governor": _governor(root) if linux else None,
        "turbo": _turbo(root) if linux else None,
        "load_avg_1m": _load_average(),
        "ac_power": _ac_power(),
        "cgroup_v2": (root / "sys" / "fs" / "cgroup" / "cgroup.controllers").exists()
        if linux
        else None,
        "container": _container(root) if linux else None,
        "virtualized": _virtualized(cpuinfo, system),
        "tools": {
            "bun": shutil.which("bun") is not None,
            "node": shutil.which("node") is not None,
            "chromium": _playwright_chromium(),
        },
    }


def _describe_cpu(machine: MachineDoc) -> str:
    """Summarize the CPU and memory.

    Args:
        machine: The machine entry.

    Returns:
        E.g. ``AMD Ryzen 9 7950X · 32 cores · 67.1 GB RAM``.
    """
    parts = [short_cpu_model(machine["cpu_model"])]
    if machine["cpu_count"]:
        parts.append(f"{machine['cpu_count']} cores")
    if machine["ram_bytes"]:
        parts.append(f"{machine['ram_bytes'] / 1e9:.1f} GB RAM")
    return " \N{MIDDLE DOT} ".join(parts)


def _tri(value: bool | None, yes: CheckStatus, no: CheckStatus) -> CheckStatus:
    """Map a yes/no/unknown finding to a check status.

    Args:
        value: The finding.
        yes: The status when true.
        no: The status when false.

    Returns:
        The status; unknown findings are ``info``.
    """
    if value is None:
        return "info"
    return yes if value else no


def checks(machine: MachineDoc) -> list[Check]:
    """Judge how suitable the machine is for stable measurements.

    Args:
        machine: The machine entry.

    Returns:
        One check per aspect; ``warn`` checks add measurement noise.
    """
    governor = machine["governor"]
    load = machine["load_avg_1m"]
    found: list[Check] = [
        Check("cpu", "info", _describe_cpu(machine)),
        Check(
            "governor",
            "info"
            if governor is None
            else "ok"
            if governor == "performance"
            else "warn",
            governor or "unknown (no cpufreq)",
            None
            if governor in {None, "performance"}
            else "run `sudo cpupower frequency-set -g performance` for stable numbers",
        ),
        Check(
            "turbo",
            _tri(machine["turbo"], "warn", "ok"),
            {True: "on", False: "off", None: "unknown"}[machine["turbo"]],
            "disable boost for stable numbers: `echo 1 | sudo tee"
            " /sys/devices/system/cpu/intel_pstate/no_turbo` (Intel) or `echo 0 |"
            " sudo tee /sys/devices/system/cpu/cpufreq/boost`"
            if machine["turbo"]
            else None,
        ),
        Check(
            "load",
            "info" if load is None else "warn" if load > LOAD_WARN else "ok",
            "unknown" if load is None else f"{load:.2f}",
            "close other programs: background load skews results"
            if load is not None and load > LOAD_WARN
            else None,
        ),
        Check(
            "power",
            _tri(machine["ac_power"], "ok", "warn"),
            {True: "AC", False: "battery", None: "unknown (no battery)"}[
                machine["ac_power"]
            ],
            "plug in AC power: laptops throttle on battery"
            if machine["ac_power"] is False
            else None,
        ),
        Check(
            "virtualized",
            _tri(machine["virtualized"], "warn", "ok"),
            {True: "yes", False: "no", None: "unknown"}[machine["virtualized"]],
            "virtual machines add noise; compare only results from the same machine type"
            if machine["virtualized"]
            else None,
        ),
        Check(
            "container",
            "info" if machine["container"] is not False else "ok",
            {True: "yes", False: "no", None: "unknown"}[machine["container"]],
        ),
        Check(
            "cgroup v2",
            _tri(machine["cgroup_v2"], "ok", "info"),
            {True: "yes", False: "no", None: "unknown"}[machine["cgroup_v2"]],
            "memory benchmarks need cgroup v2"
            if machine["cgroup_v2"] is False
            else None,
        ),
    ]
    found.extend(
        Check(
            tool,
            "ok" if present else "info",
            "found" if present else "not found",
            None if present else "needed by app benchmarks",
        )
        for tool, present in machine["tools"].items()
    )
    return found


def warning_count(machine: MachineDoc) -> int:
    """Count the checks that add measurement noise.

    Args:
        machine: The machine entry.

    Returns:
        The number of ``warn`` checks.
    """
    return sum(check.status == "warn" for check in checks(machine))
