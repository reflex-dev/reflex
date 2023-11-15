import json

from nextpy.utils import telemetry


def versiontuple(v):
    return tuple(map(int, (v.split("."))))


def test_telemetry():
    """Test that telemetry is sent correctly."""
    tel = telemetry.Telemetry()

    # Check that the user OS is one of the supported operating systems.
    assert tel.user_os is not None
    assert tel.user_os in ["Linux", "Darwin", "Java", "Windows"]

    # Check that the CPU count and memory are greater than 0.
    assert tel.cpu_count > 0

    # Check that the available memory is greater than 0
    assert tel.memory > 0

    # Check that the Nextpy version is not None.
    assert tel.nextpy_version is not None

    # Check that the Python version is greater than 3.7.
    assert tel.python_version is not None
    assert versiontuple(tel.python_version) >= versiontuple("3.7")

    # Check the json method.
    tel_json = json.loads(tel.json())
    assert tel_json["user_os"] == tel.user_os
    assert tel_json["cpu_count"] == tel.cpu_count
    assert tel_json["memory"] == tel.memory
    assert tel_json["nextpy_version"] == tel.nextpy_version
    assert tel_json["python_version"] == tel.python_version


def test_disable():
    """Test that disabling telemetry works."""
    assert not telemetry.send("test", telemetry_enabled=False)
