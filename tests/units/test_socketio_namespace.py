"""Tests for the Socket.IO event transport in reflex/socketio_namespace.py."""

from unittest.mock import AsyncMock, Mock

import pytest
from reflex_base import otel

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
