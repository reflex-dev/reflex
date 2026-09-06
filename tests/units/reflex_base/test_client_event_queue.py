"""Execute behavioral regressions against the actual frontend event queue."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_client_event_queue() -> None:
    """Verify queue ordering, reconnect handling, and prepend processing cost."""
    tests = Path(__file__).parent
    source = (
        tests.parents[2]
        / "packages/reflex-base/src/reflex_base/.templates/web/utils/state.js"
    )
    result = subprocess.run(
        ["node", str(tests / "client_event_queue.mjs"), str(source)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
