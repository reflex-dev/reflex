"""Tests for building state deltas."""

import asyncio
from typing import Any

import pytest

import reflex as rx
from reflex.istate.delta import (
    _DROP_FROM_DELTA,
    _commit_delta_records,
    _defer_delta_recording,
    _deferred_delta_records,
    _resolve_delta,
    _suppress_delta_recording,
)
from reflex.state import BaseState


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


@pytest.mark.parametrize("exception", [RuntimeError, asyncio.CancelledError])
def test_deferred_records_reset_after_failure(exception: type[BaseException]):
    """A failed or cancelled merged delta cannot leak its delivery collector.

    Args:
        exception: The failure that interrupts the deferred scope.
    """
    with _defer_delta_recording() as outer:
        with pytest.raises(exception), _defer_delta_recording() as inner:
            assert _deferred_delta_records.get() is inner
            raise exception
        assert _deferred_delta_records.get() is outer
    assert _deferred_delta_records.get() is None


async def test_deferred_records_respect_suppression():
    """Suppressed traversals stay unrecorded inside a deferred delivery scope."""

    class RecordingState(BaseState):
        @rx.var(cache=False)
        def value(self) -> str:
            """Return an uncached value.

            Returns:
                The test value.
            """
            return "value"

    state = RecordingState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    attr = RecordingState.computed_vars["value"]._last_delta_key_attr
    with _defer_delta_recording() as pending:
        with _suppress_delta_recording():
            await state._get_resolved_delta()
        assert not pending
        delta = await state._get_resolved_delta()
        assert pending
        assert not hasattr(state, attr)
        _commit_delta_records(pending, delta)
        assert hasattr(state, attr)
