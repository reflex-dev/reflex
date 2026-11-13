"""Whole-tree memory and CPU of a command, from a transient cgroup v2 scope.

``systemd-run --scope`` starts the command in a new cgroup, so the kernel's
counters cover every process of the tree, bun, node and vite included:
``memory.peak`` (Linux 5.19+), ``memory.stat``, ``memory.events`` and
``cpu.stat``. The scope is created by the user's systemd manager or, on hosts
without one (GitHub runners), by the system manager through passwordless sudo,
still running the command as the current user. Elsewhere
:meth:`CgroupScope.available` says why, and callers fall back to
:mod:`reflex_bench.collectors.pss`.

systemd removes a scope's cgroup when its last process exits, so it must be read
while something still runs in it.
"""

from __future__ import annotations

import functools
import os
import platform
import re
import secrets
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import psutil

from reflex_bench.collectors import PROC

CGROUP_ROOT = Path("/sys/fs/cgroup")
UNIT_PREFIX = "reflex-bench-"
MIN_KERNEL = (5, 19)

ScopeMode = Literal["user", "sudo"]

_MODE_NAMES: dict[ScopeMode, str] = {"user": "user systemd", "sudo": "sudo"}
_ACCOUNTING = ("-p", "MemoryAccounting=yes", "-p", "CPUAccounting=yes")


@dataclass(frozen=True)
class CgroupReading:
    """The counters of a scope's cgroup, in the kernel's units.

    Attributes:
        memory_peak_bytes: The highest memory use since the scope started, or
            since the last :meth:`CgroupScope.reset_peak` when ``peak_reset``.
        memory_current_bytes: The memory in use now.
        anon_bytes: Anonymous memory (``memory.stat`` ``anon``).
        file_bytes: Page cache (``memory.stat`` ``file``).
        oom: Times the limit was hit and reclaim failed (``memory.events``).
        oom_kill: Processes the OOM killer killed in the scope.
        cpu_usage_usec: CPU time of all processes, in microseconds.
        cpu_user_usec: Its user part.
        cpu_system_usec: Its system part.
        peak_reset: Whether ``memory_peak_bytes`` starts at the last reset.
    """

    memory_peak_bytes: int
    memory_current_bytes: int
    anon_bytes: int
    file_bytes: int
    oom: int
    oom_kill: int
    cpu_usage_usec: int
    cpu_user_usec: int
    cpu_system_usec: int
    peak_reset: bool

    @property
    def cpu_s(self) -> float:
        """The CPU time of all processes.

        Returns:
            Seconds.
        """
        return self.cpu_usage_usec / 1e6


def _linux() -> bool:
    """Check the operating system.

    Returns:
        Whether it is Linux.
    """
    return sys.platform == "linux"


def _cgroup2_root(mounts: Path = PROC / "self" / "mounts") -> Path | None:
    """Find where the cgroup v2 hierarchy is mounted.

    Args:
        mounts: The mount table.

    Returns:
        ``/sys/fs/cgroup`` on unified hosts, ``/sys/fs/cgroup/unified`` on hybrid
        ones, ``None`` without cgroup v2.
    """
    try:
        text = mounts.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[2] == "cgroup2":
            return Path(fields[1].replace("\\040", " "))
    return None


def _kernel() -> tuple[int, int]:
    """Read the kernel version.

    Returns:
        ``(major, minor)``, ``(0, 0)`` when unknown.
    """
    match = re.match(r"(\d+)\.(\d+)", platform.release())
    return (int(match[1]), int(match[2])) if match else (0, 0)


def _run(argv: Sequence[str]) -> tuple[bool, str]:
    """Run a probe command.

    Args:
        argv: The command.

    Returns:
        Whether it succeeded, and the last line of its error output.
    """
    try:
        proc = subprocess.run(
            list(argv),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    lines = (proc.stderr or proc.stdout).strip().splitlines()
    return proc.returncode == 0, lines[-1] if lines else f"exit code {proc.returncode}"


def _scope_argv(
    mode: ScopeMode, unit: str | None, properties: Sequence[str], path: str | None
) -> list[str]:
    """Build the ``systemd-run`` prefix that starts a command in a new scope.

    Args:
        mode: ``user`` for the user manager, ``sudo`` for the system manager.
        unit: The scope's unit name, without ``.scope``.
        properties: ``-p NAME=VALUE`` arguments.
        path: The command's ``PATH``, which sudo would reset.

    Returns:
        The arguments up to and including ``--``.
    """
    if mode == "user":
        argv = ["systemd-run", "--user", "--scope", "--quiet", "--collect"]
    else:
        # -E keeps the caller's environment, --uid/--gid run the command as the
        # caller; sudo resets PATH to its secure_path, so it is set again.
        argv = ["sudo", "-n", "-E", "systemd-run", "--scope", "--quiet", "--collect"]
    if unit is not None:
        argv.append(f"--unit={unit}")
    if mode == "sudo":
        argv += [f"--uid={os.getuid()}", f"--gid={os.getgid()}"]
        if path:
            argv.append(f"--setenv=PATH={path}")
    return [*argv, *properties, "--"]


@functools.cache
def probe() -> tuple[ScopeMode | None, str | None]:
    """Find how this host can start cgroup scopes, by trying it.

    The result is cached for the life of the process.

    Returns:
        ``(mode, None)`` when scopes work, else ``(None, reason)``.
    """
    if not _linux():
        return None, "cgroup scopes need Linux"
    root = _cgroup2_root()
    if root is None:
        return None, "no cgroup v2 hierarchy is mounted"
    try:
        controllers = (root / "cgroup.controllers").read_text(encoding="utf-8").split()
    except OSError:
        controllers = []
    if "memory" not in controllers:
        return (
            None,
            f"the cgroup v2 hierarchy at {root} has no memory controller (hybrid cgroup v1 host)",
        )
    kernel = _kernel()
    if kernel < MIN_KERNEL:
        return (
            None,
            f"memory.peak needs Linux 5.19 or later (running {kernel[0]}.{kernel[1]})",
        )
    if shutil.which("systemd-run") is None:
        return None, "systemd-run not found"
    ok, detail = _run([*_scope_argv("user", None, _ACCOUNTING, None), "true"])
    if ok:
        return "user", None
    reasons = [f"no user systemd manager ({detail})"]
    ok, detail = _run(["sudo", "-n", "true"])
    if not ok:
        reasons.append(f"no passwordless sudo ({detail})")
        return None, "; ".join(reasons)
    ok, detail = _run([
        *_scope_argv("sudo", None, _ACCOUNTING, os.environ.get("PATH")),
        "true",
    ])
    if ok:
        return "sudo", None
    reasons.append(f"sudo systemd-run failed ({detail})")
    return None, "; ".join(reasons)


@functools.cache
def oom_policy_supported(mode: ScopeMode) -> bool:
    """Check whether systemd accepts ``OOMPolicy=continue`` on scopes, by trying it.

    With the default ``OOMPolicy=stop``, systemd 253 and later stops a whole scope
    after an OOM kill in it, so ``memory.events`` is gone before anyone reads it.
    Older versions reject the property on scopes and do not stop them.

    Args:
        mode: How scopes are started.

    Returns:
        Whether the property is accepted.
    """
    policy = (*_ACCOUNTING, "-p", "OOMPolicy=continue")
    return _run([*_scope_argv(mode, None, policy, os.environ.get("PATH")), "true"])[0]


def status() -> tuple[bool, str]:
    """Describe cgroup scope support for ``reflex-bench doctor``.

    Returns:
        Whether scopes work, and ``ok (user systemd)``, ``ok (sudo)`` or
        ``unavailable: <reason>``.
    """
    mode, reason = probe()
    if mode is None:
        return False, f"unavailable: {reason}"
    return True, f"ok ({_MODE_NAMES[mode]})"


def _keyed(path: Path) -> dict[str, int]:
    """Parse a flat-keyed cgroup file such as ``memory.stat``.

    Args:
        path: The file, one ``name value`` pair per line.

    Returns:
        The values by name.
    """
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        name, _, value = line.partition(" ")
        if value.strip().isdigit():
            values[name] = int(value)
    return values


def _running(process: psutil.Process) -> bool:
    """Check that a process runs and is not a zombie.

    Args:
        process: The process.

    Returns:
        Whether it runs.
    """
    try:
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


class CgroupScope:
    """A transient systemd scope around one command: wrap it, attach, read.

    :meth:`wrap` prefixes the command so it starts in a new scope, :meth:`attach`
    finds the scope's cgroup once the command runs, and :meth:`read` returns its
    counters while a process of the scope is alive.
    """

    def __init__(
        self,
        *,
        limit_bytes: int | None = None,
        swap_max: int | None = 0,
        mode: ScopeMode | None = None,
        proc_root: Path = PROC,
        cgroup_root: Path | None = None,
    ) -> None:
        """Prepare a scope.

        Args:
            limit_bytes: ``MemoryMax`` of the scope; ``None`` for no limit.
            swap_max: ``MemorySwapMax`` under a limit; the default 0 keeps a
                limited command from passing by swapping. ``None`` leaves swap
                alone.
            mode: How to start scopes; probed when ``None``.
            proc_root: The ``/proc`` mount.
            cgroup_root: The cgroup v2 mount; found from the mount table when ``None``.

        Raises:
            RuntimeError: When no mode is given and this host cannot start scopes.
        """
        if mode is None:
            mode, reason = probe()
            if mode is None:
                msg = f"cgroup scopes are unavailable: {reason}"
                raise RuntimeError(msg)
        self.mode: ScopeMode = mode
        self.limit_bytes = limit_bytes
        self.swap_max = swap_max
        self.unit: str | None = None
        self.path: Path | None = None
        self._proc_root = proc_root
        self._cgroup_root = cgroup_root
        self._peak_fd: int | None = None

    @staticmethod
    def available() -> str | None:
        """Check whether this host can start cgroup scopes (cached).

        Returns:
            ``None`` when it can, else why not.
        """
        return probe()[1]

    def wrap(
        self, argv: Sequence[str], *, env: Mapping[str, str] | None = None
    ) -> list[str]:
        """Prefix a command so it starts in a new scope.

        Args:
            argv: The command.
            env: The environment the command will run with; its ``PATH``
                survives sudo. Defaults to ``os.environ``.

        Returns:
            The wrapped command.
        """
        self.close()
        self.unit = UNIT_PREFIX + secrets.token_hex(6)
        self.path = None
        properties = list(_ACCOUNTING)
        if self.limit_bytes is not None:
            properties += ["-p", f"MemoryMax={self.limit_bytes}"]
            if self.swap_max is not None:
                properties += ["-p", f"MemorySwapMax={self.swap_max}"]
            # An OOM kill must leave the scope running so its counters stay readable.
            if oom_policy_supported(self.mode):
                properties += ["-p", "OOMPolicy=continue"]
        path = (os.environ if env is None else env).get("PATH")
        return [*_scope_argv(self.mode, self.unit, properties, path), *argv]

    def _cgroup_of(self, pid: int) -> str | None:
        """Read the cgroup v2 path of a process.

        Args:
            pid: The process id.

        Returns:
            The path relative to the cgroup v2 root, or ``None`` when unreadable.
        """
        try:
            text = (self._proc_root / str(pid) / "cgroup").read_text(encoding="utf-8")
        except OSError:
            return None
        for line in text.splitlines():
            if line.startswith("0::"):
                return line[3:]
        return None

    def attach(self, pid: int, timeout: float = 10.0) -> None:
        """Find the scope's cgroup once systemd has moved the wrapped command into it.

        The command may be ``pid`` itself (``systemd-run`` execs it) or one of its
        descendants (``sudo`` stays in the caller's cgroup).

        Args:
            pid: The process started with the wrapped command.
            timeout: Seconds to wait.

        Raises:
            RuntimeError: Before :meth:`wrap`, or when no process of the tree
                enters the scope in time.
        """
        if self.unit is None:
            msg = "wrap() a command before attach()"
            raise RuntimeError(msg)
        suffix = f"/{self.unit}.scope"
        root = self._cgroup_root or _cgroup2_root() or CGROUP_ROOT
        deadline = time.monotonic() + timeout
        try:
            process: psutil.Process | None = psutil.Process(pid)
        except psutil.NoSuchProcess:
            process = None
        while True:
            try:
                tree = [process, *process.children(recursive=True)] if process else []
            except psutil.NoSuchProcess:
                tree = []
            for member in tree:
                relative = self._cgroup_of(member.pid)
                if relative is not None and relative.endswith(suffix):
                    self.path = root / relative.lstrip("/")
                    return
            if process is None or not _running(process) or time.monotonic() >= deadline:
                msg = f"pid {pid} never entered scope {self.unit}"
                raise RuntimeError(msg)
            time.sleep(0.01)

    def _file(self, name: str) -> Path:
        """Locate a file of the scope's cgroup.

        Args:
            name: The file name, e.g. ``memory.peak``.

        Returns:
            The path.

        Raises:
            RuntimeError: Before :meth:`attach`.
        """
        if self.path is None:
            msg = "attach() the scope before reading it"
            raise RuntimeError(msg)
        return self.path / name

    def reset_peak(self) -> None:
        """Start a new ``memory.peak`` window, for per-phase peaks.

        From Linux 6.12 a write to ``memory.peak`` resets the peak seen through
        that file descriptor, so later reads report the peak since the reset.
        Where that is not supported (an older kernel, or a scope file owned by
        root), reads keep reporting the whole run's peak with ``peak_reset``
        false.
        """
        path = self._file("memory.peak")
        if self._peak_fd is not None:
            os.write(self._peak_fd, b"reset\n")
            return
        # Before 6.12 memory.peak has no write handler and is read-only.
        if not path.stat().st_mode & stat.S_IWUSR:
            return
        try:
            fd = os.open(path, os.O_RDWR)
        except OSError:
            return
        try:
            os.write(fd, b"reset\n")
            int(os.pread(fd, 64, 0))
        except (OSError, ValueError):
            os.close(fd)
            return
        self._peak_fd = fd

    def read(self) -> CgroupReading:
        """Read the scope's counters; its cgroup must still exist.

        Returns:
            The reading.
        """
        memory = _keyed(self._file("memory.stat"))
        events = _keyed(self._file("memory.events"))
        cpu = _keyed(self._file("cpu.stat"))
        if self._peak_fd is None:
            peak = int(self._file("memory.peak").read_text(encoding="utf-8"))
        else:
            peak = int(os.pread(self._peak_fd, 64, 0))
        return CgroupReading(
            memory_peak_bytes=peak,
            memory_current_bytes=int(
                self._file("memory.current").read_text(encoding="utf-8")
            ),
            anon_bytes=memory.get("anon", 0),
            file_bytes=memory.get("file", 0),
            oom=events.get("oom", 0),
            oom_kill=events.get("oom_kill", 0),
            cpu_usage_usec=cpu.get("usage_usec", 0),
            cpu_user_usec=cpu.get("user_usec", 0),
            cpu_system_usec=cpu.get("system_usec", 0),
            peak_reset=self._peak_fd is not None,
        )

    def close(self) -> None:
        """Release the ``memory.peak`` descriptor of a reset; later reads cover the whole run."""
        if self._peak_fd is not None:
            os.close(self._peak_fd)
            self._peak_fd = None
