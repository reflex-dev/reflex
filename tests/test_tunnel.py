import pytest

from pynecone.utils import tunnel


@pytest.mark.parametrize(
    "input_string, expected_output",
    [("example.tar.gz", "example"), ("file.zip", "file")],
)
def test_remove_file_extensions(input_string, expected_output):
    output = tunnel.remove_file_extensions(input_string)
    assert output == expected_output


def test_is_port_in_use_socket_error():
    ip = "127.0.0.1"
    port = 8000

    assert tunnel.is_port_in_use(ip, port) is False


def test_find_unused_ports():
    ip_address = "3.101.35.30"
    start_port = 8000
    end_port = 8100
    num_ports = 2

    unused_ports = tunnel.find_unused_ports(ip_address, start_port, end_port, num_ports)

    assert len(unused_ports) == num_ports
    assert all(port >= start_port and port < end_port for port in unused_ports)
    assert all(not tunnel.is_port_in_use(ip_address, port) for port in unused_ports)
