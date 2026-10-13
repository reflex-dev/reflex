"""Execute behavioral regressions against the actual frontend runtime."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
@pytest.mark.parametrize(
    "script",
    [
        "client_event_queue.mjs",
        "client_state_updates.mjs",
        "state_string_helpers.mjs",
    ],
)
def test_client_runtime(script: str) -> None:
    """Verify queue processing, incoming state updates, and string helpers.

    Args:
        script: Runtime regression script to execute.
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
