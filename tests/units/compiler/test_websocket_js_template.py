"""Regression tests for the websocket.js frontend transport template."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_websocket_session_lifecycle() -> None:
    """Execute the transport's session open and reconnect tests against the real template."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the frontend runtime tests")
    result = subprocess.run(
        [
            node,
            "--experimental-vm-modules",
            str(Path(__file__).with_name("websocket_js.test.mjs")),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
