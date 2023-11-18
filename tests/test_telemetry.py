from reflex.utils import telemetry


def versiontuple(v):
    return tuple(map(int, (v.split("."))))


def test_telemetry():
    """Test that telemetry is sent correctly."""
    # Check that the user OS is one of the supported operating systems.
    user_os = telemetry.get_os()
    assert user_os is not None
    assert user_os in ["Linux", "Darwin", "Java", "Windows"]

    # Check that the CPU count and memory are greater than 0.
    assert telemetry.get_cpu_count() > 0

    # Check that the available memory is greater than 0
    assert telemetry.get_memory() > 0

    # Check that the Reflex version is not None.
    assert telemetry.get_reflex_version() is not None

    # Check that the Python version is greater than 3.7.
    python_version = telemetry.get_python_version()
    assert python_version is not None
    assert versiontuple(python_version) >= versiontuple("3.7")


def test_disable():
    """Test that disabling telemetry works."""
    assert not telemetry.send("test", telemetry_enabled=False)
