"""Tests for the delta.js frontend template helper."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

DELTA_JS_TEMPLATE = (
    Path(__file__).parents[3]
    / "packages/reflex-base/src/reflex_base/.templates/web/utils/helpers/delta.js"
)
DELTA_JS_CASES = Path(__file__).parent / "delta_js_cases.mjs"


@pytest.fixture(scope="module")
def delta_js_results() -> dict[str, bool]:
    """Run the applyDelta test cases with node.

    Returns:
        A mapping of case name to whether the case passed.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    output = subprocess.run(
        [node, str(DELTA_JS_CASES), str(DELTA_JS_TEMPLATE)],
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return json.loads(output)


def test_delta_js_cases_are_collected(delta_js_results: dict[str, bool]) -> None:
    """The node harness should report every case it defines."""
    expected = DELTA_JS_CASES.read_text().count("\ncheck(")
    assert len(delta_js_results) == expected


def test_apply_delta_skips_equivalent_values(delta_js_results: dict[str, bool]) -> None:
    """Deltas that do not differ from the saved state should not be applied.

    Returning the same state object lets ``useReducer`` bail out of the
    re-render, and reusing the saved value for unchanged keys keeps memoized
    consumers of those vars from invalidating.
    """
    failed = sorted(name for name, passed in delta_js_results.items() if not passed)
    assert not failed, f"applyDelta cases failed: {', '.join(failed)}"


def test_state_js_reexports_apply_delta() -> None:
    """``applyDelta`` must stay importable from ``$/utils/state``."""
    state_js = (DELTA_JS_TEMPLATE.parents[1] / "state.js").read_text()
    assert 'export { applyDelta } from "$/utils/helpers/delta";' in state_js
