"""Tests for building state deltas."""

from typing import Any

from reflex.istate.delta import _DROP_FROM_DELTA, _resolve_delta


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
