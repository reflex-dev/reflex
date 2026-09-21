"""Keep XY startup page evaluation from creating uncompiled demo states."""

import subprocess
import sys
from pathlib import Path


def test_repeated_page_evaluation_preserves_component_states():
    """A second plugin evaluation must not create new frontend state names."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import reflex as rx
from reflex_docs.reflex_docs import app

page = next(
    page for route, page in app._unevaluated_pages.items()
    if "state-structure/component-state" in route
)
page.component()
before = {state.get_full_name() for state in rx.State.get_substates()}
page.component()
after = {state.get_full_name() for state in rx.State.get_substates()}
assert after == before, sorted(after - before)
""",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
