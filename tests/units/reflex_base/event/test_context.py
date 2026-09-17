"""Tests for EventContext."""

from unittest import mock

from reflex_base.event.context import EventContext


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
