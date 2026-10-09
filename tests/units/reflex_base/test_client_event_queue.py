"""Execute behavioral regressions against the actual frontend event queue."""

import shutil
import subprocess
from pathlib import Path

import pytest


def _run_state_js_test(script: str) -> None:
    """Run a Node test script against the frontend state module.

    Args:
        script: The test script name, relative to this directory.
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


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_client_event_queue() -> None:
    """Verify queue behavior and prepend/connected dispatch processing cost."""
    _run_state_js_test("client_event_queue.mjs")


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_state_string_helpers() -> None:
    """Verify the code-point string helpers match Python str semantics."""
    _run_state_js_test("state_string_helpers.mjs")
