"""Tests for the source-map round-trip through CompilerSession."""

from __future__ import annotations

import pytest

pytest.importorskip("reflex_compiler_rust._native")

from reflex.compiler.ir import builder as ir
from reflex.compiler.session import CompilerSession


@pytest.fixture(scope="module")
def session() -> CompilerSession:
    return CompilerSession()


def test_synthetic_locs_produce_empty_map(session: CompilerSession) -> None:
    page = ir.page(route="/x", root=ir.text("hello"))
    js, mappings = session.compile_page_with_sourcemap("X", page)
    assert "hello" in js
    assert mappings == []


def test_real_loc_recorded(session: CompilerSession) -> None:
    text = ir.text("hi", loc=ir.source_loc(file_id=7, line=42, col=11))
    page = ir.page(route="/x", root=text)
    js, mappings = session.compile_page_with_sourcemap("X", page)
    assert "hi" in js
    assert len(mappings) >= 1
    offset, file_id, line, col = mappings[0]
    assert file_id == 7
    assert line == 42
    assert col == 11
    # The recorded offset should land on or just before the JS string literal.
    rendered_text_pos = js.index('"hi"')
    assert offset <= rendered_text_pos


def test_nested_components_record_multiple_locs(session: CompilerSession) -> None:
    inner = ir.text("inner", loc=ir.source_loc(file_id=1, line=10, col=1))
    outer = ir.element(
        "div",
        children=[inner],
        loc=ir.source_loc(file_id=1, line=5, col=1),
    )
    page = ir.page(route="/x", root=outer)
    js, mappings = session.compile_page_with_sourcemap("X", page)
    # Two distinct source lines should produce at least two entries.
    lines = {line for _, _, line, _ in mappings}
    assert {5, 10}.issubset(lines)
