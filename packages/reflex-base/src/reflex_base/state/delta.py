"""Build the deltas of state changes sent to the client."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import time
from collections.abc import Coroutine, Iterator, Mapping
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Final, NamedTuple

from reflex_base.constants.state import FIELD_MARKER

if TYPE_CHECKING:
    from reflex_base.state.node import StateNode
    from reflex_base.vars.base import ComputedVar

Delta = dict[str, dict[str, Any]]
DeltaMapping = Mapping[str, Mapping[str, Any]]


# Sentinel a delta-value coroutine may resolve to in order to suppress its key:
# when ``_resolve_delta`` awaits a coroutine value and gets this object back, it
# drops the key from the delta instead of writing it. Lets a value whose
# inclusion can only be decided asynchronously be deferred into the delta as a
# coroutine and then omitted post-hoc. Compared by identity (the object itself is
# the contract); never serialized into a delta sent to the client.
_DROP_FROM_DELTA: Final = object()

# Whether the delta currently being built reaches the client at all. Carried out
# of band rather than as an argument so that every internal call stays
# ``get_delta()``/``_get_resolved_delta()``: downstream packages patch those
# methods with signatures taking no arguments, and the flag describes the whole
# traversal rather than any single state in it. A ContextVar, not a global:
# deltas for different clients are built in concurrent tasks, and leaking a
# discarded traversal's flag into one of those would suppress a real update.
_record_delta_values: ContextVar[bool] = ContextVar(
    "_record_delta_values", default=True
)


class _DeltaRecord(NamedTuple):
    """An uncached var value that counts as sent once the delta delivers it."""

    state_name: str
    key: str
    value: Any
    instance: StateNode
    attr: str
    stored: tuple[str, Any] | None


# Records gathered while a delta is built, for the caller that delivers it; None
# when nobody is collecting, in which case the values computed never count as
# sent. Recording has to wait for the delta to come back out of ``get_delta``:
# a downstream override may drop an entry or replace it with a placeholder, and
# a value the client never received has to be sent again later.
_pending_delta_records: ContextVar[list[_DeltaRecord] | None] = ContextVar(
    "_pending_delta_records", default=None
)


@contextlib.contextmanager
def _suppress_delta_recording() -> Iterator[None]:
    """Stop delta values built in this block from counting as sent to the client.

    For a delta that is computed for its side effects and then discarded, whose
    values the client never receives. Clears the collector as well, so that a
    block nested inside a traversal that is recording still records nothing.

    Yields:
        None, with recording suppressed.
    """
    token = _record_delta_values.set(False)
    records_token = _pending_delta_records.set(None)
    try:
        yield
    finally:
        _pending_delta_records.reset(records_token)
        _record_delta_values.reset(token)


def _commit_delta_records(pending: list[_DeltaRecord], delta: Delta) -> None:
    """Record what a delivered delta leaves the client holding for each value.

    A value counts as sent only where the delta still holds the very object that
    was computed for it. A ``get_delta`` override may instead have dropped the
    key, leaving the client on the value the existing record already describes,
    or replaced it with a placeholder, which makes that record wrong: the client
    now holds something this side never computed, so the record is discarded and
    the next value is sent whatever it turns out to be.

    Args:
        pending: The records gathered while the delta was built.
        delta: The delta as it comes back out of ``get_delta``, resolved.
    """
    for state_name, key, value, instance, attr, stored in pending:
        subdelta = delta.get(state_name)
        if subdelta is None or key not in subdelta:
            # Withheld entirely: the client keeps what it already had.
            continue
        if stored is None or subdelta[key] is not value:
            # A value that can never be compared, or a placeholder delivered in
            # its place: forget what the client has, so the next value is sent
            # whatever it is.
            try:
                delattr(instance, attr)
            except AttributeError:
                # Nothing was recorded, so there is nothing to serialize.
                continue
        else:
            setattr(instance, attr, stored)
        # Ensure the recorded value gets serialized to redis.
        instance._was_touched = True


async def _resolve_delta(delta: Delta) -> Delta:
    """Await all coroutines in the delta, dropping keys that resolve to the drop sentinel.

    Args:
        delta: The delta to process.

    Returns:
        The same delta dict with all coroutines resolved to their return value,
        and any key whose coroutine resolved to ``_DROP_FROM_DELTA`` removed
        (along with any state subdict left empty by such removals).
    """
    tasks = {}
    for state_name, state_delta in delta.items():
        for var_name, value in state_delta.items():
            if inspect.iscoroutine(value):
                tasks[state_name, var_name] = asyncio.create_task(
                    value,
                    name=f"reflex_resolve_delta|{state_name}|{var_name}|{time.time()}",
                )
    for (state_name, var_name), task in tasks.items():
        resolved = await task
        if resolved is _DROP_FROM_DELTA:
            del delta[state_name][var_name]
            if not delta[state_name]:
                del delta[state_name]
        else:
            delta[state_name][var_name] = resolved
    return delta


def _record_or_drop_delta_value(
    cvar: ComputedVar,
    instance: StateNode,
    value: Any,
    token: str,
    state_name: str,
    key: str,
    pending: list[_DeltaRecord],
) -> Any:
    """Keep an uncached computed var value in the delta unless the client has it.

    Args:
        cvar: The computed var that produced the value.
        instance: The state instance the computed var is attached to.
        value: The computed value, already resolved.
        token: The client token the delta is being produced for.
        state_name: The full name of the state the value belongs to.
        key: The delta key the value is stored under.
        pending: The records to append to once the value is kept.

    Returns:
        The value, or ``_DROP_FROM_DELTA`` when it matches the last value that
        was recorded as sent to the client.
    """
    record = cvar._pending_delta_record(instance, value, token)
    if record is None:
        return _DROP_FROM_DELTA
    pending.append(_DeltaRecord(state_name, key, value, instance, *record))
    return value


async def _drop_unchanged_delta_value(
    cvar: ComputedVar,
    instance: StateNode,
    value: Coroutine[None, None, Any],
    token: str,
    state_name: str,
    key: str,
    pending: list[_DeltaRecord],
) -> Any:
    """Await an async uncached computed var, dropping it if the value did not change.

    Args:
        cvar: The computed var that produced the coroutine.
        instance: The state instance the computed var is attached to.
        value: The coroutine returned by the computed var.
        token: The client token the delta is being produced for.
        state_name: The full name of the state the value belongs to.
        key: The delta key the resolved value is stored under.
        pending: The records to append to once the value is kept.

    Returns:
        The resolved value, or ``_DROP_FROM_DELTA`` when it matches the last
        value that was sent to the client.
    """
    return _record_or_drop_delta_value(
        cvar, instance, await value, token, state_name, key, pending
    )


def build_delta(state: StateNode) -> Delta:
    """Get the delta for a state and its dirty substates.

    Recurses through each substate's ``get_delta`` method, so an override of it
    applies. The uncached computed var values it computes only count as sent to
    the client once ``resolve_delta`` finds them in the delta that comes back
    out of such an override.

    Args:
        state: The state.

    Returns:
        The delta.
    """
    delta = {}

    state._mark_dirty_computed_vars()
    delta_vars = state.dirty_vars & state._frontend_var_names

    always_dirty_computed_vars = state._always_dirty_computed_vars
    # Where to leave the values this traversal sends, for whoever delivers
    # the delta to record them; None when nothing is collecting them.
    pending = _pending_delta_records.get() if always_dirty_computed_vars else None
    # Token of the client this delta is for, used to know which values it has.
    token = state._client_token() if pending is not None else ""
    full_name = state.get_full_name()
    subdelta: dict[str, Any] = {}
    for prop in delta_vars:
        value = state.get_value(prop)
        key = prop + FIELD_MARKER
        if pending is not None and prop in always_dirty_computed_vars:
            # Uncached computed vars are recomputed for every delta; only
            # send them when the recomputed value actually changed. Nothing
            # is left out of a delta nobody collects: what the client has is
            # only known for the values a delivered delta recorded.
            cvar = state.computed_vars[prop]
            if inspect.iscoroutine(value):
                value = _drop_unchanged_delta_value(
                    cvar, state, value, token, full_name, key, pending
                )
                # An async value cannot be compared to what the client has
                # until it is awaited, and a filter that withholds it closes
                # the coroutine before that. Stake the key on the wrapper
                # now, so that a placeholder delivered in its place still
                # invalidates the record; the real one, appended while the
                # delta resolves, comes after this and wins.
                pending.append(
                    _DeltaRecord(
                        full_name, key, value, state, cvar._last_delta_key_attr, None
                    )
                )
            else:
                value = _record_or_drop_delta_value(
                    cvar, state, value, token, full_name, key, pending
                )
                if value is _DROP_FROM_DELTA:
                    continue
        subdelta[key] = value

    if subdelta:
        delta[full_name] = subdelta

    substates = state.substates
    for substate in state.dirty_substates.union(state._always_dirty_substates):
        delta.update(substates[substate].get_delta())
    return delta


async def resolve_delta(state: StateNode) -> Delta:
    """Get the delta to deliver to the client, with all coroutines resolved.

    What this returns is what the caller delivers to the client -- past any
    ``get_delta`` override -- so it is here that the uncached computed var
    values it carries count as sent.

    Args:
        state: The root of the states to get the delta for.

    Returns:
        The resolved delta.
    """
    # No collector at all when this delta is not delivered, so that nothing
    # it carries counts as sent, at any depth of the traversal.
    pending: list[_DeltaRecord] | None = [] if _record_delta_values.get() else None
    records_token = _pending_delta_records.set(pending)
    try:
        delta = await _resolve_delta(state.get_delta())
    finally:
        _pending_delta_records.reset(records_token)
    if pending:
        _commit_delta_records(pending, delta)
    return delta


def clean_state(state: StateNode) -> None:
    """Reset the dirty vars of a state and, through their ``_clean``, its dirty substates.

    Args:
        state: The state.
    """
    substates = state.substates
    for substate in state.dirty_substates:
        if substate in substates:
            substates[substate]._clean()
    state.dirty_vars = set()
    state.dirty_substates = set()
