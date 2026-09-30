"""Execute behavioral regressions against the actual frontend event queue."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
@pytest.mark.parametrize("script", ["client_event_queue.mjs", "client_session.mjs"])
def test_client_event_queue(script: str) -> None:
    """Verify frontend queue and session behavior against the actual module.

    Args:
        script: The Node behavioral test suite to execute.
    """
    tests = Path(__file__).parent
    source = (
        tests.parents[2]
        / "packages/reflex-base/src/reflex_base/.templates/web/utils/state.js"
    )
    result = subprocess.run(
        [
            "node",
            "--experimental-vm-modules",
            str(tests / script),
            str(source),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
