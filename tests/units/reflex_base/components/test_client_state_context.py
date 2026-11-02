"""Tests for the compile-time wiring of client state scopes."""

import dataclasses
from collections.abc import Callable
from typing import Any, cast

from reflex_base.components.client_state_context import (
    ClientStateScope,
    local_client_state_names,
)
from reflex_base.components.component import Component
from reflex_base.plugins import CompileContext, CompilerHooks, PageContext
from reflex_base.vars.sequence import LiteralArrayVar

import reflex as rx
from reflex.compiler.plugins import default_page_plugins


class ScopeState(rx.State):
    """State with a list to loop over."""

    items: list[str] = ["a", "b"]


@dataclasses.dataclass(slots=True)
class _Page:
    route: str
    component: Callable[[], Component]
    title: Any = None
    description: Any = None
    image: str = ""
    meta: tuple[dict[str, Any], ...] = ()
    _source_module: str | None = None


def _compile(component_factory: Callable[[], Component]) -> PageContext:
    """Compile one page with the default plugins.

    Args:
        component_factory: The page function.

    Returns:
        The compiled page context.
    """
    ctx = CompileContext(
        pages=[_Page(route="/p", component=component_factory)],
        hooks=CompilerHooks(plugins=default_page_plugins()),
    )
    with ctx:
        ctx.compile()
    return ctx.compiled_pages["/p"]


def _owned(page_ctx: PageContext) -> list[str] | None:
    """Get the names the compiled page's scope claims, or None without a scope.

    Args:
        page_ctx: The compiled page.

    Returns:
        The owned names, or None.
    """
    root = page_ctx.root_component
    if not isinstance(root, ClientStateScope):
        return None
    owns = cast("LiteralArrayVar", root.owns)
    return sorted(cast("list[str]", owns._var_value))


def test_local_names_come_from_local_hooks_only() -> None:
    """Global and unrelated hooks contribute no names."""
    local = rx.client_state(0)
    named = rx.client_state(0, name="named_global")
    hooks = rx.vstack(
        rx.text(local.value), rx.text(named.value), rx.text(local.value)
    )._get_all_hooks()

    assert local_client_state_names(hooks) == [local._state_name]


def test_local_names_are_sorted_and_unique() -> None:
    """The emitted list is stable across runs."""
    first = rx.client_state(0, prefix="b")
    second = rx.client_state(0, prefix="a")
    hooks = rx.vstack(
        rx.text(first.value), rx.text(second.value), rx.text(first.value)
    )._get_all_hooks()

    assert local_client_state_names(hooks) == sorted([
        first._state_name,
        second._state_name,
    ])


def test_page_owns_a_local_name_used_in_a_memoized_subtree() -> None:
    """A name whose hook moved into an auto-memo module is still the page's.

    ``rx.text(local.value)`` is memoized into its own module, so its hook is
    not among the page hooks; the page scope has to claim the name anyway, or
    a memo instance rendering first would own it.
    """
    local = rx.client_state(0)

    page_ctx = _compile(lambda: rx.box(rx.text(local.value)))

    assert _owned(page_ctx) == [local._state_name]
    assert page_ctx.output_code is not None
    assert (
        f'jsx(ClientStateScope,{{owns:["{local._state_name}"]}}' in page_ctx.output_code
    )
    assert "ClientStateScope" in str(page_ctx.imports)


def test_page_owns_a_local_name_used_inside_a_snapshot_boundary() -> None:
    """A name used inside a sealed subtree is found through the body's hooks."""
    local = rx.client_state(0)

    page_ctx = _compile(
        lambda: rx.box(rx.foreach(ScopeState.items, lambda _item: rx.text(local.value)))
    )

    assert _owned(page_ctx) == [local._state_name]


def test_page_without_local_state_gets_no_scope() -> None:
    """A page with only global or no client state needs no scope."""
    named = rx.client_state(0, name="page_global")

    assert _owned(_compile(lambda: rx.box(rx.text(named.value)))) is None
    assert _owned(_compile(lambda: rx.box(rx.text("static")))) is None


def test_page_does_not_claim_names_used_only_inside_a_memo() -> None:
    """A memo body's names belong to each memo instance, not to the page."""

    @rx.memo
    def own_counter() -> rx.Component:
        return rx.text(rx.client_state(0).value)

    assert _owned(_compile(lambda: rx.box(own_counter()))) is None


def test_page_evaluation_renders_no_hooks() -> None:
    """Deciding the owner costs nothing at evaluation; it happens after the walk."""
    from unittest import mock

    from reflex.compiler.plugins.builtin import DefaultPagePlugin

    local = rx.client_state(0)
    page = _Page(route="/p", component=lambda: rx.box(rx.text(local.value)))
    with mock.patch.object(Component, "_get_all_hooks", autospec=True) as hooks:
        CompilerHooks(plugins=(DefaultPagePlugin(),)).eval_page(
            page.component, page=page
        )
    hooks.assert_not_called()
