"""Tests for EventContext."""

import dataclasses
from unittest import mock

import pytest
from reflex_base.event.context import EventContext
from reflex_base.session import SessionToken, SessionTokenManager
from reflex_base.utils.exceptions import SessionAuthorizationError


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


@pytest.mark.parametrize("operation", ["constructor", "fork", "replace"])
@pytest.mark.parametrize("authorized", [True, False])
def test_context_session_authorization(
    mock_root_event_context: EventContext,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    authorized: bool,
):
    """Every context creation path checks ownership.

    Args:
        mock_root_event_context: The root context fixture.
        monkeypatch: The environment patch fixture.
        operation: The creation path under test.
        authorized: Whether the client token belongs to the session.
    """
    monkeypatch.setenv("REFLEX_SESSION_TOKEN_MODE", "enforce")
    manager = SessionTokenManager("test", secrets=(b"a" * 32,))
    session = manager.create()
    token = manager.create_client_token(session if authorized else manager.create())
    parent = dataclasses.replace(mock_root_event_context, session_token=session)

    def create_context() -> EventContext:
        """Exercise the selected context construction path.

        Returns:
            The constructed context.
        """
        if operation == "fork":
            return parent.fork(token=token)
        if operation == "replace":
            return dataclasses.replace(parent, token=token)
        return EventContext(
            token=token,
            session_token=session,
            state_manager=parent.state_manager,
            enqueue_impl=parent.enqueue_impl,
        )

    if authorized:
        assert create_context().session_token is session
    else:
        with pytest.raises(SessionAuthorizationError):
            create_context()


@pytest.mark.parametrize("mode", ["off", "warn", "enforce"])
def test_missing_session_modes(
    mock_root_event_context: EventContext,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
):
    """Missing sessions warn, pass, or fail according to the rollout mode.

    Args:
        mock_root_event_context: The root context fixture.
        monkeypatch: The environment patch fixture.
        mode: The rollout mode.
    """
    monkeypatch.setenv("REFLEX_SESSION_TOKEN_MODE", mode)
    with mock.patch("reflex_base.event.context.console.deprecate") as warning:
        if mode == "enforce":
            with pytest.raises(SessionAuthorizationError):
                dataclasses.replace(
                    mock_root_event_context, token="legacy", session_token=None
                )
        else:
            dataclasses.replace(
                mock_root_event_context, token="legacy", session_token=None
            )
        assert warning.call_count == (mode == "warn")


def test_system_session_and_explicit_fanout(
    mock_root_event_context: EventContext, monkeypatch: pytest.MonkeyPatch
):
    """Trusted fan-out explicitly overrides the ambient session.

    Args:
        mock_root_event_context: The root context fixture.
        monkeypatch: The environment patch fixture.
    """
    monkeypatch.setenv("REFLEX_SESSION_TOKEN_MODE", "enforce")
    parent = dataclasses.replace(mock_root_event_context, session_token=None)
    child = parent.fork(token="other-client", session_token=SessionToken.SYSTEM)
    assert child.session_token is SessionToken.SYSTEM
    assert child.fork().session_token is SessionToken.SYSTEM
