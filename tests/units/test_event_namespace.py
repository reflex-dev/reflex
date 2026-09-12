"""Tests for the plain WebSocket event transport in reflex/event_namespace.py."""

import asyncio
import base64
import json
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from opentelemetry import trace
from reflex_base import otel
from starlette.routing import WebSocketRoute

from reflex import event_namespace
from reflex.app import App
from reflex.channels import (
    MAX_MESSAGE_BUFFERS,
    RESERVED_EVENTS,
    Channel,
    ChannelSession,
)
from reflex.event_namespace import (
    CHANNEL_ERROR_MESSAGE,
    CLOSE_MESSAGE,
    HANDSHAKE_MESSAGE,
    OPEN_MESSAGE,
    OPENED_MESSAGE,
    PING_MESSAGE,
    PONG_MESSAGE,
    PROTOCOL_VERSION,
    WebsocketEventNamespace,
    decode_channel_frame,
    encode_channel_frame,
)
from reflex.utils import format

from .conftest import active_tracer, metric_points

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

    async def send_bytes(self, data: bytes):
        """Record an outgoing binary frame."""
        self.sent.append(data)

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
    app._channels = {}
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
    assert set(websocket.sent[0][1]) == {
        "ping_interval",
        "ping_timeout",
        "protocol",
        "max_message_size",
    }
    assert websocket.sent[0][1]["protocol"] == PROTOCOL_VERSION
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


@pytest.mark.asyncio
async def test_websocket_records_connections_and_message_sizes(
    namespace: WebsocketEventNamespace, otel_metrics
):
    """A session adjusts the connection gauge and sizes frames in both directions."""
    websocket = FakeWebSocket()
    websocket.feed(["ping"])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    (connections,) = metric_points(otel_metrics, otel.METRIC_WEBSOCKET_CONNECTIONS)
    # Connect and disconnect both happened, so the gauge is back at zero.
    assert connections.value == 0
    sizes = {
        p.attributes[otel.ATTR_NETWORK_IO_DIRECTION]: p.sum
        for p in metric_points(otel_metrics, otel.METRIC_WEBSOCKET_MESSAGE_SIZE)
    }
    assert sizes == {
        "receive": len(json.dumps(["ping"])),
        "transmit": len(format.json_dumps(["ping", "pong"])),
    }


@pytest.mark.asyncio
async def test_websocket_event_uses_frontend_traceparent(
    namespace: WebsocketEventNamespace, mock_app: Mock, otel_exporter
):
    """A traceparent in the event payload becomes the parent of the event span."""
    seen: list = []

    async def enqueue(token, event):
        await asyncio.sleep(0)
        seen.append(trace.get_current_span().get_span_context())

    mock_app.event_processor.enqueue = enqueue
    traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    websocket = FakeWebSocket()
    websocket.feed(
        ["event", {"name": "state.h", "traceparent": traceparent}],
        ["event", {"name": "state.h"}],
    )
    with active_tracer().start_as_current_span("websocket"):
        await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    remote, fresh = seen
    assert f"{remote.trace_id:032x}" == "0af7651916cd43dd8448eb211c80319c"
    assert not fresh.is_valid


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
        "OPEN_MESSAGE": OPEN_MESSAGE,
        "OPENED_MESSAGE": OPENED_MESSAGE,
        "CLOSE_MESSAGE": CLOSE_MESSAGE,
        "CHANNEL_ERROR_MESSAGE": CHANNEL_ERROR_MESSAGE,
    }


class RecordingChannel(Channel):
    """A channel that records what the transport hands it."""

    name = "probe"

    def __init__(self, accepts_binary: bool = False):
        """Initialize the channel, recording opens, messages and closes."""
        type(self).accepts_binary = accepts_binary
        super().__init__()
        self.opened: list[ChannelSession] = []
        self.closed: list[ChannelSession] = []
        self.messages: list[tuple[str, Any, list[bytes]]] = []

    async def on_open(self, session: ChannelSession) -> None:
        """Record the opened session."""
        self.opened.append(session)

    async def on_message(
        self, session: ChannelSession, event: str, data: Any, buffers: list[bytes]
    ) -> None:
        """Record the message and answer an echo."""
        self.messages.append((event, data, buffers))
        await session.send("echo", data, buffers)

    async def on_close(self, session: ChannelSession) -> None:
        """Record the closed session."""
        self.closed.append(session)


def channel_frames(websocket: FakeWebSocket, channel: str = "probe") -> list[Any]:
    """Text frames the server sent on a channel.

    Args:
        websocket: The fake websocket.
        channel: The channel name.

    Returns:
        The matching frames.
    """
    return [
        frame
        for frame in websocket.sent
        if isinstance(frame, list) and len(frame) > 2 and frame[2] == channel
    ]


def test_channel_frame_round_trip():
    """A binary frame decodes to the values it was built from."""
    buffers = [b"\x01\x02\x03", b"", bytes(range(16))]
    frame = encode_channel_frame("payload", {"fig": "f1"}, "probe", buffers)
    assert decode_channel_frame(frame) == ("payload", {"fig": "f1"}, "probe", buffers)


def test_channel_frame_aligns_attachments():
    """Every attachment starts on an 8-byte boundary, whatever the header size."""
    for name_length in range(1, 24):
        frame = encode_channel_frame(
            "e", {"pad": "x" * name_length}, "probe", [b"\x01" * 3, b"\x02" * 5]
        )
        offsets = []
        offset = 4 + int.from_bytes(frame[:4], "little")
        for length in (3, 5):
            offset += -offset % 8
            offsets.append(offset)
            offset += length
        assert all(candidate % 8 == 0 for candidate in offsets)
        assert frame[offsets[0] : offsets[0] + 3] == b"\x01" * 3
        assert frame[offsets[1] : offsets[1] + 5] == b"\x02" * 5


@pytest.mark.parametrize(
    "frame",
    [
        b"",
        b"\x02\x00",
        (255).to_bytes(4, "little") + b'["e",null,"c",[]]',
        (17).to_bytes(4, "little") + b'["e",null,"c",42]',
        (18).to_bytes(4, "little") + b'["e",null,"c",[1]]',
        (21).to_bytes(4, "little") + b'["e",null,"c",[-1]]xx',
        (17).to_bytes(4, "little") + b'{"not": "a list"}',
        (11).to_bytes(4, "little") + b"not json at all",
    ],
)
def test_malformed_channel_frame_is_rejected(frame: bytes):
    """A frame that does not follow the binary format raises."""
    with pytest.raises(ValueError):
        decode_channel_frame(frame)


def test_channel_frame_rejects_too_many_attachments():
    """A frame declaring more attachments than the cap raises."""
    header = json.dumps(["e", None, "c", [0] * 65]).encode()
    with pytest.raises(ValueError, match="more than"):
        decode_channel_frame(len(header).to_bytes(4, "little") + header)


@pytest.mark.asyncio
async def test_channel_open_and_message(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """Opening a channel answers _opened and routes messages to the channel."""
    channel = RecordingChannel()
    mock_app._channels = {"probe": channel}
    websocket = FakeWebSocket()
    websocket.feed([OPEN_MESSAGE, None, "probe"], ["sub", {"fig": "f1"}, "probe"])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert channel_frames(websocket)[0] == [OPENED_MESSAGE, None, "probe"]
    assert [session.client_token for session in channel.opened] == ["tok1"]
    assert channel.messages == [("sub", {"fig": "f1"}, [])]
    assert ["echo", {"fig": "f1"}, "probe"] in websocket.sent
    # The disconnect closed the session again.
    assert channel.closed == channel.opened


@pytest.mark.asyncio
async def test_channel_unknown_name_reports_error(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """Opening a channel the backend does not serve answers _error."""
    mock_app._channels = {}
    websocket = FakeWebSocket()
    websocket.feed([OPEN_MESSAGE, None, "nope"])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    error = channel_frames(websocket, "nope")[0]
    assert error[0] == CHANNEL_ERROR_MESSAGE
    assert error[1]["code"] == "unknown_channel"


@pytest.mark.asyncio
async def test_channel_message_before_open_reports_error(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """A message for an unopened channel answers _error and is not dispatched."""
    channel = RecordingChannel()
    mock_app._channels = {"probe": channel}
    websocket = FakeWebSocket()
    websocket.feed(["sub", {}, "probe"])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert channel_frames(websocket)[0][1]["code"] == "channel_not_open"
    assert channel.messages == []


@pytest.mark.asyncio
async def test_channel_close_ends_the_session(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """A _close frame runs on_close and stops dispatching to the channel."""
    channel = RecordingChannel()
    mock_app._channels = {"probe": channel}
    websocket = FakeWebSocket()
    websocket.feed(
        [OPEN_MESSAGE, None, "probe"],
        [CLOSE_MESSAGE, None, "probe"],
        ["sub", {}, "probe"],
    )
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert len(channel.closed) == 1
    assert channel.messages == []
    assert channel_frames(websocket)[-1][1]["code"] == "channel_not_open"


@pytest.mark.asyncio
async def test_channel_binary_message_round_trip(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """A binary frame reaches a channel that accepts binary, and echoes back."""
    channel = RecordingChannel(accepts_binary=True)
    mock_app._channels = {"probe": channel}
    websocket = FakeWebSocket()
    websocket.feed(
        [OPEN_MESSAGE, None, "probe"],
        encode_channel_frame("push", {"n": 2}, "probe", [b"\x00\x01", b"\x02"]),
    )
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert channel.messages == [("push", {"n": 2}, [b"\x00\x01", b"\x02"])]
    echoed = [frame for frame in websocket.sent if isinstance(frame, bytes)]
    assert decode_channel_frame(echoed[0]) == (
        "echo",
        {"n": 2},
        "probe",
        [b"\x00\x01", b"\x02"],
    )


@pytest.mark.asyncio
async def test_channel_binary_rejected_when_not_accepted(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """Binary attachments to a text-only channel answer _error."""
    channel = RecordingChannel(accepts_binary=False)
    mock_app._channels = {"probe": channel}
    websocket = FakeWebSocket()
    websocket.feed(
        [OPEN_MESSAGE, None, "probe"],
        encode_channel_frame("push", None, "probe", [b"\x00"]),
    )
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert channel_frames(websocket)[-1][1]["code"] == "binary_not_accepted"
    assert channel.messages == []


@pytest.mark.asyncio
async def test_malformed_binary_frame_closes_connection(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """A binary frame that is not a channel frame closes the connection."""
    mock_app._channels = {"probe": RecordingChannel()}
    websocket = FakeWebSocket()
    websocket.feed(b"\xff\xff\xff\xff not a frame")
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code == 1002


@pytest.mark.asyncio
async def test_oversize_binary_frame_closes_connection(
    namespace: WebsocketEventNamespace, mock_app: Mock, monkeypatch: pytest.MonkeyPatch
):
    """A binary frame over the size limit closes the connection with 1009."""
    mock_app._channels = {"probe": RecordingChannel()}
    monkeypatch.setenv("REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE", "16")
    websocket = FakeWebSocket()
    websocket.feed(encode_channel_frame("push", None, "probe", [b"\x00" * 64]))
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code == 1009


@pytest.mark.asyncio
async def test_channel_handler_error_keeps_connection(
    namespace: WebsocketEventNamespace, mock_app: Mock, caplog
):
    """A channel handler raising is logged without dropping the connection."""

    class BoomChannel(Channel):
        name = "boom"

        async def on_message(self, session, event, data, buffers) -> None:
            msg = "handler failed"
            raise RuntimeError(msg)

    mock_app._channels = {"boom": BoomChannel()}
    websocket = FakeWebSocket()
    with caplog.at_level(logging.ERROR):
        websocket.feed([OPEN_MESSAGE, None, "boom"], ["go", None, "boom"], ["ping"])
        await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
        await _drain_tasks()

    assert websocket.close_code is None
    assert ["ping", "pong"] in websocket.sent
    assert "handler failed" in caplog.text


@pytest.mark.asyncio
async def test_channel_frame_with_non_string_name_closes_connection(
    namespace: WebsocketEventNamespace,
):
    """A frame whose channel element is not a string closes the connection."""
    websocket = FakeWebSocket()
    websocket.feed(["sub", None, 42])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code == 1002


NODE = shutil.which("node") or ""


@pytest.mark.skipif(not NODE, reason="Requires node to run the client codec")
def test_binary_frame_codec_matches_the_client(tmp_path: Path):
    """Both ends agree on the binary frame layout, both ways.

    The layout (header length, padding, alignment) is implemented twice, and a
    disagreement would only surface as an unreadable payload in a browser.
    """
    buffers = [b"\x01\x02\x03", b"", bytes(range(24))]
    frame = encode_channel_frame("payload", {"fig": "f1", "n": 3}, "probe", buffers)
    script = tmp_path / "codec.mjs"
    # A file URL, not a path: an absolute Windows path is neither a valid ESM
    # specifier nor a valid JS string literal (its separators are escapes).
    template = json.dumps(WEBSOCKET_JS_TEMPLATE.as_uri())
    script.write_text(f"""
import {{ encodeChannelFrame, decodeChannelFrame }} from {template};

const fromPython = Uint8Array.from(Buffer.from(process.argv[2], "base64"));
const [event, data, channel, buffers] = decodeChannelFrame(fromPython.buffer);
const encoded = encodeChannelFrame(event, data, channel, buffers);
console.log(JSON.stringify({{
    event,
    data,
    channel,
    lengths: buffers.map((b) => b.byteLength),
    // Every attachment must be readable as a typed array in place.
    aligned: buffers.every((b) => b.byteOffset % 8 === 0),
    encoded: Buffer.from(encoded).toString("base64"),
}}));
""")
    result = subprocess.run(
        [NODE, str(script), base64.b64encode(frame).decode()],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    decoded = json.loads(result.stdout)

    assert decoded["event"] == "payload"
    assert decoded["data"] == {"fig": "f1", "n": 3}
    assert decoded["channel"] == "probe"
    assert decoded["lengths"] == [len(buffer) for buffer in buffers]
    assert decoded["aligned"]
    # The frame the client built decodes back to the same message.
    assert decode_channel_frame(base64.b64decode(decoded["encoded"])) == (
        "payload",
        {"fig": "f1", "n": 3},
        "probe",
        buffers,
    )


@pytest.mark.asyncio
async def test_repeated_channel_open_reuses_the_session(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """Opening an already-open channel answers again without a second session.

    A second session would keep the first one's room membership alive with
    nothing left to close it.
    """

    class RoomChannel(RecordingChannel):
        name = "probe"

        async def on_open(self, session: ChannelSession) -> None:
            """Join a room so an orphaned session would be observable."""
            await super().on_open(session)
            session.join("all")

    channel = RoomChannel()
    mock_app._channels = {"probe": channel}
    websocket = FakeWebSocket()
    websocket.feed([OPEN_MESSAGE, None, "probe"], [OPEN_MESSAGE, None, "probe"])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert len(channel.opened) == 1
    assert [frame[0] for frame in channel_frames(websocket)] == [
        OPENED_MESSAGE,
        OPENED_MESSAGE,
    ]
    # The disconnect left nothing behind.
    assert channel._rooms == {}
    assert channel._sessions == {}


@pytest.mark.asyncio
async def test_interrupted_teardown_still_unlinks_the_token(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """Token cleanup starts before any teardown await can be interrupted.

    Server shutdown cancels the connection task, and an await in the teardown
    path raises again inside a cancelled scope. A token left linked would make
    the client's reconnect look like a duplicate tab.
    """

    class StallingChannel(RecordingChannel):
        name = "probe"

        async def on_close(self, session: ChannelSession) -> None:
            """Fail the way a cancelled cleanup await would."""
            raise asyncio.CancelledError

    mock_app._channels = {"probe": StallingChannel()}
    websocket = FakeWebSocket()
    websocket.feed([OPEN_MESSAGE, None, "probe"])
    with pytest.raises(asyncio.CancelledError):
        await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert "tok1" not in namespace.token_to_sid


@pytest.mark.asyncio
async def test_interrupted_open_leaves_no_session_behind(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """A session interrupted inside on_open is still cleaned up on disconnect.

    on_open may already have joined rooms, so a session the transport never
    recorded would stay reachable by fan-out with nothing left to close it.
    """

    class InterruptedChannel(RecordingChannel):
        name = "probe"

        async def on_open(self, session: ChannelSession) -> None:
            """Join a room, then fail the way a cancellation would."""
            session.join("all")
            raise asyncio.CancelledError

    channel = InterruptedChannel()
    mock_app._channels = {"probe": channel}
    websocket = FakeWebSocket()
    websocket.feed([OPEN_MESSAGE, None, "probe"])
    with pytest.raises(asyncio.CancelledError):
        await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert channel._rooms == {}
    assert channel._sessions == {}


@pytest.mark.asyncio
async def test_disconnect_marks_the_session_closed(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """The session a channel holds reports the disconnect to its handlers."""
    channel = RecordingChannel()
    mock_app._channels = {"probe": channel}
    websocket = FakeWebSocket()
    websocket.feed([OPEN_MESSAGE, None, "probe"])
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert [session.open for session in channel.opened] == [False]


@pytest.mark.asyncio
async def test_deeply_nested_frame_closes_connection(
    namespace: WebsocketEventNamespace,
):
    """A frame the JSON decoder cannot recurse through closes the connection.

    Deep nesting exhausts the decoder's stack instead of failing to parse, and
    a RecursionError escaping the receive loop would drop the session with a
    traceback rather than a protocol close.
    """
    depth = sys.getrecursionlimit() * 200
    websocket = FakeWebSocket()
    websocket.feed("[" * depth + "]" * depth)
    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code == 1002


def test_decoding_a_too_deeply_nested_header_is_a_value_error(mocker):
    """A header the decoder cannot recurse through fails like any bad frame.

    Callers handle malformed frames by catching ValueError; that the decoder
    signals deep nesting with RecursionError is its own business, and the
    header size cap makes how deep is too deep interpreter-specific, so the
    failure is simulated rather than provoked.
    """
    # Only this module's reference to json, so nothing else loses its decoder.
    mocker.patch.object(
        event_namespace,
        "json",
        SimpleNamespace(loads=Mock(side_effect=RecursionError("too deep"))),
    )
    frame = encode_channel_frame("push", None, "probe", [b"\x00"])

    with pytest.raises(ValueError, match="nested too deeply"):
        decode_channel_frame(frame)


@pytest.mark.asyncio
async def test_handshake_advertises_the_message_limit(
    namespace: WebsocketEventNamespace, monkeypatch: pytest.MonkeyPatch
):
    """The client needs the inbound limit to refuse an oversized frame itself."""
    monkeypatch.setenv("REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE", "4096")
    websocket = FakeWebSocket()
    websocket.feed()

    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.sent[0][1]["max_message_size"] == 4096


def test_client_limits_match_the_protocol():
    """The client enforces the same caps the backend closes the connection over.

    Both ends declare them independently; a client cap that drifted above the
    backend's would turn a loud local error back into a dropped connection.
    """
    template = WEBSOCKET_JS_TEMPLATE.read_text()

    assert f"const MAX_MESSAGE_BUFFERS = {MAX_MESSAGE_BUFFERS};" in template
    reserved = re.search(r"const LIFECYCLE_EVENTS = new Set\(\[([^\]]+)\]\);", template)
    assert reserved is not None
    assert {name.strip().strip('"') for name in reserved.group(1).split(",")} == set(
        RESERVED_EVENTS
    )


@pytest.mark.skipif(not NODE, reason="Requires node to run the client")
def test_client_refuses_frames_the_backend_would_close_over(tmp_path: Path):
    """The client enforces the size limit itself, whenever it learns of it.

    The backend answers an oversized frame by closing the connection, taking
    the app's state updates with it, so every path that can produce one has to
    be stopped on the client: emitting while open, emitting before the channel
    opens (checked again when the limit arrives), and multibyte text, whose
    UTF-8 size is what the backend measures.
    """
    script = tmp_path / "limits.mjs"
    script.write_text(f"""
import {{ getChannel }} from {json.dumps(WEBSOCKET_JS_TEMPLATE.as_uri())};

const result = {{ sent: 0, errors: [] }};
const transport = {{ _maxMessageSize: 1024, _send: () => {{ result.sent += 1; }} }};

const open = getChannel("open");
open._transport = transport;
open.connected = true;
try {{
    open.emit("push", {{ blob: "x".repeat(5000) }});
}} catch (error) {{
    result.tooBig = error.message;
}}
try {{
    // 400 characters, 1200 UTF-8 bytes: only a byte-accurate check catches it.
    // An escape rather than the character itself, so this script stays ASCII
    // whatever encoding the test's locale writes it in.
    open.emit("push", "\\u20ac".repeat(400));
}} catch (error) {{
    result.multibyte = error.message;
}}
open.emit("push", {{ small: true }});

// Emitted with no transport, so with no limit to check against yet.
const queued = getChannel("queued");
queued.on("error", (error) => result.errors.push(error.code));
queued.emit("push", {{ blob: "y".repeat(5000) }});
queued._transport = transport;
queued._receive("_opened", null, []);

console.log(JSON.stringify(result));
""")
    result = subprocess.run(
        [NODE, str(script)], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert "1024" in report["tooBig"]
    # 400 characters: a length check would have passed it, a byte check does not.
    multibyte = re.search(r"is (\d+) bytes", report["multibyte"])
    assert multibyte is not None, report["multibyte"]
    assert 1024 < int(multibyte.group(1)) < 4 * 400
    assert report["errors"] == ["message_too_large"]
    # Only the message that fits was ever handed to the transport.
    assert report["sent"] == 1


@pytest.mark.asyncio
async def test_large_metadata_is_bounded_only_by_the_message_limit(
    namespace: WebsocketEventNamespace, mock_app: Mock
):
    """Metadata is limited by the frame size, not by a second hidden cap.

    The same metadata sent without attachments travels as a text frame, which
    only the message limit applies to; a binary frame that rejected it would
    close the connection over a payload the client had no way to know was too
    big -- the handshake advertises one limit. Driven through the receive path,
    because that is where such a frame would be turned into a close.
    """
    channel = RecordingChannel(accepts_binary=True)
    mock_app._channels = {"probe": channel}
    # Far past any header-shaped cap, far under the 1 MB message limit.
    metadata = {"spec": "x" * (128 * 1024)}
    websocket = FakeWebSocket()
    websocket.feed(
        [OPEN_MESSAGE, None, "probe"],
        encode_channel_frame("payload", metadata, "probe", [b"\x00\x01"]),
    )

    await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
    await _drain_tasks()

    assert websocket.close_code is None
    assert channel.messages == [("payload", metadata, [b"\x00\x01"])]


@pytest.mark.asyncio
async def test_event_from_a_session_whose_token_went_away_closes_it(
    namespace: WebsocketEventNamespace, mock_app: Mock, caplog
):
    """A session that loses its token mid-connection is closed, not left logging.

    The token manager drops the mapping when a token moves to another socket
    or its record goes stale, while that socket stays open and sending.
    Everything it sends is unservable, so answering each frame with a warning
    that embeds the client's payload is both a log flood and an injection
    vector.
    """

    class LosesItsToken(FakeWebSocket):
        """Drops the token mapping once the connection is already serving."""

        async def receive(self) -> dict[str, Any]:
            message = await super().receive()
            namespace.sid_to_token.clear()
            return message

    websocket = LosesItsToken()
    websocket.feed(
        ["ping"],
        ["event", {"name": "state.on_click", "payload": {"x": "\n[fake] log line"}}],
    )

    with caplog.at_level(logging.DEBUG):
        await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
        await _drain_tasks()

    assert websocket.close_code == 1008
    mock_app.event_processor.enqueue.assert_not_awaited()
    # Nothing the client sent reached the log, at any level.
    assert "[fake] log line" not in caplog.text
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
