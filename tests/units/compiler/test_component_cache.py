"""Tests for the experimental static-subtree component construction cache."""

import dataclasses
from collections.abc import Callable
from typing import Any

from reflex_base.components.component import Component
from reflex_base.plugins import CompileContext, CompilerHooks

import reflex as rx
from reflex.compiler import component_cache
from reflex.compiler.plugins import default_page_plugins


@dataclasses.dataclass(slots=True)
class _FakePage:
    route: str
    component: Callable[[], Component]
    title: Any = None
    description: Any = None
    image: str = ""
    meta: tuple[dict[str, Any], ...] = ()
    _source_module: str | None = None


def _static_footer() -> Component:
    return rx.el.footer(
        rx.el.span("© Reflex"),
        rx.el.a("Docs", href="/docs"),
        class_name="footer",
    )


def _page_a() -> Component:
    return rx.el.div(rx.el.h1("Page A"), _static_footer())


def _page_b() -> Component:
    return rx.el.div(rx.el.h1("Page B"), _static_footer())


def _compile_pages(pages: list[_FakePage]) -> dict[str, str]:
    ctx = CompileContext(
        pages=pages,
        hooks=CompilerHooks(plugins=default_page_plugins()),
    )
    with ctx:
        ctx.compile()
    return {r: (pc.output_code or "") for r, pc in ctx.compiled_pages.items()}


def test_value_signature_scalars():
    assert component_cache._value_signature("a") == repr("a")
    assert component_cache._value_signature(1) == repr(1)
    assert component_cache._value_signature(1.5) == repr(1.5)
    assert component_cache._value_signature(True) == repr(True)
    assert component_cache._value_signature(None) == repr(None)


def test_value_signature_containers():
    assert component_cache._value_signature([1, "a"]) is not None
    # order-independent for dicts
    a = component_cache._value_signature({"x": 1, "y": 2})
    b = component_cache._value_signature({"y": 2, "x": 1})
    assert a == b
    # a non-literal anywhere poisons the whole value
    assert component_cache._value_signature([1, object()]) is None
    assert component_cache._value_signature({"x": object()}) is None


def test_value_signature_constant_var_vs_state_var():
    # a constant Var (no var data) is signable
    const = rx.Var.create("x")
    assert component_cache._value_signature(const) is not None
    # a state-bound Var carries var data -> not static
    state_var = SigState.value  # type: ignore[attr-defined]
    assert component_cache._value_signature(state_var) is None


class SigState(rx.State):
    """State used to produce a state-bound Var for signature tests."""

    value: str = ""


def test_signature_static_vs_dynamic():
    component_cache.reset()
    child = rx.el.span("hi")
    component_cache._SIG_BY_ID[id(child)] = "child-sig"
    sig = component_cache.signature(rx.el.div, [child], {"class_name": "foo"})
    assert sig is not None
    # different prop -> different signature
    assert component_cache.signature(rx.el.div, [child], {"class_name": "bar"}) != sig
    # a state-bound prop -> not cacheable
    assert (
        component_cache.signature(rx.el.div, [child], {"class_name": SigState.value})
        is None
    )


def test_signature_unknown_child_is_dynamic():
    component_cache.reset()
    # a child that was never registered (no signature) -> uncacheable
    assert component_cache.signature(rx.el.div, [rx.el.span("x")], {}) is None


def test_install_uninstall_round_trip():
    from reflex_base.components.component import Component

    original = Component._create
    component_cache.reset()
    component_cache.install()
    assert Component._create.__func__ is not original.__func__  # type: ignore[attr-defined]
    # double install is a no-op
    component_cache.install()
    component_cache.uninstall()
    assert Component._create.__func__ is original.__func__  # type: ignore[attr-defined]
    # double uninstall is safe
    component_cache.uninstall()
    assert Component._create.__func__ is original.__func__  # type: ignore[attr-defined]


def test_static_subtree_is_reused():
    component_cache.reset()
    component_cache.install()
    try:
        first = rx.el.div("shared", class_name="footer")
        second = rx.el.div("shared", class_name="footer")
    finally:
        component_cache.uninstall()
    # identical static call returns the SAME cached object
    assert first is second
    assert component_cache.STATS["hits"] >= 1


def test_dynamic_subtree_is_not_reused():
    component_cache.reset()
    component_cache.install()
    try:
        first = rx.el.div(SigState.value, class_name="dyn")
        second = rx.el.div(SigState.value, class_name="dyn")
    finally:
        component_cache.uninstall()
    # a state-bound subtree is rebuilt each time (no signature)
    assert first is not second


def test_nested_static_propagates_and_caches_parent():
    component_cache.reset()
    component_cache.install()
    try:
        a = rx.el.div(rx.el.span("x"), class_name="card")
        b = rx.el.div(rx.el.span("x"), class_name="card")
    finally:
        component_cache.uninstall()
    # the inner span signature propagates so the parent div is cached too
    assert a is b


def test_end_to_end_shared_chrome_is_byte_identical():
    pages = [
        _FakePage(route="/a", component=_page_a),
        _FakePage(route="/b", component=_page_b),
    ]
    # clean (uncached) compile
    clean = _compile_pages(pages)

    # cached compile of the same pages
    component_cache.reset()
    component_cache.install()
    try:
        cached = _compile_pages(pages)
    finally:
        component_cache.uninstall()

    # the shared static footer recurs across pages -> at least one cache hit
    assert component_cache.STATS["hits"] > 0
    # and the emitted output is byte-identical to the uncached compile
    assert cached == clean


def test_reset_clears_state():
    component_cache.reset()
    component_cache.install()
    try:
        rx.el.div("x")
    finally:
        component_cache.uninstall()
    component_cache.reset()
    assert component_cache.STATS == {"hits": 0, "builds": 0}
    assert component_cache._CACHE == {}
    assert component_cache._SIG_BY_ID == {}
