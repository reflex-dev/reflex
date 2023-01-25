import pytest

from pynecone import utils


def test_os():
    """Test that the OS is detected correctly."""
    assert utils.get_os() != None
    assert utils.get_os() in ["Linux", "Darwin", "Java", "Windows"]


def versiontuple(v):
    return tuple(map(int, (v.split("."))))


def test_python_version():
    """Test that the Python version is detected correctly."""
    assert utils.get_python_version() != None
    assert versiontuple(utils.get_python_version()) >= versiontuple("3.7")


def test_telemetry():
    """Test that telemetry is sent correctly."""
    payload = utils.add_telemetry()
    assert payload["pynecone_version"] != None
    assert payload["python_version"] != None
    assert payload["os"] != None
    assert payload["cpu_count"] > 0
    assert payload["memory"] > 0
