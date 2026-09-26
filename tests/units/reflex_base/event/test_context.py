"""Tests for EventContext."""

import asyncio
import contextlib
import dataclasses
from collections.abc import AsyncIterator, Sequence
from typing import Any, TypeVar, cast
from unittest import mock

import pytest
from reflex_base.event.context import EventContext

from reflex.istate.manager import StateLease, StateManager
from reflex.istate.manager.token import BaseStateToken, StateToken
from reflex.state import BaseState

TOKEN = "ctx-token"
STATE = TypeVar("STATE", bound=BaseState)


class CtxRoot(BaseState):
    """The root of the state tree checked out in these tests."""

    value: int = 0


class CtxChild(CtxRoot):
    """A substate of CtxRoot."""

    child_value: int = 0


class CtxSibling(CtxRoot):
    """Another substate of CtxRoot."""

    sibling_value: int = 0


@dataclasses.dataclass
class PickleStateManager(StateManager):
    """A state manager storing pickles, so every load returns new instances."""

    stored: dict[str, bytes] = dataclasses.field(default_factory=dict)
    loads: list[list[str]] = dataclasses.field(default_factory=list)
    locks: dict[str, asyncio.Lock] = dataclasses.field(default_factory=dict)
    # When set, the next load waits for it after reading the stored data.
    gate: asyncio.Event | None = None

    async def load_states(
        self, tokens: Sequence[StateToken], *, create: bool = True
    ) -> list[Any]:
        """Load new instances of the stored states.

        Args:
            tokens: The tokens of the states to load.
            create: Whether to create the states that are not stored.

        Returns:
            The state for each token.
        """
        self.loads.append([str(token) for token in tokens])
        stored = [self.stored.get(str(token)) for token in tokens]
        if (gate := self.gate) is not None:
            self.gate = None
            await gate.wait()
        return [
            token.deserialize(data=data)
            if data is not None
            else token.new_instance()
            if create
            else None
            for token, data in zip(tokens, stored, strict=True)
        ]

    async def store_states(
        self,
        states: Sequence[tuple[StateToken, Any]],
        lease: StateLease | None,
        **context,
    ) -> None:
        """Store pickles of the touched states.

        Args:
            states: The tokens and states to store.
            lease: The lease of the held lock.
            context: The state modification context.
        """
        for token, state in states:
            if token.get_and_reset_touched_state(state):
                self.stored[str(token)] = token.serialize(state)

    @contextlib.asynccontextmanager
    async def lock(self, token: StateToken, **context) -> AsyncIterator[StateLease]:
        """Hold the lock on the token's ident.

        Args:
            token: The token to lock.
            context: The state modification context.

        Yields:
            The lease.
        """
        async with self.locks.setdefault(token.ident, asyncio.Lock()):
            yield StateLease(ident=token.ident)


@pytest.fixture
def manager() -> PickleStateManager:
    """A state manager returning new instances on every load.

    Returns:
        The state manager.
    """
    return PickleStateManager()


def _context(manager: StateManager) -> EventContext:
    """Create an event context checking out states from a manager.

    Args:
        manager: The state manager.

    Returns:
        The event context.
    """
    return EventContext(
        token=TOKEN, state_manager=manager, enqueue_impl=mock.AsyncMock()
    )


def _token(cls: type[STATE]) -> StateToken[STATE]:
    """Get the token of a state class for TOKEN.

    Args:
        cls: The state class.

    Returns:
        The token.
    """
    return cast("StateToken[STATE]", BaseStateToken(ident=TOKEN, cls=cls))


def test_fork_creates_child(mock_root_event_context: EventContext):
    """fork() creates a child context with a new txid and shared impls.

    Args:
        mock_root_event_context: The root event context fixture.
    """
    child = mock_root_event_context.fork(token="child-tok")
    assert child.token == "child-tok"
    assert child.parent_txid == mock_root_event_context.txid
    assert child.txid != mock_root_event_context.txid
    assert child.state_manager is mock_root_event_context.state_manager
    assert child.enqueue_impl is mock_root_event_context.enqueue_impl


def test_fork_inherits_token(mock_root_event_context: EventContext):
    """fork() without token= inherits the parent's token.

    Args:
        mock_root_event_context: The root event context fixture.
    """
    child = mock_root_event_context.fork()
    assert child.token == mock_root_event_context.token


async def test_emit_delta(mock_root_event_context: EventContext, emitted_deltas: list):
    """emit_delta records the delta via emit_delta_impl.

    Args:
        mock_root_event_context: The root event context fixture.
        emitted_deltas: List to capture emitted deltas.
    """
    ctx = mock_root_event_context.fork(token="tok")
    delta = {"state": {"x": 1}}
    await ctx.emit_delta(delta)
    assert emitted_deltas == [("tok", delta)]


async def test_emit_event(mock_root_event_context: EventContext, emitted_events: list):
    """emit_event records the event via emit_event_impl.

    Args:
        mock_root_event_context: The root event context fixture.
        emitted_events: List to capture emitted events.
    """
    from reflex.event import Event

    ctx = mock_root_event_context.fork(token="tok")
    ev = Event(name="test", payload={})
    await ctx.emit_event(ev)
    assert len(emitted_events) == 1
    assert emitted_events[0][0] == "tok"


async def test_emit_delta_noop_when_no_impl():
    """emit_delta is a no-op when emit_delta_impl is None."""
    from reflex.istate.manager.memory import StateManagerMemory

    ctx = EventContext(
        token="t",
        state_manager=StateManagerMemory(),
        enqueue_impl=mock.AsyncMock(),
        emit_delta_impl=None,
    )
    await ctx.emit_delta({"s": {"k": "v"}})


async def test_emit_event_noop_when_no_impl():
    """emit_event is a no-op when emit_event_impl is None."""
    from reflex.istate.manager.memory import StateManagerMemory

    ctx = EventContext(
        token="t",
        state_manager=StateManagerMemory(),
        enqueue_impl=mock.AsyncMock(),
        emit_event_impl=None,
    )
    await ctx.emit_event()


async def test_get_state_checks_out_one_tree(manager: PickleStateManager):
    """States loaded separately are linked into one tree of single instances.

    Args:
        manager: The state manager.
    """
    ctx = _context(manager)
    child = await ctx.get_state(_token(CtxChild))
    sibling = await ctx.get_state(_token(CtxSibling))
    root = await ctx.get_state(_token(CtxRoot))

    assert child.parent_state is root
    assert sibling.parent_state is root
    assert root.substates == {
        CtxChild.get_name(): child,
        CtxSibling.get_name(): sibling,
    }
    assert await ctx.get_state(_token(CtxChild)) is child
    async with ctx.modify_state(_token(CtxSibling)) as modified:
        assert modified is sibling
    assert ctx.state_token(root) == _token(CtxRoot)
    assert ctx.state_token(object()) is None
    # Each state was loaded once, the root before its substate.
    assert manager.loads[:2] == [
        [str(_token(CtxRoot)), str(_token(CtxChild))],
        [str(_token(CtxSibling))],
    ]


async def test_modify_state_refreshes_checked_out_states_in_place(
    manager: PickleStateManager,
):
    """Acquiring the lock brings the checked out instances up to date.

    Args:
        manager: The state manager.
    """
    reader = _context(manager)
    child = await reader.get_state(_token(CtxChild))

    async with _context(manager).modify_state(_token(CtxChild)) as written:
        assert written is not child
        written.child_value = 1
        root = written.parent_state
        assert isinstance(root, CtxRoot)
        root.value = 2

    # Reading without the lock keeps what was checked out.
    assert child.child_value == 0
    async with reader.modify_state(_token(CtxChild)) as modified:
        assert modified is child
        assert child.child_value == 1
        root = await reader.get_state(_token(CtxRoot))
        assert child.parent_state is root
        assert root.value == 2


async def test_modify_state_stores_touched_states(manager: PickleStateManager):
    """Only the states modified under the lock are stored.

    Args:
        manager: The state manager.
    """
    ctx = _context(manager)
    async with ctx.modify_state(_token(CtxChild)) as child:
        child.child_value = 3
    assert set(manager.stored) == {str(_token(CtxChild))}


async def test_modify_state_is_reentrant_for_the_holding_task(
    manager: PickleStateManager,
):
    """The task holding the lock may re-enter it, other tasks wait for it.

    Args:
        manager: The state manager.
    """
    ctx = _context(manager)
    order = []

    async def other_task():
        async with ctx.modify_state(_token(CtxChild)) as child:
            order.append(("other", child.child_value))

    async with ctx.modify_state(_token(CtxChild)) as outer:
        async with ctx.modify_state(_token(CtxChild)) as inner:
            assert inner is outer
            inner.child_value = 4
        # The states are stored when leaving the outermost block.
        assert not manager.stored
        task = asyncio.create_task(other_task())
        for _ in range(5):
            await asyncio.sleep(0)
        assert not order
        order.append(("outer", outer.child_value))
    assert manager.stored
    await task
    assert order == [("outer", 4), ("other", 4)]


async def test_flat_token_is_cached_apart_from_the_tree(
    manager: PickleStateManager,
):
    """A flat token sharing the ident of a tree is its own state.

    Args:
        manager: The state manager.
    """
    ctx = _context(manager)
    flat_token = StateToken(ident=TOKEN, cls=dict)
    flat = await ctx.get_state(flat_token)
    root = await ctx.get_state(_token(CtxRoot))

    assert flat == {}
    assert flat is not root
    async with ctx.modify_state(flat_token) as modified:
        assert modified is flat
        modified["key"] = "value"
    assert await ctx.get_state(flat_token) is flat
    assert StateToken.deserialize(manager.stored[str(flat_token)]) == {"key": "value"}


async def test_load_racing_the_lock_is_redone(manager: PickleStateManager):
    """A load started before the lock was acquired is not checked out under it.

    Args:
        manager: The state manager.
    """
    ctx = _context(manager)
    manager.gate = gate = asyncio.Event()
    loading = asyncio.create_task(ctx.get_state(_token(CtxChild)))
    for _ in range(5):
        await asyncio.sleep(0)

    # Another context changes the state while the load is in flight.
    async with _context(manager).modify_state(_token(CtxChild)) as written:
        written.child_value = 7

    async with ctx.modify_state(_token(CtxSibling)):
        gate.set()
        child = await loading
        assert child.child_value == 7
