"""Tests for building state deltas."""

from typing import Any

import pytest
from reflex_base.constants.state import FIELD_MARKER

import reflex as rx
from reflex.istate.delta import _DROP_FROM_DELTA, _resolve_delta
from reflex.istate.proxy import MutableProxy
from reflex.state import BaseState


class DeltaState(BaseState):
    """A state with a plain, a mutable and a computed var."""

    count: int = 0
    items: list[int] = []

    @rx.var
    def doubled(self) -> int:
        """Double the count.

        Returns:
            Twice the count.
        """
        return self.count * 2


class DeltaSubstate(DeltaState):
    """A substate inheriting the vars of DeltaState."""


async def _coro(value: Any) -> Any:  # noqa: RUF029 - a trivial coroutine value for the delta
    return value


async def test_resolve_delta_awaits_coroutines_and_keeps_plain_values():
    """_resolve_delta awaits coroutine values and leaves plain values untouched."""
    delta = {"s1": {"a": _coro(1), "b": 2}}
    resolved = await _resolve_delta(delta)
    assert resolved == {"s1": {"a": 1, "b": 2}}


async def test_resolve_delta_drops_keys_resolving_to_sentinel():
    """A coroutine resolving to _DROP_FROM_DELTA removes its key from the delta."""
    delta = {"s1": {"gone": _coro(_DROP_FROM_DELTA), "stay": _coro("kept"), "plain": 3}}
    resolved = await _resolve_delta(delta)
    assert resolved == {"s1": {"stay": "kept", "plain": 3}}


async def test_resolve_delta_pops_subdict_emptied_by_drops():
    """A state subdict left empty after dropping all its keys is removed entirely."""
    delta = {"s1": {"only": _coro(_DROP_FROM_DELTA)}, "s2": {"keep": 1}}
    resolved = await _resolve_delta(delta)
    assert resolved == {"s2": {"keep": 1}}


async def test_resolve_delta_pops_subdict_when_all_keys_drop():
    """A subdict is removed when multiple coroutines all resolve to _DROP_FROM_DELTA."""
    delta = {
        "s1": {"a": _coro(_DROP_FROM_DELTA), "b": _coro(_DROP_FROM_DELTA)},
        "s2": {"keep": 1},
    }
    resolved = await _resolve_delta(delta)
    assert resolved == {"s2": {"keep": 1}}


def test_build_delta_reads_stored_fields_from_instance_dict(
    monkeypatch: pytest.MonkeyPatch,
):
    """Stored fields skip get_value, computed vars still go through it."""
    state = DeltaState()
    state.count = 2
    state.items.append(1)
    get_value = DeltaState.get_value
    read = []

    def spy(self: DeltaState, key: str) -> Any:
        read.append(key)
        return get_value(self, key)

    monkeypatch.setattr(DeltaState, "get_value", spy)
    delta = state.get_delta()[DeltaState.get_full_name()]

    assert read == ["doubled"]
    assert delta == {
        "count" + FIELD_MARKER: 2,
        "items" + FIELD_MARKER: [1],
        "doubled" + FIELD_MARKER: 4,
    }
    items = delta["items" + FIELD_MARKER]
    assert not isinstance(items, MutableProxy)
    assert items is get_value(state, "items")


def test_build_delta_stores_default_of_unread_field():
    """A dirty field never read yet gets its default stored and sent."""
    state = DeltaState()
    state.dirty_vars.add("items")
    assert "items" not in state.__dict__

    delta = state.get_delta()[DeltaState.get_full_name()]

    assert delta == {"items" + FIELD_MARKER: []}
    assert delta["items" + FIELD_MARKER] is state.__dict__["items"]


def test_build_delta_sends_inherited_var_under_its_owner():
    """An inherited var set through a substate is sent with the state owning it."""
    state = DeltaState()
    substate = state.substates[DeltaSubstate.get_name()]
    substate.count = 3
    assert "count" not in substate.__dict__

    assert state.get_delta() == {
        DeltaState.get_full_name(): {
            "count" + FIELD_MARKER: 3,
            "doubled" + FIELD_MARKER: 6,
        }
    }
