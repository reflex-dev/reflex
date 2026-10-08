"""Tests for the Socket.IO event transport in reflex/socketio_namespace.py."""

import asyncio
import logging
from unittest.mock import AsyncMock, Mock

import pytest
from reflex_base import constants, otel

from reflex.socketio_namespace import EventNamespace

from .conftest import metric_points


@pytest.fixture
def mock_app() -> Mock:
    """A mock app for the event namespace.

    Returns:
        The mock app.
    """
    app = Mock()
    app._state = None
    app._channels = {}
    app.router = Mock(return_value=None)
    app.event_processor.enqueue = AsyncMock()
    return app


@pytest.fixture
def namespace(mock_app: Mock, mocker) -> EventNamespace:
    """A Socket.IO event namespace with a mock app and a local token manager.

    Redis is disabled so token linking cannot leak into a shared Redis.

    Returns:
        The namespace.
    """
    mocker.patch("reflex.utils.prerequisites.check_redis_used", return_value=False)
    return EventNamespace("/_event", mock_app)


@pytest.mark.asyncio
async def test_connect_with_token_is_accepted(namespace: EventNamespace):
    """A client that authenticates keeps its connection and its ASGI scope."""
    scope = {"type": "websocket", "headers": []}
    accepted = await namespace.on_connect(
        "sid1", {"QUERY_STRING": "token=tok1", "asgi.scope": scope}
    )

    assert accepted is not False
    assert namespace.sid_to_token["sid1"] == "tok1"
    assert namespace._scopes["sid1"] is scope


@pytest.mark.asyncio
async def test_connect_without_token_is_refused(namespace: EventNamespace):
    """A connection that never links a token is closed, not left open.

    Nothing it sends can be served, and Socket.IO does not run the disconnect
    handler for a refused connect, so the namespace has to undo its own
    bookkeeping here.
    """
    refused = await namespace.on_connect(
        "sid1", {"QUERY_STRING": "", "asgi.scope": {"type": "websocket"}}
    )

    assert refused is False
    assert "sid1" not in namespace.sid_to_token
    assert namespace._scopes == {}


@pytest.mark.asyncio
async def test_refused_connect_is_not_counted_as_a_connection(
    namespace: EventNamespace, otel_metrics
):
    """A refused connection leaves the gauge where it was, not one above it."""
    await namespace.on_connect("sid1", {"QUERY_STRING": ""})

    (connections,) = metric_points(otel_metrics, otel.METRIC_WEBSOCKET_CONNECTIONS)
    assert connections.value == 0


@pytest.mark.asyncio
async def test_connect_processes_boot_event_from_auth(
    namespace: EventNamespace, mock_app: Mock
):
    """The hydrate event carried in the CONNECT packet is processed on connect.

    As the connection's first event it records the new sid and token on the
    state, so the connect does not load and save the state tree for that; a
    connect without a boot event still does.
    """
    mock_app._state = Mock()
    state = Mock(router_data={})
    modify_state = mock_app.state_manager.modify_state = Mock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=state))
    )
    boot_event = {"name": "state.hydrate_and_load", "payload": {}, "router_data": {}}
    environ = {
        "QUERY_STRING": "token=tok1",
        "asgi.scope": {"type": "websocket", "headers": []},
    }

    await namespace.on_connect("sid1", environ, {"event": boot_event})

    token, event = mock_app.event_processor.enqueue.await_args.args
    assert (token, event.name) == ("tok1", "state.hydrate_and_load")
    modify_state.assert_not_called()

    # Without a boot event (or without auth at all) nothing is processed, and
    # the connect records the new sid and token on the state itself.
    mock_app.event_processor.enqueue.reset_mock()
    await namespace.on_connect("sid2", {"QUERY_STRING": "token=tok2"}, None)
    await namespace.on_connect("sid3", {"QUERY_STRING": "token=tok3"})
    mock_app.event_processor.enqueue.assert_not_awaited()
    assert modify_state.call_count == 2
    assert state.router_data[constants.RouteVar.SESSION_ID] == "sid3"
    assert state.router_data[constants.RouteVar.CLIENT_TOKEN] == "tok3"


@pytest.mark.asyncio
async def test_connect_whose_boot_event_fails_is_refused(
    namespace: EventNamespace, mock_app: Mock, otel_metrics, caplog
):
    """A boot event that fails to process refuses the connect and undoes it.

    Raising instead would leave the session registered with Socket.IO yet
    unanswered, so the client would neither hydrate nor retry.
    """
    mock_app.event_processor.enqueue.side_effect = ValueError("bad boot event")
    boot_event = {"name": "state.hydrate_and_load", "payload": {}, "router_data": {}}
    environ = {
        "QUERY_STRING": "token=tok1",
        "asgi.scope": {"type": "websocket", "headers": []},
    }

    with caplog.at_level(logging.ERROR, logger="reflex.event_namespace"):
        refused = await namespace.on_connect("sid1", environ, {"event": boot_event})
    # Let the token cleanup task run.
    await asyncio.sleep(0)

    assert refused is False
    assert "Error handling the boot event" in caplog.text
    assert "sid1" not in namespace.sid_to_token
    assert "tok1" not in namespace.token_to_sid
    assert namespace._scopes == {}
    (connections,) = metric_points(otel_metrics, otel.METRIC_WEBSOCKET_CONNECTIONS)
    assert connections.value == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data", ['{"name": "state.on_click", "payload": {}, "router_data": {}}', 42]
)
async def test_undeserializable_event_disconnects_the_session(
    namespace: EventNamespace, mock_app: Mock, caplog, data: object
):
    """A malformed event ends the session, as on the plain transport.

    Escaping into python-socketio, the error logged a traceback per frame,
    outside any error budget, and the session stayed open.
    """
    await namespace.on_connect(
        "sid1", {"QUERY_STRING": "token=tok1", "asgi.scope": {"headers": []}}
    )
    namespace.disconnect = AsyncMock()

    with caplog.at_level(logging.DEBUG, logger="reflex.event_namespace"):
        await namespace.on_event("sid1", data)

    namespace.disconnect.assert_awaited_once_with("sid1")
    mock_app.event_processor.enqueue.assert_not_awaited()
    assert all(record.levelno <= logging.DEBUG for record in caplog.records)
