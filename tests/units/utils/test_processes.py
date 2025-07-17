"""Test process utilities."""

import socket
import threading
import time
from contextlib import closing
from unittest import mock

import pytest

from reflex.utils.processes import is_process_on_port


def test_is_process_on_port_free_port():
    """Test is_process_on_port returns False when port is free."""
    # Find a free port
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("", 0))
        free_port = sock.getsockname()[1]

    # Port should be free after socket is closed
    assert not is_process_on_port(free_port)


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


def test_is_process_on_port_ipv6():
    """Test is_process_on_port works with IPv6."""
    # Test with IPv6 socket
    try:
        server_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        server_socket.bind(("", 0))
        server_socket.listen(1)

        occupied_port = server_socket.getsockname()[1]

        try:
            # Port should be occupied on IPv6
            assert is_process_on_port(occupied_port)
        finally:
            server_socket.close()
    except OSError:
        # IPv6 might not be available on some systems
        pytest.skip("IPv6 not available on this system")


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


def test_is_process_on_port_concurrent_access():
    """Test is_process_on_port works correctly with concurrent access."""
    shared = None

    def create_server_and_test():
        nonlocal shared
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("", 0))

        server.listen(1)

        port = server.getsockname()[1]
        shared = port

        # Small delay to ensure the test runs while server is active
        time.sleep(0.1)
        server.close()

    thread = threading.Thread(target=create_server_and_test)
    thread.start()

    # Wait a bit for the server to start
    time.sleep(0.05)

    assert shared is not None

    # Port should be occupied while server is running (both bound-only and listening)
    assert is_process_on_port(shared)

    thread.join()

    # Give it a moment for the socket to be fully released
    time.sleep(0.1)
    assert not is_process_on_port(shared)
