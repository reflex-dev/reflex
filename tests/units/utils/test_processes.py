"""Test process utilities."""

import contextlib
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from contextlib import closing
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


def test_frontend_registry_stops_late_enrollment_once(monkeypatch):
    """A worker racing shutdown cannot orphan a frontend or stop it twice."""
    stopped = []
    monkeypatch.setattr(processes, "_stop_frontend", stopped.append)
    registry = processes._FrontendRegistry()
    first = mock.Mock(spec=subprocess.Popen)
    late = mock.Mock(spec=subprocess.Popen)
    registry.register(first)
    registry.stop_all()
    registry.register(late)
    registry.stop_all()
    assert stopped == [first, late]


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


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_frontend_group_ends_with_run_context(tmp_path):
    """The opted-in frontend and its child are both stopped at context exit."""
    grandchild_pid = tmp_path / "grandchild.pid"
    ready = threading.Event()
    root: list[subprocess.Popen[str]] = []

    def frontend():
        code = (
            "import subprocess,sys,time\n"
            "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\n"
            f"open({str(grandchild_pid)!r},'w').write(str(p.pid))\n"
            "time.sleep(60)\n"
        )
        p = subprocess.Popen(
            [sys.executable, "-c", code],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        root.append(p)
        processes.track_frontend(p)
        ready.set()
        p.wait()

    with run_concurrently_context(frontend):
        assert ready.wait(DEFAULT_TIMEOUT)
        deadline = time.monotonic() + DEFAULT_TIMEOUT
        while not grandchild_pid.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert grandchild_pid.exists()
    assert root[0].poll() is not None
    grandchild = int(grandchild_pid.read_text())
    deadline = time.monotonic() + DEFAULT_TIMEOUT
    while time.monotonic() < deadline:
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            break
        # The orphan may remain a zombie until init reaps it.
        import psutil

        if psutil.Process(grandchild).status() == psutil.STATUS_ZOMBIE:
            break
        time.sleep(0.05)
    else:
        with contextlib.suppress(ProcessLookupError):
            os.kill(grandchild, signal.SIGKILL)
        pytest.fail("frontend grandchild remained runnable")


def test_run_context_leaves_untracked_process_alone():
    """A child without frontend opt-in is not stopped by cleanup."""
    child = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
    try:
        with run_concurrently_context(lambda: None):
            pass
        assert child.poll() is None
    finally:
        child.terminate()
        child.wait(timeout=DEFAULT_TIMEOUT)
