"""Tests for the compile-time wiring of client state scopes."""

from reflex_base.components.client_state_context import (
    ClientStateScope,
    local_client_state_names,
    scope_page,
)

import reflex as rx


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


def test_scope_page_wraps_a_page_using_local_state() -> None:
    """The page owns the local names its body uses."""
    local = rx.client_state(0)
    page = rx.box(rx.text(local.value))

    scoped = scope_page(page)

    assert isinstance(scoped, ClientStateScope)
    assert scoped.children == [page]
    assert str(scoped.owns) == f'["{local._state_name}"]'


def test_scope_page_leaves_other_pages_unchanged() -> None:
    """A page with only global or no client state needs no scope."""
    named = rx.client_state(0, name="page_global")
    page = rx.box(rx.text(named.value))

    assert scope_page(page) is page


def test_scope_page_ignores_names_used_only_inside_a_memo() -> None:
    """A memo body's names belong to each memo instance, not to the page."""

    @rx.memo
    def own_counter() -> rx.Component:
        return rx.text(rx.client_state(0).value)

    page = rx.box(own_counter())

    assert scope_page(page) is page
