"""Regression tests for reflex/utils/exec.py."""

from unittest.mock import MagicMock

import pytest

from reflex.utils import exec


@pytest.mark.parametrize(
    ("vite_log_line", "expected_url"),
    [
        ("  Local:   http://localhost:3000/", "http://localhost:3000/"),
        (
            "  Local:   http://localhost:3000/withslash/",
            "http://localhost:3000/withslash/",
        ),
        # No leading slash: Vite still bakes the path, must not be doubled.
        ("  Local:   http://localhost:3000/noslash/", "http://localhost:3000/noslash/"),
        ("  Local:   http://localhost:3000/a/b/", "http://localhost:3000/a/b/"),
    ],
)
def test_vite_url_captured_without_doubling(
    mocker, vite_log_line: str, expected_url: str
):
    """Vite's log URL already contains the frontend_path; exec.py must not append it again.

    Args:
        mocker: Pytest mocker fixture.
        vite_log_line: A simulated line from the Vite dev-server stdout.
        expected_url: The URL that should be passed to notify_frontend.
    """
    mocker.patch("reflex.utils.exec.get_web_dir")
    mocker.patch(
        "reflex.utils.exec.get_package_json_and_hash", return_value=({}, "fake-hash")
    )
    mock_process = MagicMock()
    mock_process.stdout = True
    mocker.patch("reflex.utils.processes.new_process", return_value=mock_process)
    mocker.patch("reflex.utils.processes.stream_logs", return_value=[vite_log_line])
    mocker.patch(
        "reflex.utils.exec.get_config", return_value=MagicMock(frontend_path="noslash")
    )
    mock_notify_frontend = mocker.patch("reflex.utils.exec.notify_frontend")
    mocker.patch("reflex.utils.exec.notify_backend")

    exec.run_process_and_launch_url(["npm", "run", "dev"])

    mock_notify_frontend.assert_called_once_with(expected_url, True)
