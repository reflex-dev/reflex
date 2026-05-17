"""Smoke tests for `CompilerSession.compile_memo_from_component`.

Phase 3 of the memoize port (plan §0b lever (b3)) is the
``memo_single_component_template`` replacement: pyread walks a wrapper
Component and `emit_memo_module` produces the
``export const <name> = memo(...)`` shell.

The tests here exercise the public entry point against a few real
wrapper shapes built via the legacy
``create_passthrough_component_memo``. They assert structural properties
of the rust output — exported name, ``memo(({ children })`` shell, the
``children`` placeholder reaching the call site, and the right imports.
Byte-equality against the legacy template isn't enforced because the
templates differ in whitespace.
"""

from __future__ import annotations

import copy

import pytest

pytest.importorskip("reflex_base")
pytest.importorskip("reflex_components_core")
pytest.importorskip("reflex_compiler_rust._native")

import reflex as rx
from reflex.compiler.session import CompilerSession
from reflex.experimental.memo import create_passthrough_component_memo


class _MemoState(rx.State):
    n: int = 0
    items: list[str] = []

    @rx.event
    def bump(self) -> None:
        self.n += 1


def _build_body(component):
    """Return the memo body Component with the `{children}` hole substituted in."""
    _, defn = create_passthrough_component_memo(component)
    body = copy.copy(defn.component)
    if defn.passthrough_hole_child is not None:
        body.children = [defn.passthrough_hole_child]
    return defn, body


@pytest.fixture(scope="module")
def session() -> CompilerSession:
    return CompilerSession()


def test_memo_button_with_event_handler(session: CompilerSession) -> None:
    """A button with an event handler memos into a `memo(({ children }))` module."""
    defn, body = _build_body(rx.button("click", on_click=_MemoState.bump))
    js = session.compile_memo_from_component(
        defn.export_name, "({ children })", body
    )
    assert f"export const {defn.export_name} = memo(({{ children }})" in js
    assert "addEvents" in js  # event handler hook used inside memo body
    assert 'import { memo, useContext, useRef } from "react";' in js
    assert "RadixThemesButton" in js
    # the placeholder reaches the JSX call site as a free `children` identifier
    assert ", children)" in js


def test_memo_box_with_state_child(session: CompilerSession) -> None:
    """A box wrapping a state-bearing child memos with `children` placeholder.

    The state-referring text gets substituted into the `{children}` hole at
    wrapper-build time, so the memo body renders `<Box>{children}</Box>` and
    holds no direct StateContexts binding — the state binding lives on the
    page-level call site, not inside the memo.
    """
    defn, body = _build_body(rx.box(rx.text(_MemoState.n.to(str))))
    js = session.compile_memo_from_component(defn.export_name, "({ children })", body)
    assert defn.export_name in js
    assert "memo(" in js
    assert "RadixThemesBox" in js
    assert ", children)" in js


def test_memo_snapshot_signature(session: CompilerSession) -> None:
    """Snapshot memos use `()` signature, not `({ children })`."""
    defn, body = _build_body(rx.text("static"))
    js = session.compile_memo_from_component(defn.export_name, "()", body)
    assert "memo(()" in js
    assert "({ children })" not in js
