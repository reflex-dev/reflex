"""Tests for stopping a process together with everything it started."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest
from reflex_base.utils import process_tree

# A child that starts a grandchild and does not forward signals to it, like
# ``npm run`` in front of a dev server. It reports the grandchild PID on stdout.
_ORPHANING_CHILD = """
import subprocess, sys, time
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
print(grandchild.pid, flush=True)
time.sleep(60)
"""

# A child that ignores SIGTERM, so only SIGKILL stops it.
_STUBBORN_CHILD = """
import signal, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
print("ready", flush=True)
time.sleep(60)
"""


def _alive(pid: int) -> bool:
    """Check whether a process still exists.

    Args:
        pid: The process ID.

    Returns:
        Whether the process exists (a zombie counts as gone).
    """
    if sys.platform == "win32":
        try:
            return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False
    try:
        os.kill(pid, 0)
        if sys.platform == "linux":
            stat = Path(f"/proc/{pid}/stat").read_bytes()
            return stat.rsplit(b")", 1)[1].split()[0] != b"Z"
    except OSError:
        return False
    return True


def _wait_gone(pid: int, timeout: float = 5) -> bool:
    """Wait until a process is gone.

    Args:
        pid: The process ID.
        timeout: How long to wait.

    Returns:
        Whether the process went away in time.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.02)
    return not _alive(pid)


def _start(tmp_path: Path, source: str) -> tuple[subprocess.Popen, str]:
    """Start a scripted child and read its first output line.

    Args:
        tmp_path: The directory for the script.
        source: The script source.

    Returns:
        The process and its first output line.
    """
    script = tmp_path / "child.py"
    script.write_text(source)
    proc = subprocess.Popen(
        [sys.executable, str(script)], stdout=subprocess.PIPE, text=True
    )
    assert proc.stdout is not None
    return proc, proc.stdout.readline().strip()


def test_descendant_pids_lists_the_whole_tree(tmp_path: Path):
    """Every level below the process is found, parents before children."""
    proc, line = _start(tmp_path, _ORPHANING_CHILD)
    grandchild = int(line)
    try:
        if sys.platform == "win32":
            pytest.skip("taskkill walks the tree on Windows")
        assert process_tree.descendant_pids(proc.pid) == [grandchild]
        tree = process_tree.descendant_pids(os.getpid())
        assert tree.index(proc.pid) < tree.index(grandchild)
    finally:
        process_tree.stop_process_tree(proc, timeout=1)


@pytest.mark.skipif(sys.platform != "linux", reason="/proc is Linux-only")
def test_descendant_pids_falls_back_to_ps(tmp_path: Path, monkeypatch):
    """Without /proc the tree is read from ps, as on macOS."""
    monkeypatch.setattr(process_tree, "_PROC", tmp_path / "no-proc")
    proc, line = _start(tmp_path, _ORPHANING_CHILD)
    try:
        assert process_tree.descendant_pids(proc.pid) == [int(line)]
    finally:
        process_tree.stop_process_tree(proc, timeout=1)


def test_stop_process_tree_stops_an_orphaned_grandchild(tmp_path: Path):
    """A descendant the child does not stop itself is stopped too."""
    proc, line = _start(tmp_path, _ORPHANING_CHILD)
    grandchild = int(line)
    try:
        started = time.monotonic()
        process_tree.stop_process_tree(proc, timeout=5)
        assert time.monotonic() - started < 4
        assert proc.returncode is not None
        assert _wait_gone(grandchild)
    finally:
        # SIGTERM exists on every platform; on Windows it terminates outright.
        with contextlib.suppress(OSError):
            os.kill(grandchild, signal.SIGTERM)


# The killed grandchild stays a zombie under its living parent, which only
# the Linux check sees as gone.
@pytest.mark.skipif(sys.platform != "linux", reason="zombie detection needs /proc")
def test_kill_descendants_kills_below_the_root_only(tmp_path: Path):
    """Every descendant is killed at once and the root keeps running."""
    proc, line = _start(tmp_path, _ORPHANING_CHILD)
    grandchild = int(line)
    try:
        process_tree.kill_descendants(proc.pid)
        assert _wait_gone(grandchild, timeout=1)
        assert proc.poll() is None
    finally:
        process_tree.stop_process_tree(proc, timeout=1)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_kill_descendants_kills_known_pids_no_longer_below_the_root(tmp_path: Path):
    """A descendant seen earlier is killed although its parent has exited."""
    proc, line = _start(tmp_path, _ORPHANING_CHILD)
    grandchild = int(line)
    root = _sleeper()
    try:
        proc.terminate()
        proc.wait(timeout=5)
        assert grandchild not in process_tree.descendant_pids(root.pid)
        process_tree.kill_descendants(root.pid, [grandchild])
        assert _wait_gone(grandchild, timeout=1)
    finally:
        root.kill()
        root.wait()
        with contextlib.suppress(OSError):
            os.kill(grandchild, signal.SIGKILL)


def _sleeper() -> subprocess.Popen:
    """Start a child with no children of its own, to serve as a root.

    Returns:
        The child process.
    """
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])


# A child that exits at once, leaving a grandchild in a process group of its
# own: it stands in for an unrelated process that took over a reused ID.
_DETACHING_CHILD = """
import subprocess, sys
grandchild = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True
)
print(grandchild.pid, flush=True)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_kill_descendants_spares_a_known_pid_outside_the_group(tmp_path: Path):
    """A known ID now held by a process outside the root's group is not killed."""
    proc, line = _start(tmp_path, _DETACHING_CHILD)
    grandchild = int(line)
    root = _sleeper()
    try:
        proc.wait(timeout=5)
        process_tree.kill_descendants(root.pid, [grandchild])
        time.sleep(0.2)
        assert _alive(grandchild)
    finally:
        root.kill()
        root.wait()
        with contextlib.suppress(OSError):
            os.kill(grandchild, signal.SIGKILL)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_stop_process_tree_kills_a_child_that_ignores_sigterm(tmp_path: Path):
    """A child that survives the deadline is killed."""
    proc, line = _start(tmp_path, _STUBBORN_CHILD)
    assert line == "ready"
    started = time.monotonic()
    process_tree.stop_process_tree(proc, timeout=0.5)
    assert proc.returncode == -signal.SIGKILL
    assert 0.5 <= time.monotonic() - started < 3


def test_stop_process_tree_on_an_exited_process(tmp_path: Path):
    """Stopping a process that already exited only reaps it."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    process_tree.stop_process_tree(proc, timeout=1)
    assert proc.returncode == 0


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process states")
def test_alive_treats_an_unreaped_child_as_gone():
    """A zombie no longer runs, so waiting for it would only waste the timeout."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    deadline = time.monotonic() + 5
    while process_tree._alive(proc.pid) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not process_tree._alive(proc.pid)
    # _alive reaped the zombie, which is what happens to orphans under PID 1.
    assert proc.poll() in (0, None)
