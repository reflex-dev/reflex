import pytest

from pynecone import telemetry
import json


def versiontuple(v):
    return tuple(map(int, (v.split("."))))


def test_telemetry():
    """Test that telemetry is sent correctly."""
    tel = telemetry.Telemetry()

    # Check that the user OS is one of the supported operating systems.
    tel.get_os()

    assert tel.user_os != None
    assert tel.user_os in ["Linux", "Darwin", "Java", "Windows"]

    # Check that the CPU count and memory are greater than 0.
    tel.get_cpu_count()

    assert tel.cpu_count > 0

    # Check that the available memory is greater than 0
    tel.get_memory()

    assert tel.memory > 0

    # Check that the Pynecone version is not None.
    tel.get_python_version()
    assert tel.pynecone_version != None

    # Check that the Python version is greater than 3.7.
    tel.get_pynecone_version()

    assert tel.python_version != None
    assert versiontuple(tel.python_version) >= versiontuple("3.7")

    # Check the json method.
    tel_json = json.loads(tel.json())
    assert tel_json["user_os"] == tel.user_os
    assert tel_json["cpu_count"] == tel.cpu_count
    assert tel_json["memory"] == tel.memory
    assert tel_json["pynecone_version"] == tel.pynecone_version
    assert tel_json["python_version"] == tel.python_version
