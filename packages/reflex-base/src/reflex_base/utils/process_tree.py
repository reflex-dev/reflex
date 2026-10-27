"""Stop a process together with everything it started.

Reflex keeps the processes it starts in its own process group, so a terminal
Ctrl-C, a ``kill -- -<pgid>`` from a service manager or a group SIGKILL reach
all of them at once. The price is that a signal sent to one PID stops only
that process: a package manager in front of a dev server, for example, exits
and leaves the server behind. :func:`stop_process_tree` closes that gap by
signalling every descendant it can find, waiting for all of them against one
deadline, and killing whatever is left.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

# Linux lists every process under /proc; other POSIX systems need ps(1).
_PROC = Path("/proc")


def _stat_fields(pid: int | str) -> list[bytes] | None:
    """Read the fixed fields of a process's ``/proc/<pid>/stat``.

    Args:
        pid: The process ID.

    Returns:
        The fields after the command name (state, ppid, ...), or None when
        the process is gone.
    """
    try:
        stat = (_PROC / str(pid) / "stat").read_bytes()
    except OSError:
        return None
    # The command name may hold spaces or parentheses; the fixed fields start
    # after its closing parenthesis.
    return stat[stat.rfind(b")") + 1 :].split()


def _process_parents() -> Iterator[tuple[int, int]]:
    """Yield ``(pid, ppid)`` for every process on a POSIX system.

    Yields:
        Each process ID with its parent process ID.
    """
    if sys.platform == "linux" and _PROC.is_dir():
        for entry in _PROC.iterdir():
            # A process that exited while being listed has no fields.
            if entry.name.isdigit() and (fields := _stat_fields(entry.name)):
                yield int(entry.name), int(fields[1])
        return
    listing = subprocess.run(
        ["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True, check=False
    ).stdout
    for line in listing.splitlines():
        fields = line.split()
        if len(fields) == 2:
            yield int(fields[0]), int(fields[1])


def descendant_pids(pid: int) -> list[int]:
    """List every live descendant of a process, parents before their children.

    Args:
        pid: The root process ID.

    Returns:
        The descendant process IDs, or an empty list on Windows, where
        ``taskkill /T`` walks the tree itself.
    """
    if sys.platform == "win32":
        return []
    children: dict[int, list[int]] = {}
    for child, parent in _process_parents():
        children.setdefault(parent, []).append(child)
    found: list[int] = []
    pending = [pid]
    while pending:
        own = children.get(pending.pop(), ())
        found.extend(own)
        pending.extend(own)
    return found


def _alive(pid: int) -> bool:
    """Check whether a process still exists.

    Args:
        pid: The process ID.

    Returns:
        Whether the process still runs; an exited process nobody reaped yet
        counts as gone.
    """
    # An orphan is reparented to this process when it is PID 1 or a
    # subreaper, in which case only this process can reap it.
    with contextlib.suppress(ChildProcessError):
        if os.waitpid(pid, os.WNOHANG)[0]:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if sys.platform == "linux":
        fields = _stat_fields(pid)
        return fields is not None and fields[0] != b"Z"
    return True


def _signal(pids: list[int], signum: int):
    """Send a signal to each process, ignoring the ones already gone.

    Args:
        pids: The process IDs.
        signum: The signal.
    """
    for pid in pids:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signum)


def kill_descendants(pid: int):
    """SIGKILL every descendant of a process at once, without waiting.

    On Windows this does nothing: there is no SIGKILL, and ``taskkill /T``
    in :func:`stop_process_tree` already ends a tree without a grace period.

    Args:
        pid: The root process ID, which is left running.
    """
    if sys.platform != "win32":
        _signal(descendant_pids(pid), signal.SIGKILL)


def _wait(process: subprocess.Popen, descendants: list[int], deadline: float):
    """Wait until the process and its descendants are gone or the deadline passes.

    Args:
        process: The process, which is reaped here.
        descendants: The descendant process IDs to wait for.
        deadline: The monotonic time to give up at.
    """
    while True:
        remaining = deadline - time.monotonic()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=max(remaining, 0))
        if process.returncode is not None and not any(map(_alive, descendants)):
            return
        if remaining <= 0:
            return
        time.sleep(min(0.02, remaining))


def stop_process_tree(process: subprocess.Popen, timeout: float = 5.0):
    """Stop a process and every process below it.

    On POSIX the process and its descendants get SIGTERM, then SIGKILL if any
    of them is still alive after ``timeout`` seconds; a descendant started
    during the wait is caught by a second look before the kill, as long as
    the process itself still runs. A process that forks while handling
    SIGTERM and exits before that fork is seen leaves it behind: without a
    process group of its own, descendant discovery is best effort. On Windows
    ``taskkill /T /F`` ends the whole tree at once. The process is reaped
    either way, so ``process.returncode`` is set afterwards.

    Args:
        process: The process to stop.
        timeout: Seconds to wait for a graceful exit before killing.
    """
    if sys.platform == "win32":
        if process.poll() is None:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
            )
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=timeout)
        return
    if process.poll() is not None:
        return
    descendants = descendant_pids(process.pid)
    _signal([process.pid, *descendants], signal.SIGTERM)
    _wait(process, descendants, time.monotonic() + timeout)
    if process.returncode is None:
        descendants = [*descendants, *descendant_pids(process.pid)]
        _signal([process.pid], signal.SIGKILL)
    survivors = [pid for pid in descendants if _alive(pid)]
    if survivors:
        _signal(survivors, signal.SIGKILL)
    # A killed process disappears promptly; a short wait reaps the child.
    _wait(process, survivors, time.monotonic() + 1)
