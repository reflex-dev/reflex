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


def test_repeated_page_evaluation_isolates_compiler_mutations():
    """Metadata, child edits, and styles must not contaminate future evaluations."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import reflex as rx
from reflex.compiler.utils import add_meta
from reflex_docs.reflex_docs import app

page = next(
    page for route, page in app._unevaluated_pages.items()
    if "state-structure/component-state" in route
)
first = page.component()
original_count = len(first.children)
original_child_count = len(first.children[0].children)
original_style = dict(first.children[0].style)
before = {state.get_full_name() for state in rx.State.get_substates()}
add_meta(first, title="First compile", image="first.png", meta=[])
first.children[0].children.append(rx.el.div("compile-only child"))
first.children[0].style["marginTop"] = "937px"
second = page.component()
assert len(second.children) == original_count
assert len(second.children[0].children) == original_child_count
assert dict(second.children[0].style) == original_style
assert {state.get_full_name() for state in rx.State.get_substates()} == before
add_meta(second, title="Second compile", image="second.png", meta=[])
third = page.component()
assert len(third.children) == original_count
assert dict(third.children[0].style) == original_style
""",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
