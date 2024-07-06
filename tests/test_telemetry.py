import pytest
from packaging.version import parse as parse_python_version

from reflex.utils import telemetry


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
    assert parse_python_version(python_version) >= parse_python_version("3.7")


def test_disable():
    """Test that disabling telemetry works."""
    assert not telemetry._send("test", telemetry_enabled=False)


@pytest.mark.parametrize("event", ["init", "reinit", "run-dev", "run-prod", "export"])
def test_send(mocker, event):
    httpx_post_mock = mocker.patch("httpx.post")
    # mocker.patch(
    #     "builtins.open",
    #     mocker.mock_open(
    #         read_data='{"project_hash": "78285505863498957834586115958872998605"}'
    #     ),
    # )

    # Mock the read_text method of Path
    pathlib_path_read_text_mock = mocker.patch(
        "pathlib.Path.read_text",
        return_value='{"project_hash": "78285505863498957834586115958872998605"}',
    )

    mocker.patch("platform.platform", return_value="Mocked Platform")

    telemetry._send(event, telemetry_enabled=True)
    httpx_post_mock.assert_called_once()

    pathlib_path_read_text_mock.assert_called_once()
