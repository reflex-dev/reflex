"""Tests for the Python IR builder and the Rust round-trip.

These are unit tests of :mod:`reflex.compiler.ir.builder`, plus integration
checks that send the built IR through the Rust ``CompilerSession`` and look
at the rendered JS source.

The integration checks skip cleanly when the Rust wheel isn't installed so
contributors without the wheel can still run the unit subset.
"""

from __future__ import annotations

import re

import pytest

from reflex.compiler.ir import builder as ir
from reflex.compiler.ir import canonical, pack, schema
from reflex.compiler.session import CompilerSession


def test_text_node_shape() -> None:
    node = ir.text("hello")
    assert node[0] == schema.COMPONENT_TEXT
    assert node[1] == "hello"
    # The node id was auto-derived from the canonical hash.
    assert isinstance(node[2], int) and node[2] != 0


def test_node_id_is_stable_across_builds() -> None:
    a = ir.text("hello")
    b = ir.text("hello")
    assert a[2] == b[2]


def test_node_id_changes_with_content() -> None:
    a = ir.text("alpha")
    b = ir.text("beta")
    assert a[2] != b[2]


def test_element_packs_props_and_children() -> None:
    node = ir.element(
        "div",
        props=[("id", ir.js_expr("\"main\""))],
        children=[ir.text("inner")],
    )
    assert node[0] == schema.COMPONENT_ELEMENT
    assert node[1] == "div"
    # one prop
    assert len(node[2]) == 1 and node[2][0][0] == "id"
    # one child, which is a Text node
    assert len(node[3]) == 1 and node[3][0][0] == schema.COMPONENT_TEXT


def test_page_shape() -> None:
    page = ir.page(route="/index", root=ir.text("x"))
    assert page[0] == schema.SCHEMA_VERSION
    assert page[1] == "/index"
    assert page[2][0] == schema.COMPONENT_TEXT


def test_pack_returns_bytes() -> None:
    page = ir.page(route="/index", root=ir.text("x"))
    blob = pack.pack_page(page)
    assert isinstance(blob, bytes) and len(blob) > 0


def test_canonical_hash_is_deterministic() -> None:
    page_a = ir.page(route="/index", root=ir.text("x"))
    page_b = ir.page(route="/index", root=ir.text("x"))
    assert canonical.hash_ir_subtree(page_a) == canonical.hash_ir_subtree(page_b)


# ---- Rust round-trip (skip when wheel missing) ------------------------------

pytest.importorskip("reflex_compiler_rust._native")


@pytest.fixture(scope="module")
def session() -> CompilerSession:
    return CompilerSession()


def test_round_trip_emits_text(session: CompilerSession) -> None:
    page = ir.page(route="/index", root=ir.text("hello"))
    js = session.compile_page_ir("Index", page)
    assert "export default function Component()" in js
    assert 'export const __reflex_route_ident = "Index"' in js
    assert "\"hello\"" in js
    assert "export const __reflex_route = \"/index\"" in js


def test_round_trip_emits_element(session: CompilerSession) -> None:
    page = ir.page(
        route="/about",
        root=ir.element(
            "div",
            props=[("className", ir.js_expr("\"container\""))],
            children=[ir.text("about page")],
        ),
    )
    js = session.compile_page_ir("About", page)
    assert "jsx(div, {className: \"container\"}, \"about page\")" in js


def test_round_trip_emits_foreach(session: CompilerSession) -> None:
    page = ir.page(
        route="/list",
        root=ir.foreach(
            ir.js_expr("items"),
            ir.text("item"),
        ),
    )
    js = session.compile_page_ir("List", page)
    # Foreach emits `(iter).map((item, index) => body)`.
    assert "(items).map((item, index) =>" in js


def test_round_trip_emits_cond(session: CompilerSession) -> None:
    page = ir.page(
        route="/cond",
        root=ir.cond(
            ir.js_expr("loggedIn"),
            ir.text("welcome back"),
            ir.text("please log in"),
        ),
    )
    js = session.compile_page_ir("Cond", page)
    assert "loggedIn" in js
    # Ternary: ((test) ? then : else_)
    assert "?" in js and ":" in js


def test_round_trip_dedups_imports(session: CompilerSession) -> None:
    page = ir.page(
        route="/x",
        root=ir.fragment(
            [
                ir.element("div", props=[("x", ir.js_expr("a"))]),
                ir.element("span", props=[("y", ir.js_expr("b"))]),
            ]
        ),
        # Each Element would push (react, useState); the Rust codegen dedupes
        # on its way into the import block.
        component_imports=[("react", "useState"), ("react", "useState")],
    )
    js = session.compile_page_ir("X", page)
    # The Rust codegen merges the harvested ``(react, useState)`` pair onto
    # the same import line as the baseline ``react`` runtime aliases and
    # collapses the duplicate, so the page module ends up with one ``react``
    # import line containing ``useState`` exactly once.
    react_imports = re.findall(r'^import \{[^}]*\} from "react";', js, re.MULTILINE)
    assert len(react_imports) == 1, f"expected one react import, got {react_imports!r}\n{js}"
    assert react_imports[0].count("useState") == 1, (
        f"useState appears more than once in {react_imports[0]!r}\n{js}"
    )


def test_cache_warm_is_fast(session: CompilerSession) -> None:
    """Warm-cache hit reads the Arc without re-parsing or re-emitting."""
    page = ir.page(route="/perf", root=ir.text("hi"))
    blob = pack.pack_page(page)
    session.clear_cache()
    assert session.cache_len() == 0
    session.compile_page_bytes("Perf", blob)
    assert session.cache_len() == 1
    # Compiling again should not bump the cache.
    session.compile_page_bytes("Perf", blob)
    assert session.cache_len() == 1
