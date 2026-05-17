"""End-to-end tests for the PyO3 Component reader (pyread).

Build small Reflex pages from real ``Component`` classes, run them through
``CompilerSession.compile_page_from_component`` (the pyread path — plan
§0b lever (a)), and assert the rendered JSX contains the expected
tag/text/props. Originally tested the now-deleted msgpack bridge; the
asserts are unchanged because pyread is byte-identical on every shape
this file exercises.
"""

from __future__ import annotations

import pytest

# Skip the whole module if reflex_base imports fail (e.g., on a minimal
# environment that doesn't have the components installed).
pytest.importorskip("reflex_base")
pytest.importorskip("reflex_components_core")
pytest.importorskip("reflex_compiler_rust._native")


import reflex as rx
from reflex.compiler.session import CompilerSession


@pytest.fixture(scope="module")
def session() -> CompilerSession:
    return CompilerSession()


def _render(session: CompilerSession, ident: str, route: str, component) -> str:
    return session.compile_page_from_component(ident, component, route)


def test_pyread_text(session: CompilerSession) -> None:
    """A bare string in a component tree should round-trip as IR Text."""
    component = rx.text("hello world")
    js = _render(session, "Index", "/index", component)
    assert "hello world" in js


def test_pyread_box(session: CompilerSession) -> None:
    """A simple Box wrapping a string."""
    component = rx.box("inside")
    js = _render(session, "Box", "/box", component)
    assert "inside" in js
    # The emitted JS calls `jsx(<TagName>, …)`.
    assert "jsx(" in js


def test_pyread_nested(session: CompilerSession) -> None:
    """Nested boxes should produce nested jsx() calls."""
    component = rx.box(rx.box("inner"))
    js = _render(session, "Nested", "/nested", component)
    assert js.count("jsx(") >= 2  # outer + inner
    assert "inner" in js


def test_pyread_multiple_children(session: CompilerSession) -> None:
    component = rx.box(
        rx.text("first"),
        rx.text("second"),
        rx.text("third"),
    )
    js = _render(session, "Multi", "/multi", component)
    assert "first" in js and "second" in js and "third" in js


def test_pyread_var_data_imports_propagate(session: CompilerSession) -> None:
    """Plain page emit should still include the baseline React-runtime header."""
    component = rx.box("hello")
    js = _render(session, "Var", "/var", component)
    # The basic React-runtime import header is always there.
    assert 'import { Fragment, useContext, useRef } from "react";' in js
    # Module export always present (always named "Component" since v2).
    assert "export default function Component()" in js


class _PyReadState(rx.State):
    logged_in: bool = False
    items: list[str] = []
    mode: str = "x"


def test_pyread_cond(session: CompilerSession) -> None:
    component = rx.cond(_PyReadState.logged_in, rx.text("welcome"), rx.text("login"))
    js = _render(session, "Cond", "/cond", component)
    # Ternary emit.
    assert "?" in js and ":" in js
    assert "welcome" in js and "login" in js
    # State var should appear in the rendered expression.
    assert "logged_in" in js


def test_pyread_foreach(session: CompilerSession) -> None:
    component = rx.foreach(_PyReadState.items, lambda item: rx.text(item))
    js = _render(session, "List", "/list", component)
    # `.map(...)` per §4.8.
    assert ".map((" in js
    # The item arg name (`item` + FIELD_MARKER) should be in the body.
    assert "item" in js


def test_pyread_match(session: CompilerSession) -> None:
    component = rx.match(
        _PyReadState.mode,
        ("a", rx.text("alpha")),
        ("b", rx.text("beta")),
        rx.text("other"),
    )
    js = _render(session, "M", "/m", component)
    # Rust emits `match_template(...)` — we wired this in §4.8.
    assert "match_template(" in js
    assert "alpha" in js and "beta" in js and "other" in js
