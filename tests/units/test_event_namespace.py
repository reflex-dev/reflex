"""Tests for the plain WebSocket event transport in reflex/event_namespace.py."""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.routing import WebSocketRoute

from reflex.app import App
from reflex.event_namespace import (
    HANDSHAKE_MESSAGE,
    PING_MESSAGE,
    PONG_MESSAGE,
    WebsocketEventNamespace,
)

_DISCONNECT = object()

WEBSOCKET_JS_TEMPLATE = (
    Path(__file__).parents[2]
    / "packages/reflex-base/src/reflex_base/.templates/web/utils/helpers/websocket.js"
)


class FakeWebSocket:
    """Minimal stand-in for a starlette WebSocket."""

    def __init__(
        self,
        query_string: bytes = b"token=tok1",
        origin: str | None = None,
        subprotocols: list[str] | None = None,
    ):
        """Initialize the fake websocket."""
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
        """Record the accept call."""
        self.accepted = True
        self.accepted_subprotocol = subprotocol

    async def send_text(self, text: str):
        """Record an outgoing frame."""
        self.sent.append(json.loads(text))

    async def close(self, code: int = 1000):
        """Record the close call."""
        self.close_code = code

    async def receive(self) -> dict[str, Any]:
        """Return the next queued frame as an ASGI message.

        Returns:
            The ASGI websocket message.
        """
        item = await self._incoming.get()
        if item is _DISCONNECT:
            return {"type": "websocket.disconnect", "code": 1000}
        if isinstance(item, bytes):
            return {"type": "websocket.receive", "bytes": item}
        return {"type": "websocket.receive", "text": item}

    def feed(self, *frames: Any):
        """Queue incoming frames (lists are JSON-encoded) and a disconnect."""
        for frame in frames:
            self._incoming.put_nowait(
                frame if isinstance(frame, (str, bytes)) else json.dumps(frame)
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

    Redis is disabled so token linking cannot leak into a shared Redis.

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
    """The server sends the handshake first and links the token from the query."""
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
    """An incoming event frame reaches the app's event processor."""
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
    """An application-level ping event gets a pong reply."""
    websocket = FakeWebSocket()
    websocket.feed(["ping"], [PONG_MESSAGE])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert ["ping", "pong"] in websocket.sent


@pytest.mark.asyncio
async def test_client_error_reaches_exception_handler(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """A client_error frame is routed to the frontend exception handler."""
    errors: list[str] = []
    mock_app.frontend_exception_handler = lambda exc: errors.append(str(exc))
    websocket = FakeWebSocket()
    websocket.feed(["client_error", {"error_type": "boom", "message": "it broke"}])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert len(errors) == 1
    assert "it broke" in errors[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("frame", ["not json", '{"an": "object"}', "[42]"])
async def test_malformed_frame_closes_connection(
    namespace: WebsocketEventNamespace, frame: str
):
    """A malformed frame closes the connection with 1002 (protocol error)."""
    websocket = FakeWebSocket()
    websocket.feed(frame, ["ping"])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code == 1002
    # Nothing after the malformed frame is processed.
    assert ["ping", "pong"] not in websocket.sent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        None,
        "not an event",
        # A JSON-encoded event is still a string, not an event.
        json.dumps({"name": "state.on_click", "payload": {}, "router_data": {}}),
        42,
        {"name": 123, "payload": {}, "router_data": {}},
        {"name": "x", "payload": "nope", "router_data": {}},
        {"name": "x", "payload": {}, "router_data": {"query": "not-a-dict"}},
    ],
)
async def test_undeserializable_event_closes_connection(
    namespace: WebsocketEventNamespace,
    mock_app: Mock,
    payload: object,
    caplog: pytest.LogCaptureFixture,
):
    """An event frame that fails deserialization closes with 1002 and no warning."""
    websocket = FakeWebSocket()
    websocket.feed(["event", payload], ["ping"])
    with caplog.at_level(logging.DEBUG, logger="reflex.event_namespace"):
        await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code == 1002
    assert ["ping", "pong"] not in websocket.sent
    mock_app.event_processor.enqueue.assert_not_awaited()
    # Client-controlled input must not write above debug level.
    assert all(record.levelno <= logging.DEBUG for record in caplog.records)


@pytest.mark.asyncio
async def test_handler_error_keeps_connection(
    namespace: WebsocketEventNamespace,
    mock_app: Mock,
    caplog: pytest.LogCaptureFixture,
):
    """A server-side handler failure is logged and the connection survives."""
    mock_app.event_processor.enqueue.side_effect = RuntimeError("server bug")
    websocket = FakeWebSocket()
    websocket.feed(
        ["event", {"name": "state.on_click", "payload": {}, "router_data": {}}],
        ["ping"],
    )
    with caplog.at_level(logging.ERROR, logger="reflex.event_namespace"):
        await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code is None
    assert ["ping", "pong"] in websocket.sent
    assert any(
        record.levelno == logging.ERROR
        and "Error handling socket event" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_tokenless_connection_rejected(
    namespace: WebsocketEventNamespace, caplog: pytest.LogCaptureFixture
):
    """A connection without a token closes with 1008 and logs nothing above debug.

    The version mismatch is not reported either: it is client-controlled and
    the session is rejected anyway, so warning would only let anonymous
    connects flood the logs.
    """
    websocket = FakeWebSocket(query_string=b"", subprotocols=["0.0.1"])
    websocket.feed(["ping"])
    with caplog.at_level(logging.DEBUG, logger="reflex.event_namespace"):
        await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code == 1008
    assert ["ping", "pong"] not in websocket.sent
    assert all(record.levelno <= logging.DEBUG for record in caplog.records)


@pytest.mark.asyncio
async def test_version_mismatch_warns_for_linked_session(
    namespace: WebsocketEventNamespace, caplog: pytest.LogCaptureFixture
):
    """A linked session with a stale frontend gets one sanitized warning."""
    websocket = FakeWebSocket(subprotocols=["0.0.1\x1b[31m"])
    websocket.feed()
    with caplog.at_level(logging.WARNING, logger="reflex.event_namespace"):
        await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "0.0.1" in warnings[0]
    assert "does not match the backend version" in warnings[0]
    assert "\x1b" not in warnings[0]


@pytest.mark.asyncio
async def test_oversize_message_closes_connection(
    namespace: WebsocketEventNamespace, monkeypatch: pytest.MonkeyPatch
):
    """A frame over the size limit closes the connection with 1009."""
    monkeypatch.setenv("REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE", "10")
    websocket = FakeWebSocket()
    websocket.feed(["event", {"payload": "x" * 100}])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code == 1009


@pytest.mark.asyncio
async def test_oversize_multibyte_message_closes_connection(
    namespace: WebsocketEventNamespace, monkeypatch: pytest.MonkeyPatch
):
    """The size limit counts bytes, so multibyte text cannot sneak past it."""
    monkeypatch.setenv("REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE", "25")
    # 15 characters (under the limit) but 29 UTF-8 bytes (over it).
    frame = '["x","€€€€€€€"]'
    assert len(frame) <= 25 < len(frame.encode("utf-8"))
    websocket = FakeWebSocket()
    websocket.feed(frame)
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code == 1009


@pytest.mark.asyncio
async def test_multibyte_message_within_limit_is_processed(
    namespace: WebsocketEventNamespace, monkeypatch: pytest.MonkeyPatch
):
    """Multibyte frames within the byte limit pass through the exact check."""
    # 12 characters, 14 bytes: over limit/4 (triggers the exact byte count)
    # but within the limit itself.
    monkeypatch.setenv("REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE", "14")
    websocket = FakeWebSocket()
    websocket.feed('["ping","€"]')
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code is None
    assert ["ping", "pong"] in websocket.sent


@pytest.mark.asyncio
async def test_binary_frame_closes_connection(namespace: WebsocketEventNamespace):
    """A binary frame closes the connection with 1003 (unsupported data)."""
    websocket = FakeWebSocket()
    websocket.feed(b"\x00\x01")
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code == 1003


@pytest.mark.asyncio
async def test_disallowed_origin_is_rejected(
    namespace: WebsocketEventNamespace, mocker
):
    """A cross-origin connection is closed before being accepted."""
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
    """A connection from an allowed origin is accepted."""
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
    """A second tab connecting with the same token receives a new_token frame."""
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
    caplog: pytest.LogCaptureFixture,
):
    """Emitting to a session that went away is a silent no-op.

    A client disconnecting mid-event is routine, so nothing above DEBUG may be
    logged.
    """
    with caplog.at_level(logging.DEBUG, logger="reflex.event_namespace"):
        await namespace.emit("event", {"delta": {}}, to="gone")
    assert all(record.levelno <= logging.DEBUG for record in caplog.records)


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
    """transport="socketio" sets up the Socket.IO server and namespace."""
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
    """transport="polling" sets up the Socket.IO server with polling only."""
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
    """A custom sio server works with the Socket.IO transport."""
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


def test_protocol_message_names_match_the_client():
    """The client speaks the same protocol message names as the server.

    Both ends declare these independently, and a rename on one side is
    invisible until a browser fails to connect: the client would never
    answer a heartbeat, so every session would be dropped on ping timeout.
    """
    declarations = dict(
        re.findall(
            r'^const (\w+_MESSAGE) = "([^"]+)";$',
            WEBSOCKET_JS_TEMPLATE.read_text(),
            re.MULTILINE,
        )
    )

    assert declarations == {
        "HANDSHAKE_MESSAGE": HANDSHAKE_MESSAGE,
        "PING_MESSAGE": PING_MESSAGE,
        "PONG_MESSAGE": PONG_MESSAGE,
    }
