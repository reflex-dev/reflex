"""Tests for the plain WebSocket event transport in reflex/event_namespace.py."""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocketDisconnect

from reflex.app import App
from reflex.event_namespace import (
    HANDSHAKE_MESSAGE,
    PONG_MESSAGE,
    WebsocketEventNamespace,
)

_DISCONNECT = object()


class FakeWebSocket:
    """Minimal stand-in for a starlette WebSocket."""

    def __init__(
        self,
        query_string: bytes = b"token=tok1",
        origin: str | None = None,
        subprotocols: list[str] | None = None,
    ):
        """Initialize the fake websocket.

        Args:
            query_string: The raw query string of the connection.
            origin: The Origin header value, if any.
            subprotocols: The offered subprotocols.
        """
        self.scope: dict[str, Any] = {
            "type": "websocket",
            "query_string": query_string,
            "subprotocols": subprotocols or [],
            "headers": [(b"host", b"localhost")],
            "client": ("127.0.0.1", 1234),
        }
        self.headers = {"origin": origin} if origin is not None else {}
        self.sent: list[Any] = []
        self.accepted_subprotocol: str | None = None
        self.accepted = False
        self.close_code: int | None = None
        self._incoming: asyncio.Queue = asyncio.Queue()

    async def accept(self, subprotocol: str | None = None):
        """Record the accept call.

        Args:
            subprotocol: The selected subprotocol.
        """
        self.accepted = True
        self.accepted_subprotocol = subprotocol

    async def send_text(self, text: str):
        """Record an outgoing frame.

        Args:
            text: The frame text.
        """
        self.sent.append(json.loads(text))

    async def close(self, code: int = 1000):
        """Record the close call.

        Args:
            code: The close code.
        """
        self.close_code = code

    async def receive_text(self) -> str:
        """Return the next queued frame.

        Returns:
            The frame text.

        Raises:
            WebSocketDisconnect: When the disconnect sentinel is reached.
        """
        item = await self._incoming.get()
        if item is _DISCONNECT:
            raise WebSocketDisconnect(1000)
        return item

    def feed(self, *frames: Any):
        """Queue incoming frames (lists are JSON-encoded) and a disconnect."""
        for frame in frames:
            self._incoming.put_nowait(
                frame if isinstance(frame, str) else json.dumps(frame)
            )
        self._incoming.put_nowait(_DISCONNECT)


@pytest.fixture
def mock_app() -> Mock:
    """A mock app for the event namespace.

    Returns:
        The mock app.
    """
    app = Mock()
    app._state = None
    app.router = Mock(return_value=None)
    app.event_processor.enqueue = AsyncMock()
    return app


@pytest.fixture
def namespace(mock_app: Mock, mocker) -> WebsocketEventNamespace:
    """A websocket event namespace with a mock app and a local token manager.

    Redis is disabled so token linking stays in-process: these tests must not
    write session records into a shared Redis instance (which would leak into
    other tests) or depend on Redis I/O timing for disconnect cleanup.

    Args:
        mock_app: The mock app.
        mocker: The pytest-mock fixture.

    Returns:
        The namespace.
    """
    mocker.patch("reflex.utils.prerequisites.check_redis_used", return_value=False)
    return WebsocketEventNamespace("/_event", mock_app)


async def _drain_tasks():
    """Let pending disconnect-cleanup tasks run to completion."""
    for _ in range(3):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_handshake_and_token_link(namespace: WebsocketEventNamespace):
    """The server sends the handshake first and links the token from the query.

    Args:
        namespace: The websocket event namespace.
    """
    websocket = FakeWebSocket(subprotocols=["0.0.1"])
    websocket.feed()
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]

    assert websocket.accepted
    assert websocket.accepted_subprotocol == "0.0.1"
    assert websocket.sent[0][0] == HANDSHAKE_MESSAGE
    assert set(websocket.sent[0][1]) == {"ping_interval", "ping_timeout"}
    await _drain_tasks()
    # The session was linked and unlinked again on disconnect.
    assert "tok1" not in namespace.token_to_sid


@pytest.mark.asyncio
async def test_event_is_enqueued(namespace: WebsocketEventNamespace, mock_app: Mock):
    """An incoming event frame reaches the app's event processor.

    Args:
        namespace: The websocket event namespace.
        mock_app: The mock app.
    """
    websocket = FakeWebSocket()
    websocket.feed([
        "event",
        {"token": "tok1", "name": "state.on_click", "payload": {}, "router_data": {}},
    ])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    mock_app.event_processor.enqueue.assert_awaited_once()
    token, event = mock_app.event_processor.enqueue.await_args.args
    assert token == "tok1"
    assert event.name == "state.on_click"
    assert event.router_data["headers"]["host"] == "localhost"
    assert event.router_data["ip"] == "127.0.0.1"


@pytest.mark.asyncio
async def test_ping_pong(namespace: WebsocketEventNamespace):
    """An application-level ping event gets a pong reply.

    Args:
        namespace: The websocket event namespace.
    """
    websocket = FakeWebSocket()
    websocket.feed(["ping"], [PONG_MESSAGE])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert ["ping", "pong"] in websocket.sent


@pytest.mark.asyncio
async def test_client_error_reaches_exception_handler(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """A client_error frame is routed to the frontend exception handler.

    Args:
        namespace: The websocket event namespace.
        mock_app: The mock app.
    """
    errors: list[str] = []
    mock_app.frontend_exception_handler = lambda exc: errors.append(str(exc))
    websocket = FakeWebSocket()
    websocket.feed(["client_error", {"error_type": "boom", "message": "it broke"}])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert len(errors) == 1
    assert "it broke" in errors[0]


@pytest.mark.asyncio
async def test_malformed_frames_are_ignored(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """Malformed frames are skipped without dropping the connection.

    Args:
        namespace: The websocket event namespace.
        mock_app: The mock app.
    """
    websocket = FakeWebSocket()
    websocket.feed(
        "not json",
        '{"an": "object"}',
        [42],
        ["ping"],
    )
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    # The valid ping after the malformed frames was still processed.
    assert ["ping", "pong"] in websocket.sent
    assert websocket.close_code is None


@pytest.mark.asyncio
async def test_oversize_message_closes_connection(
    namespace: WebsocketEventNamespace, monkeypatch: pytest.MonkeyPatch
):
    """A frame over the size limit closes the connection with 1009.

    Args:
        namespace: The websocket event namespace.
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setenv("REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE", "10")
    websocket = FakeWebSocket()
    websocket.feed(["event", {"payload": "x" * 100}])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code == 1009


@pytest.mark.asyncio
async def test_disallowed_origin_is_rejected(
    namespace: WebsocketEventNamespace, mocker
):
    """A cross-origin connection is closed before being accepted.

    Args:
        namespace: The websocket event namespace.
        mocker: The pytest-mock fixture.
    """
    from reflex_base.config import get_config

    mocker.patch.object(
        get_config(), "cors_allowed_origins", ("https://allowed.example",)
    )
    websocket = FakeWebSocket(origin="https://evil.example")
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]

    assert not websocket.accepted
    assert websocket.close_code == 1008


@pytest.mark.asyncio
async def test_allowed_origin_is_accepted(namespace: WebsocketEventNamespace, mocker):
    """A connection from an allowed origin is accepted.

    Args:
        namespace: The websocket event namespace.
        mocker: The pytest-mock fixture.
    """
    from reflex_base.config import get_config

    mocker.patch.object(
        get_config(), "cors_allowed_origins", ("https://allowed.example",)
    )
    websocket = FakeWebSocket(origin="https://allowed.example")
    websocket.feed()
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.accepted


@pytest.mark.asyncio
async def test_duplicate_token_gets_new_token(namespace: WebsocketEventNamespace):
    """A second tab connecting with the same token receives a new_token frame.

    Args:
        namespace: The websocket event namespace.
    """
    first = FakeWebSocket()
    second = FakeWebSocket()
    namespace._sockets["sid1"] = first  # pyright: ignore[reportArgumentType]
    namespace._sockets["sid2"] = second  # pyright: ignore[reportArgumentType]
    await namespace.link_token_to_sid("sid1", "tok1")
    await namespace.link_token_to_sid("sid2", "tok1")

    new_token_frames = [frame for frame in second.sent if frame[0] == "new_token"]
    assert len(new_token_frames) == 1
    assert new_token_frames[0][1] != "tok1"


@pytest.mark.asyncio
async def test_emit_to_unknown_sid_does_not_raise(
    namespace: WebsocketEventNamespace,
):
    """Emitting to a session that went away is a no-op.

    Args:
        namespace: The websocket event namespace.
    """
    await namespace.emit("event", {"delta": {}}, to="gone")


def test_default_transport_uses_websocket_namespace():
    """The default transport sets up the plain websocket namespace."""
    app = App(enable_state=True)
    assert isinstance(app.event_namespace, WebsocketEventNamespace)
    assert app.sio is None
    assert app._api is not None
    websocket_routes = [
        route for route in app._api.router.routes if isinstance(route, WebSocketRoute)
    ]
    assert [route.path for route in websocket_routes] == ["/_event"]


def test_socketio_transport_uses_socketio_namespace(
    monkeypatch: pytest.MonkeyPatch,
):
    """transport="socketio" sets up the Socket.IO server and namespace.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    from reflex.socketio_namespace import EventNamespace

    monkeypatch.setenv("REFLEX_TRANSPORT", "socketio")
    app = App(enable_state=True)
    assert isinstance(app.event_namespace, EventNamespace)
    assert app.sio is not None
    # Plain websocket transport under the hood.
    assert app.sio.eio.transports == ["websocket"]


def test_polling_transport_uses_socketio_namespace(
    monkeypatch: pytest.MonkeyPatch,
):
    """transport="polling" sets up the Socket.IO server with polling only.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    from reflex.socketio_namespace import EventNamespace

    monkeypatch.setenv("REFLEX_TRANSPORT", "polling")
    app = App(enable_state=True)
    assert isinstance(app.event_namespace, EventNamespace)
    assert app.sio is not None
    assert app.sio.eio.transports == ["polling"]


def test_custom_sio_requires_socketio_transport():
    """A custom sio server with the default transport raises a clear error."""
    from socketio import AsyncServer

    with pytest.raises(RuntimeError, match=r"requires the Socket\.IO transport"):
        App(sio=AsyncServer(async_mode="asgi"))


def test_custom_sio_with_socketio_transport(monkeypatch: pytest.MonkeyPatch):
    """A custom sio server works with the Socket.IO transport.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    from socketio import AsyncServer

    monkeypatch.setenv("REFLEX_TRANSPORT", "socketio")
    sio = AsyncServer(async_mode="asgi")
    app = App(sio=sio)
    assert app.sio is sio


def test_app_event_namespace_reexport():
    """reflex.app.EventNamespace still resolves to the Socket.IO namespace."""
    import reflex.app
    from reflex.socketio_namespace import EventNamespace

    assert reflex.app.EventNamespace is EventNamespace
    with pytest.raises(AttributeError):
        _ = reflex.app.DoesNotExist
