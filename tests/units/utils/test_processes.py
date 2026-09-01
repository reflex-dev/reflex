"""Test process utilities."""

import socket
import threading
import time
from contextlib import closing
from unittest import mock

import pytest

from reflex.testing import DEFAULT_TIMEOUT, AppHarness
from reflex.utils.processes import (
    is_process_on_port,
    run_concurrently,
    run_concurrently_context,
)


def _ipv6_available() -> bool:
    """Check whether the host can actually bind IPv6 sockets.

    `socket.has_ipv6` only reflects build-time support; sandboxes and containers
    frequently compile it in but have no IPv6 stack, which makes
    `is_process_on_port` report every port as occupied.

    Returns:
        Whether an IPv6 socket can be created and bound.
    """
    try:
        with closing(socket.socket(socket.AF_INET6, socket.SOCK_STREAM)) as sock:
            sock.bind(("", 0))
    except OSError:
        return False
    return True


requires_ipv6 = pytest.mark.skipif(
    not _ipv6_available(), reason="IPv6 is not available on this system"
)


@requires_ipv6
def test_is_process_on_port_free_port():
    """Test is_process_on_port returns False when port is free."""
    # Find a free port
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("", 0))
        free_port = sock.getsockname()[1]

    # Port should be free after socket is closed
    assert not is_process_on_port(free_port)


@requires_ipv6
def test_is_process_on_port_occupied_port():
    """Test is_process_on_port returns True when port is occupied."""
    # Create a server socket to occupy a port
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("", 0))
    server_socket.listen(1)

    occupied_port = server_socket.getsockname()[1]

    try:
        # Port should be occupied
        assert is_process_on_port(occupied_port)
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


@requires_ipv6
def test_is_process_on_port_both_protocols():
    """Test is_process_on_port detects occupation on either IPv4 or IPv6."""
    # Create IPv4 server
    ipv4_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ipv4_socket.bind(("", 0))
    ipv4_socket.listen(1)

    port = ipv4_socket.getsockname()[1]

    try:
        # Should detect IPv4 occupation
        assert is_process_on_port(port)
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


@requires_ipv6
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
            lambda: shared is not None and is_process_on_port(shared)
        )
    finally:
        do_close.set()
        thread.join(timeout=DEFAULT_TIMEOUT)

    # Give it a moment for the socket to be fully released
    assert AppHarness._poll_for(
        lambda: shared is not None and not is_process_on_port(shared)
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
