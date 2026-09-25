"""Test process utilities."""

import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import types
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from unittest import mock

import pytest

from reflex.testing import DEFAULT_TIMEOUT, AppHarness
from reflex.utils import processes
from reflex.utils.processes import (
    _can_bind_at_any_port,
    is_process_on_port,
    run_concurrently,
    run_concurrently_context,
    stream_logs,
)

# `socket.has_ipv6` only reflects build-time support; without a runtime IPv6
# stack every port looks occupied to `is_process_on_port`'s default families.
requires_ipv6 = pytest.mark.skipif(
    not _can_bind_at_any_port(socket.AF_INET6),
    reason="IPv6 is not available on this system",
)


def test_is_process_on_port_free_port():
    """Test is_process_on_port returns False when port is free."""
    # Find a free port
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("", 0))
        free_port = sock.getsockname()[1]

    # Port should be free after socket is closed
    assert not is_process_on_port(free_port, (socket.AF_INET,))


def test_is_process_on_port_occupied_port():
    """Test is_process_on_port returns True when port is occupied."""
    # Create a server socket to occupy a port
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("", 0))
    server_socket.listen(1)

    occupied_port = server_socket.getsockname()[1]

    try:
        # Port should be occupied
        assert is_process_on_port(occupied_port, (socket.AF_INET,))
    finally:
        server_socket.close()


@requires_ipv6
def test_is_process_on_port_ipv6():
    """Test is_process_on_port works with IPv6."""
    server_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    server_socket.bind(("", 0))
    server_socket.listen(1)

    occupied_port = server_socket.getsockname()[1]

    try:
        # Port should be occupied on IPv6
        assert is_process_on_port(occupied_port)
    finally:
        server_socket.close()


def test_is_process_on_port_both_protocols():
    """Test is_process_on_port detects occupation on either IPv4 or IPv6."""
    # Create IPv4 server
    ipv4_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ipv4_socket.bind(("", 0))
    ipv4_socket.listen(1)

    port = ipv4_socket.getsockname()[1]

    try:
        # Should detect IPv4 occupation
        assert is_process_on_port(port, (socket.AF_INET,))
    finally:
        ipv4_socket.close()


@pytest.mark.parametrize("port", [0, 1, 80, 443, 8000, 3000, 65535])
def test_is_process_on_port_various_ports(port):
    """Test is_process_on_port with various port numbers.

    Args:
        port: The port number to test.
    """
    # This test just ensures the function doesn't crash with different port numbers
    # The actual result depends on what's running on the system
    result = is_process_on_port(port)
    assert isinstance(result, bool)


def test_is_process_on_port_mock_socket_error():
    """Test is_process_on_port handles socket errors gracefully."""
    with mock.patch("socket.socket") as mock_socket:
        mock_socket_instance = mock.MagicMock()
        mock_socket.return_value = mock_socket_instance
        mock_socket_instance.__enter__.return_value = mock_socket_instance
        mock_socket_instance.bind.side_effect = OSError("Mock socket error")

        # Should return True when socket operations fail
        result = is_process_on_port(8080)
        assert result is True


def test_is_process_on_port_permission_error():
    """Test is_process_on_port handles permission errors."""
    with mock.patch("socket.socket") as mock_socket:
        mock_socket_instance = mock.MagicMock()
        mock_socket.return_value = mock_socket_instance
        mock_socket_instance.__enter__.return_value = mock_socket_instance
        mock_socket_instance.bind.side_effect = PermissionError("Permission denied")

        # Should return True when permission is denied (can't bind = port is "occupied")
        result = is_process_on_port(80)
        assert result is True


def test_is_process_on_port_concurrent_access():
    """Test is_process_on_port works correctly with concurrent access."""
    shared = None
    is_open = threading.Event()
    do_close = threading.Event()

    def create_server_and_test():
        nonlocal do_close, is_open, shared
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("", 0))

        server.listen(1)

        port = server.getsockname()[1]
        shared = port

        is_open.set()
        do_close.wait(timeout=DEFAULT_TIMEOUT)

        server.close()

    thread = threading.Thread(target=create_server_and_test)
    thread.start()
    is_open.wait(timeout=DEFAULT_TIMEOUT)

    try:
        assert shared is not None

        # Port should be occupied while server is running (both bound-only and listening)
        assert AppHarness._poll_for(
            lambda: shared is not None and is_process_on_port(shared, (socket.AF_INET,))
        )
    finally:
        do_close.set()
        thread.join(timeout=DEFAULT_TIMEOUT)

    # Give it a moment for the socket to be fully released
    assert AppHarness._poll_for(
        lambda: shared is not None and not is_process_on_port(shared, (socket.AF_INET,))
    )


def _raise_system_exit():
    """Simulate a fatal preflight error in a worker task.

    Raises:
        SystemExit: Always, mimicking a fatal CLI error path.
    """
    raise SystemExit(1)


def test_run_concurrently_context_unblocks_main_thread_on_task_failure():
    """A task raising SystemExit interrupts a blocked with-body and propagates.

    Regression test for `reflex run` hanging forever when a fatal error (e.g.
    the node version check) exits a frontend worker thread while the backend
    blocks the main thread.
    """
    block = threading.Event()
    start = time.monotonic()

    with pytest.raises(SystemExit), run_concurrently_context(_raise_system_exit):
        # Simulate the backend blocking the main thread (e.g. granian serve()).
        block.wait(timeout=10)

    # The failed task must interrupt the main thread well before the body's
    # own 10s wait expires; 5 seconds leaves headroom on slow CI runners.
    assert time.monotonic() - start < 5, (
        "task failure did not interrupt the blocked main thread"
    )


def test_run_concurrently_context_reraises_real_keyboard_interrupt():
    """A KeyboardInterrupt in the with-body propagates when no task failed."""
    with pytest.raises(KeyboardInterrupt), run_concurrently_context(lambda: None):
        raise KeyboardInterrupt


def test_run_concurrently_propagates_task_exception():
    """An exception raised by a task propagates out of run_concurrently."""

    def _fail():
        msg = "boom"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="boom"):
        run_concurrently(_fail)


def _sleep_child(seconds: float = 60, **kwargs) -> subprocess.Popen:
    """Spawn a run-managed child that stays alive until terminated.

    Args:
        seconds: How long the child sleeps.
        **kwargs: Extra new_process kwargs (e.g. start_new_session).

    Returns:
        The live child process.
    """
    return processes.new_process(
        [sys.executable, "-c", f"import time; time.sleep({seconds})"],
        run_managed=True,
        **kwargs,
    )


def _wait_for_key(mapping: dict, key: str) -> None:
    """Wait until a mapping gains a key, for cross-thread handoffs.

    Args:
        mapping: The mapping to watch.
        key: The key to wait for.
    """
    deadline = time.monotonic() + DEFAULT_TIMEOUT
    while key not in mapping and time.monotonic() < deadline:
        time.sleep(0.01)
    assert key in mapping, f"timed out waiting for {key}"


def _process_gone(pid: int) -> bool:
    """Check whether nothing runnable remains at a pid.

    Args:
        pid: The process ID.

    Returns:
        True when the pid is gone or a zombie awaiting reap by its new parent.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    if sys.platform == "linux":
        stat = Path(f"/proc/{pid}/stat")
        if stat.exists():
            try:
                return stat.read_text().split()[2] in ("Z", "X")
            except FileNotFoundError:
                return True
    # On non-Linux POSIX, psutil identifies zombies without /proc.
    import psutil

    try:
        return psutil.Process(pid).status() in (
            psutil.STATUS_ZOMBIE,
            psutil.STATUS_DEAD,
        )
    except psutil.NoSuchProcess:
        return True


def _run_context_in_thread(*fns) -> tuple[threading.Thread, list[BaseException]]:
    """Run a context in a joined thread so a hang fails instead of blocking.

    Args:
        *fns: The task functions for run_concurrently_context.

    Returns:
        The started thread and the list collecting any raised error.
    """
    errors: list[BaseException] = []

    def _run():
        try:
            with run_concurrently_context(*fns):
                pass
        except BaseException as e:
            errors.append(e)

    runner = threading.Thread(target=_run)
    runner.start()
    return runner, errors


def test_run_concurrently_context_terminates_child_processes():
    """A run-managed child still running at body exit is terminated.

    Regression test for `reflex run` hanging on SIGTERM/SIGINT without a TTY:
    the backend stops but the frontend dev server keeps running, and the exit
    path used to wait on it forever.
    """
    children: dict[str, subprocess.Popen] = {}

    def _task():
        children["child"] = _sleep_child()
        children["child"].wait()

    with run_concurrently_context((_task,)):
        _wait_for_key(children, "child")

    assert children["child"].poll() is not None, "child process was not terminated"
    if sys.platform != "win32":
        assert children["child"].returncode == -signal.SIGTERM


@pytest.mark.skipif(sys.platform == "win32", reason="process-group semantics are POSIX")
def test_run_concurrently_context_terminates_detached_child_tree(tmp_path):
    """A detached child's whole process group - grandchildren too - is torn down.

    Mirrors the dev frontend: bun (group leader) with a node child. Only
    signaling the direct pid used to leave the grandchild alive, holding the
    output pipe open and hanging shutdown.
    """
    pid_file = tmp_path / "grandchild.pid"
    spawner = (
        "import subprocess, sys, time\n"
        "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(g.pid))\n"
        "time.sleep(60)\n"
    )
    children: dict[str, subprocess.Popen] = {}

    def _task():
        children["child"] = processes.new_process(
            [sys.executable, "-c", spawner], run_managed=True, start_new_session=True
        )
        children["child"].wait()

    try:
        with run_concurrently_context((_task,)):
            _wait_for_key(children, "child")
            deadline = time.monotonic() + DEFAULT_TIMEOUT
            while not pid_file.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert pid_file.exists(), "grandchild was never spawned"

        child = children["child"]
        assert child.poll() is not None, "detached child was not terminated"
        grandchild_pid = int(pid_file.read_text().strip())
        deadline = time.monotonic() + DEFAULT_TIMEOUT
        while not _process_gone(grandchild_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert _process_gone(grandchild_pid), (
            f"grandchild {grandchild_pid} survived the child's process-group teardown"
        )
    finally:
        pid_file.unlink(missing_ok=True)
        if "child" in children and children["child"].poll() is None:
            children["child"].kill()
            children["child"].wait()


def test_run_concurrently_context_unblocks_task_streaming_child_output():
    """A task blocked reading a live child's stdout is unblocked on exit.

    Runs in a joined thread so a regression cannot hang the test suite itself.
    """
    children: dict[str, subprocess.Popen] = {}

    def _stream_child_output():
        child = _sleep_child()
        children["child"] = child
        assert child.stdout is not None
        for _line in child.stdout:
            pass

    runner, errors = _run_context_in_thread((_stream_child_output,))
    runner.join(timeout=DEFAULT_TIMEOUT)
    try:
        assert not runner.is_alive(), (
            "context exit hung on a task streaming child process output"
        )
        assert not errors, f"context raised unexpectedly: {errors}"
        _wait_for_key(children, "child")
        assert children["child"].poll() is not None, "child process was not terminated"
    finally:
        child = children.get("child")
        if child is not None and child.poll() is None:
            child.kill()
            child.wait()


def test_run_concurrently_context_terminates_children_on_body_exception():
    """A with-body failure also tears down still-running run-managed children."""
    children: dict[str, subprocess.Popen] = {}

    def _task():
        children["child"] = _sleep_child()
        children["child"].wait()

    with (
        pytest.raises(ValueError, match="body failed"),
        run_concurrently_context((_task,)),
    ):
        _wait_for_key(children, "child")
        msg = "body failed"
        raise ValueError(msg)

    assert children["child"].poll() is not None, "child process was not terminated"


def test_run_concurrently_context_ignores_exited_child_processes():
    """Children that already exited are left alone (no error, no signals)."""
    children: dict[str, subprocess.Popen] = {}
    errors: list[BaseException] = []

    def _task():
        exited = processes.new_process([sys.executable, "-c", "pass"], run_managed=True)
        exited.wait(timeout=DEFAULT_TIMEOUT)
        children["exited"] = exited
        children["live"] = _sleep_child()
        children["live"].wait()

    def _ctx():
        try:
            with run_concurrently_context((_task,)):
                # Exit only after the task recorded the exited child and is
                # blocked on the live one.
                _wait_for_key(children, "live")
        except BaseException as e:
            errors.append(e)

    runner = threading.Thread(target=_ctx)
    runner.start()
    runner.join(timeout=DEFAULT_TIMEOUT)
    assert not runner.is_alive(), "context exit hung on an exited child"
    assert not errors, f"context raised unexpectedly: {errors}"
    assert children["exited"].returncode == 0, "exited child was signaled"
    assert children["live"].poll() is not None


def test_run_concurrently_context_leaves_unmanaged_processes_alone():
    """Children that never opted in to run management are never signaled."""
    children: dict[str, subprocess.Popen] = {}

    def _task():
        children["managed"] = _sleep_child()
        # Same thread, same context - but not run-managed.
        children["unmanaged"] = processes.new_process([
            sys.executable,
            "-c",
            "import time; time.sleep(60)",
        ])
        children["managed"].wait()

    try:
        with run_concurrently_context((_task,)):
            _wait_for_key(children, "unmanaged")
        assert children["managed"].poll() is not None, "managed child survived"
        assert children["unmanaged"].poll() is None, "unmanaged child was terminated"
    finally:
        for child in children.values():
            if child.poll() is None:
                child.kill()
                child.wait()


def test_concurrent_run_contexts_terminate_only_their_own_children():
    """Two live contexts unwind independently; each tears down only its own."""
    children: dict[str, subprocess.Popen] = {}
    finish_b = threading.Event()

    def _task(name):
        children[name] = _sleep_child()
        children[name].wait()

    errors_b: list[BaseException] = []

    def _ctx_b():
        try:
            with run_concurrently_context((lambda: _task("b"),)):
                _wait_for_key(children, "b")
                finish_b.wait(timeout=DEFAULT_TIMEOUT * 4)
        except BaseException as e:
            errors_b.append(e)

    runner_b = threading.Thread(target=_ctx_b)
    runner_b.start()
    runner_a, errors_a = _run_context_in_thread((lambda: _task("a"),))
    try:
        _wait_for_key(children, "b")
        # Context A exits immediately, terminating only its own child while B runs.
        runner_a.join(timeout=DEFAULT_TIMEOUT)
        assert not runner_a.is_alive(), "context A exit hung"
        assert children["a"].poll() is not None, "context A child survived"
        assert children["b"].poll() is None, "context B child was terminated by A"
    finally:
        finish_b.set()
        runner_b.join(timeout=DEFAULT_TIMEOUT)
        for child in children.values():
            if child.poll() is None:
                child.kill()
                child.wait()
    assert not runner_b.is_alive(), "context B exit hung"
    assert errors_a == []
    assert errors_b == []


def test_nested_run_contexts_terminate_inner_children_first():
    """An inner context unwinds its own children while the outer keeps running."""
    children: dict[str, subprocess.Popen] = {}

    def _task(name):
        children[name] = _sleep_child()
        children[name].wait()

    with run_concurrently_context((lambda: _task("outer"),)):
        _wait_for_key(children, "outer")
        with run_concurrently_context((lambda: _task("inner"),)):
            _wait_for_key(children, "inner")
        assert children["inner"].poll() is not None, "inner child survived inner exit"
        assert children["outer"].poll() is None, "outer child died with inner exit"
    assert children["outer"].poll() is not None, "outer child survived outer exit"


def test_run_child_registry_terminates_late_registration():
    """A child registering after termination began is terminated at once."""
    registry = processes._RunChildRegistry()
    first = _sleep_child()
    registry.register(first)
    registry.terminate_all()
    assert first.poll() is not None

    late = _sleep_child()
    try:
        registry.register(late)
        assert late.wait(timeout=DEFAULT_TIMEOUT) is not None, (
            "late-registered child survived registry shutdown"
        )
    finally:
        if late.poll() is None:
            late.kill()
            late.wait()


@pytest.mark.skipif(sys.platform == "win32", reason="process-group semantics are POSIX")
def test_run_child_registry_kills_late_stubborn_tree(tmp_path):
    """A late-registered detached tree that ignores SIGTERM is force-killed."""
    pid_file = tmp_path / "stubborn-gc.pid"
    ready_file = tmp_path / "stubborn-ready"
    spawner = (
        "import signal, subprocess, sys, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "g = subprocess.Popen([sys.executable, '-c', 'import signal, time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(g.pid))\n"
        f"open({str(ready_file)!r}, 'w').write('ready')\n"
        "time.sleep(60)\n"
    )
    registry = processes._RunChildRegistry()
    registry.terminate_all()

    child = processes.new_process(
        [sys.executable, "-c", spawner], run_managed=True, start_new_session=True
    )
    try:
        # Let the child install its SIGTERM handler before the drain starts,
        # so the escalation to SIGKILL - not a startup race - is what ends it.
        deadline = time.monotonic() + DEFAULT_TIMEOUT
        while not ready_file.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready_file.exists(), "stubborn child never became ready"
        registry.register(child)
        # The child ignored SIGTERM; the bounded drain must escalate to SIGKILL.
        assert child.wait(timeout=DEFAULT_TIMEOUT * 2) == -signal.SIGKILL
        deadline = time.monotonic() + DEFAULT_TIMEOUT
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        if pid_file.exists():
            grandchild_pid = int(pid_file.read_text().strip())
            while not _process_gone(grandchild_pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            assert _process_gone(grandchild_pid), (
                "stubborn grandchild survived the late drain"
            )
    finally:
        pid_file.unlink(missing_ok=True)
        ready_file.unlink(missing_ok=True)
        if child.poll() is None:
            child.kill()
            child.wait()


@pytest.mark.skipif(sys.platform == "win32", reason="process-group semantics are POSIX")
def test_run_concurrently_context_reaps_group_of_already_exited_leader(tmp_path):
    """A detached leader that exits before unwind must not strand its group.

    The leader spawns a long-lived grandchild and exits on its own; the
    grandchild keeps the leader's process group alive, so teardown must signal
    the saved pgid even though the leader process is gone.
    """
    pid_file = tmp_path / "orphan-gc.pid"
    spawner = (
        "import subprocess, sys\n"
        "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(g.pid))\n"
    )

    def _task():
        child = processes.new_process(
            [sys.executable, "-c", spawner], run_managed=True, start_new_session=True
        )
        child.wait()  # the leader exits on its own, right after spawning

    grandchild_pid = None
    try:
        with run_concurrently_context((_task,)):
            deadline = time.monotonic() + DEFAULT_TIMEOUT
            while not pid_file.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert pid_file.exists(), "grandchild was never spawned"
        grandchild_pid = int(pid_file.read_text().strip())
        deadline = time.monotonic() + DEFAULT_TIMEOUT
        while not _process_gone(grandchild_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert _process_gone(grandchild_pid), (
            f"grandchild {grandchild_pid} survived teardown of an exited leader"
        )
    finally:
        pid_file.unlink(missing_ok=True)
        if grandchild_pid is not None and not _process_gone(grandchild_pid):
            os.kill(grandchild_pid, signal.SIGKILL)


def test_windows_teardown_tolerates_root_already_gone(monkeypatch):
    """A root that exited before teardown is a documented no-op, not an error."""
    _install_fake_psutil(monkeypatch, None)
    processes._terminate_process_tree_windows(_fake_popen(999), timeout=0.1)


class _FakeProc:
    """A fake psutil.Process for Windows teardown tests."""

    def __init__(
        self,
        pid: int,
        children: list["_FakeProc"] | None = None,
        ignore_terminate: bool = False,
        deny_access: bool = False,
    ):
        """Initialize the fake process.

        Args:
            pid: The fake pid.
            children: Fake descendants.
            ignore_terminate: Whether terminate() is a no-op.
            deny_access: Whether every operation raises AccessDenied.
        """
        self.pid = pid
        self._children = children or []
        self._ignore_terminate = ignore_terminate
        self._deny = deny_access
        self._alive = True
        self.terminated = False
        self.killed = False

    def children(self, recursive: bool = True) -> "list[_FakeProc]":
        """Return the fake descendants.

        Args:
            recursive: Unused; matches psutil.

        Returns:
            The fake children.
        """
        if not self._alive:
            raise _FakeNoSuchProcess(self.pid)
        return list(self._children)

    def terminate(self) -> None:
        """Terminate the fake process unless it is stubborn or protected."""
        if self._deny:
            raise _FakeAccessDenied(self.pid)
        self.terminated = True
        if not self._ignore_terminate:
            self._alive = False

    def kill(self) -> None:
        """Kill the fake process unless it is protected."""
        if self._deny:
            raise _FakeAccessDenied(self.pid)
        self.killed = True
        self._alive = False

    def is_running(self) -> bool:
        """Whether the fake process is alive.

        Returns:
            True while alive.
        """
        return self._alive

    def __eq__(self, other) -> bool:
        """Compare by identity fields.

        Args:
            other: The other object.

        Returns:
            True for the same fake process.
        """
        return isinstance(other, _FakeProc) and other.pid == self.pid


class _FakeNoSuchProcess(Exception):
    """Fake psutil.NoSuchProcess."""


class _FakeAccessDenied(Exception):
    """Fake psutil.AccessDenied."""


class _FakePsutilModule(types.ModuleType):
    """The psutil module surface that Windows process teardown uses."""

    Process: Callable[[int], _FakeProc]
    NoSuchProcess: type[_FakeNoSuchProcess]
    AccessDenied: type[_FakeAccessDenied]
    wait_procs: Callable[
        [list[_FakeProc], int | float | None],
        tuple[list[_FakeProc], list[_FakeProc]],
    ]


def _install_fake_psutil(monkeypatch, root: _FakeProc | None) -> None:
    """Inject a fake psutil and pretend to be on Windows.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        root: The fake root process psutil.Process() returns, or None to
            simulate a root that already exited.
    """
    fake_psutil = _FakePsutilModule("psutil")
    if root is None:

        def _process(pid):
            raise _FakeNoSuchProcess(pid)

        fake_psutil.Process = _process
    else:
        fake_psutil.Process = lambda pid: root
    fake_psutil.NoSuchProcess = _FakeNoSuchProcess
    fake_psutil.AccessDenied = _FakeAccessDenied

    def _wait_procs(procs, timeout=None):
        gone = [proc for proc in procs if not proc.is_running()]
        alive = [proc for proc in procs if proc.is_running()]
        return gone, alive

    fake_psutil.wait_procs = _wait_procs
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    monkeypatch.setattr(sys, "platform", "win32")


def _fake_popen(pid: int) -> mock.Mock:
    """Build a mock Popen with a pid and a live poll.

    Args:
        pid: The fake pid.

    Returns:
        The mock Popen.
    """
    proc = mock.Mock()
    proc.pid = pid
    proc.poll.return_value = None
    return proc


def test_windows_teardown_kills_stubborn_descendant_after_root_exits(monkeypatch):
    """A descendant ignoring terminate is killed even once the root is gone."""
    stubborn = _FakeProc(2, ignore_terminate=True)
    root = _FakeProc(1, children=[stubborn])
    _install_fake_psutil(monkeypatch, root)

    processes._terminate_process_tree_windows(_fake_popen(1), timeout=0.1)

    assert not root.is_running()
    assert stubborn.killed, "descendant that ignored terminate was not killed"


def test_windows_teardown_catches_descendant_spawned_during_teardown(monkeypatch):
    """A descendant appearing after the terminate pass is still swept up."""
    root = _FakeProc(1)
    _install_fake_psutil(monkeypatch, root)
    original_children = root.children
    calls = {"n": 0}

    def _children(recursive: bool = True):
        calls["n"] += 1
        if calls["n"] == 1:
            return []  # no descendants visible during the terminate pass
        return [late]

    late = _FakeProc(2)
    root.children = _children  # type: ignore[method-assign]

    processes._terminate_process_tree_windows(_fake_popen(1), timeout=0.1)

    assert late.killed, "descendant spawned during teardown survived"
    root.children = original_children  # keep the fake reusable


def test_windows_teardown_contains_access_denied(monkeypatch):
    """AccessDenied on one descendant neither aborts nor masks the sweep."""
    protected = _FakeProc(2, deny_access=True)
    normal = _FakeProc(3)
    root = _FakeProc(1, children=[protected, normal])
    _install_fake_psutil(monkeypatch, root)

    processes._terminate_process_tree_windows(_fake_popen(1), timeout=0.1)

    assert not normal.is_running(), "unprotected descendant was not swept"
    assert protected.is_running(), "AccessDenied process should survive untouched"


def test_run_concurrently_context_no_interrupt_after_body_exception():
    """A task failing after the body raised must not interrupt the caller.

    The executor is shut down without waiting, so a task can fail after the
    context has unwound; the caller's own exception must propagate untouched
    instead of a stray KeyboardInterrupt landing in unrelated code.
    """
    task_may_fail = threading.Event()
    interrupt_callback_ran = threading.Event()

    def _fail_on_release():
        # Hold the failure until the context has fully unwound below.
        task_may_fail.wait(timeout=DEFAULT_TIMEOUT)
        raise SystemExit(1)

    with (
        pytest.raises(ValueError, match="body failed"),
        run_concurrently_context(_fail_on_release) as tasks,
    ):
        # Done callbacks run in registration order, so this fires strictly
        # after the context's own interrupt callback has run for the task.
        tasks[0].add_done_callback(lambda _t: interrupt_callback_ran.set())
        msg = "body failed"
        raise ValueError(msg)

    # The context has unwound (in_body cleared); only now may the task fail.
    task_may_fail.set()
    assert interrupt_callback_ran.wait(timeout=DEFAULT_TIMEOUT), (
        "worker task did not finish"
    )
    # A stale interrupt would already have been sent by the callback above;
    # give signal delivery a moment so it would surface as KeyboardInterrupt
    # here (delivery latency is microseconds; 0.1s is generous headroom).
    time.sleep(0.1)


def test_run_concurrently_context_no_interrupt_after_pre_body_failure():
    """A failure racing context entry must not leave the interrupt armed.

    With one task already failed and another still running, the pre-body
    failure check can raise before the body is ever entered; the surviving
    task's later failure must not interrupt the caller after the context has
    unwound. When the fast failure instead loses the race to context entry,
    the body path exercises the same invariant, so both orderings assert
    identically.
    """
    task_may_fail = threading.Event()
    late_finished = threading.Event()

    def _fail_fast():
        raise SystemExit(2)

    def _fail_on_release():
        try:
            task_may_fail.wait(timeout=DEFAULT_TIMEOUT)
            raise SystemExit(3)
        finally:
            late_finished.set()

    with (
        pytest.raises(SystemExit),
        run_concurrently_context(_fail_fast, _fail_on_release),
    ):
        # Reached only when the fast failure loses the race to context entry;
        # its interrupt then surfaces here and converts to the task's error.
        task_may_fail.wait(timeout=DEFAULT_TIMEOUT)

    # The context has unwound; only now may the surviving task fail.
    task_may_fail.set()
    assert late_finished.wait(timeout=DEFAULT_TIMEOUT), "task did not finish"
    # The interrupt callback runs within microseconds of the task finishing;
    # a stale interrupt would surface as KeyboardInterrupt in this window.
    time.sleep(0.1)


def _finished_process(returncode: int, output: str = "ready\n") -> mock.MagicMock:
    """Build a Popen stand-in that has already exited with the given code.

    Args:
        returncode: The exit status the process reports.
        output: The stdout the process produced before exiting.

    Returns:
        A mock that satisfies what stream_logs reads from a Popen.
    """
    process = mock.MagicMock(spec=subprocess.Popen)
    process.__enter__.return_value = process
    process.__exit__.return_value = False
    process.stdout = iter([output])
    process.poll.return_value = returncode
    process.returncode = returncode
    return process


@pytest.mark.parametrize(
    "returncode",
    [
        pytest.param(-signal.SIGINT, id="sigint-direct"),
        pytest.param(128 + signal.SIGINT, id="sigint-via-shell"),
        pytest.param(-signal.SIGTERM, id="sigterm-direct"),
        pytest.param(128 + signal.SIGTERM, id="sigterm-via-shell"),
    ],
)
def test_stream_logs_treats_user_interrupt_as_clean_exit_on_posix(
    returncode: int, caplog, monkeypatch
):
    """On POSIX a child torn down by SIGINT or SIGTERM is an orderly stop.

    Each signal is reported two ways, negative by Popen and 128+N by a shell
    wrapper. SIGINT was accepted in both forms; SIGTERM in neither, so a plain
    `kill -TERM` of `reflex run` logged "Starting frontend failed" and raised
    SystemExit (#6981).

    Args:
        returncode: The signal-derived exit status to check.
        caplog: Pytest log capture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.setattr(processes.constants, "IS_WINDOWS", False)
    process = _finished_process(returncode)

    with caplog.at_level(logging.ERROR):
        lines = list(stream_logs("Starting frontend", process))

    assert lines == ["ready\n"]
    assert caplog.records == []


@pytest.mark.parametrize(
    "returncode",
    [
        pytest.param(-signal.SIGINT, id="sigint-direct"),
        pytest.param(128 + signal.SIGINT, id="sigint-via-shell"),
        pytest.param(15, id="sigterm-terminateprocess"),
    ],
)
def test_stream_logs_treats_user_interrupt_as_clean_exit_on_windows(
    returncode: int, caplog, monkeypatch
):
    """On Windows the accepted set is unchanged: os.kill(pid, SIGTERM) calls
    TerminateProcess with the signal number, so SIGTERM surfaces as a bare 15.

    Args:
        returncode: The exit status to check.
        caplog: Pytest log capture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.setattr(processes.constants, "IS_WINDOWS", True)
    process = _finished_process(returncode)

    with caplog.at_level(logging.ERROR):
        lines = list(stream_logs("Starting frontend", process))

    assert lines == ["ready\n"]
    assert caplog.records == []


@pytest.mark.parametrize(
    "returncode",
    [
        pytest.param(-signal.SIGTERM, id="minus-15"),
        pytest.param(128 + signal.SIGTERM, id="143"),
    ],
)
def test_stream_logs_keeps_posix_sigterm_codes_as_failures_on_windows(
    returncode: int, caplog, monkeypatch
):
    """On Windows -15 and 143 are ordinary application exit codes, not signals.

    Accepting them there would let a genuine frontend failure skip the error
    log and the SystemExit.

    Args:
        returncode: The exit status to check.
        caplog: Pytest log capture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.setattr(processes.constants, "IS_WINDOWS", True)
    process = _finished_process(returncode)

    with caplog.at_level(logging.ERROR), pytest.raises(SystemExit):
        list(stream_logs("Starting frontend", process))

    assert any(
        f"failed with exit code {returncode}" in r.getMessage() for r in caplog.records
    )


def test_stream_logs_still_fails_on_a_real_error_exit(caplog):
    """The relaxed set must not swallow an actual non-zero exit.

    Args:
        caplog: Pytest log capture.
    """
    process = _finished_process(1)

    with caplog.at_level(logging.ERROR), pytest.raises(SystemExit):
        list(stream_logs("Starting frontend", process))

    assert any("failed with exit code 1" in r.getMessage() for r in caplog.records)


def test_windows_kill_job_terminates_tree_after_root_exit(monkeypatch):
    """A kill-on-close job tears down the tree even when the root exited first.

    Job membership is assigned at spawn time, so unlike the psutil sweep it
    stays valid after the root's exit: terminating the job kills descendants
    a dead root can no longer enumerate.
    """
    _install_fake_psutil(monkeypatch, None)  # root already gone for psutil
    terminated_jobs = []
    monkeypatch.setattr(processes, "_create_kill_job", lambda process: 4242)
    monkeypatch.setattr(processes, "_terminate_job", terminated_jobs.append)

    registry = processes._RunChildRegistry()
    root = _fake_popen(777)
    root.poll.return_value = 0  # the root already exited
    registry.register(root)
    registry.terminate_all(timeout=0.1)

    assert terminated_jobs == [4242], (
        "kill-on-close job was not terminated for an exited root"
    )


def test_windows_teardown_never_sweeps_a_reused_exited_root_pid(monkeypatch):
    """An exited Popen cannot grant ownership of a new process at its old PID."""
    unrelated = _FakeProc(1, children=[_FakeProc(2)])
    _install_fake_psutil(monkeypatch, unrelated)
    root = _fake_popen(1)
    root.poll.return_value = 0

    processes._terminate_process_tree_windows(root, timeout=0.1)

    assert not unrelated.terminated
    assert not unrelated._children[0].terminated


def test_windows_teardown_falls_back_to_psutil_without_job(monkeypatch):
    """When job setup fails, the psutil sweep still terminates the tree."""
    child = _FakeProc(2)
    fake_root = _FakeProc(1, children=[child])
    _install_fake_psutil(monkeypatch, fake_root)
    monkeypatch.setattr(processes, "_create_kill_job", lambda process: None)
    terminated_jobs = []
    monkeypatch.setattr(processes, "_terminate_job", terminated_jobs.append)

    registry = processes._RunChildRegistry()
    registry.register(_fake_popen(1))
    registry.terminate_all(timeout=0.1)

    assert terminated_jobs == [], "no job existed, so no job was terminated"
    assert fake_root.terminated, "psutil fallback did not terminate the root"
    assert not child.is_running(), "descendant survived"


@pytest.mark.skipif(sys.platform != "win32", reason="job objects are Windows-only")
def test_create_kill_job_terminates_assigned_process():
    """A real child assigned to a kill-on-close job dies with the job."""
    child = subprocess.Popen(
        ["cmd.exe", "/c", "ping", "-n", "60", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        job = processes._create_kill_job(child)
        assert job is not None, "job setup failed on Windows"
        processes._terminate_job(job)
        child.wait(timeout=DEFAULT_TIMEOUT)
        assert child.poll() is not None, "assigned child survived job termination"
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def test_windows_drain_sweeps_before_terminating_job(monkeypatch):
    """The psutil sweep runs before the job kill, which takes the root down.

    Descendants spawned before the job assignment landed are discoverable
    only while the root is alive, so sweeping after the job kill would miss
    them.
    """
    calls = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        processes,
        "_terminate_process_tree_windows",
        lambda process, timeout: calls.append("sweep"),
    )
    monkeypatch.setattr(processes, "_terminate_job", lambda job: calls.append("job"))

    processes._drain_process_tree(_fake_popen(1), None, 0.1, job=7)

    assert calls == ["sweep", "job"]
