"""Benchmarks comparing the plain WebSocket transport with Socket.IO.

Measures the server-side transport layer in isolation: inbound event frames
from an established connection to the (mocked) event processor, and outbound
state updates to the (mocked) wire. Both transports share BaseEventNamespace,
so the difference is the framing and dispatch layer. Socket.IO runs with
``async_handlers=False`` (inline dispatch), its cheapest configuration.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
import pytest_asyncio
from pytest_codspeed import BenchmarkFixture

from reflex.event_namespace import WebsocketEventNamespace
from reflex.state import StateUpdate

NUM_MESSAGES = 100
NAMESPACE = "/_event"
TOKEN = "benchmark-token"

_EVENT_FIELDS = {
    "name": "benchmark___state.increment",
    "router_data": {
        "pathname": "/benchmark",
        "asPath": "/benchmark?tab=2",
        "query": {"tab": "2"},
    },
    "payload": {"value": 42, "label": "increment", "flag": True},
}

_UPDATE = StateUpdate(
    delta={
        "benchmark___state": {f"var_{i}": f"value_{i}" for i in range(15)}
        | {"counter": 42, "flag": True, "items": list(range(10))},
    }
)

_DISCONNECT = object()

_ASGI_SCOPE = {
    "type": "websocket",
    "headers": [(b"host", b"localhost")],
    "client": ("127.0.0.1", 1234),
}


def _make_app(sio: Any = None) -> SimpleNamespace:
    """Build a minimal app double for the event namespace.

    Returns:
        The app double.
    """
    enqueued: list[Any] = []

    async def enqueue(token: str, event: Any) -> None:  # noqa: RUF029
        enqueued.append((token, event))

    return SimpleNamespace(
        _state=None,
        sio=sio,
        router=lambda _path: None,
        event_processor=SimpleNamespace(enqueue=enqueue),
        enqueued=enqueued,
    )


class FakeWebSocket:
    """Minimal stand-in for a starlette WebSocket."""

    def __init__(self, frames: list[str]):
        """Initialize with the inbound frames to deliver."""
        self.scope: dict[str, Any] = {
            "type": "websocket",
            "query_string": f"token={TOKEN}".encode(),
            "subprotocols": [],
            "headers": [(b"host", b"localhost")],
            "client": ("127.0.0.1", 1234),
        }
        self.headers: dict[str, str] = {}
        self.sent: list[str] = []
        self._incoming = [*frames, _DISCONNECT]
        self._pos = 0

    async def accept(self, subprotocol: str | None = None):
        """Accept the connection."""

    async def send_text(self, text: str):
        """Record an outgoing frame."""
        self.sent.append(text)

    async def receive(self) -> dict[str, Any]:
        """Return the next queued frame as an ASGI message.

        Returns:
            The ASGI websocket message.
        """
        item = self._incoming[self._pos]
        self._pos += 1
        if item is _DISCONNECT:
            return {"type": "websocket.disconnect", "code": 1000}
        return {"type": "websocket.receive", "text": item}

    async def close(self, code: int = 1000):
        """Close the connection."""


@pytest_asyncio.fixture
async def websocket_inbound():  # noqa: RUF029 - async so it runs on the benchmark loop
    """Runner delivering NUM_MESSAGES event frames over the plain transport.

    Yields:
        An async callable running one full connection lifecycle.
    """
    with mock.patch("reflex.utils.prerequisites.check_redis_used", return_value=False):
        app = _make_app()
        namespace = WebsocketEventNamespace(NAMESPACE, app)  # pyright: ignore[reportArgumentType]
        frames = [json.dumps(["event", _EVENT_FIELDS])] * NUM_MESSAGES

        async def run() -> None:
            websocket = FakeWebSocket(frames)
            await namespace.handle_websocket(websocket)  # pyright: ignore[reportArgumentType]
            assert len(app.enqueued) >= NUM_MESSAGES

        yield run


def _make_socketio_transport() -> tuple[Any, Any, SimpleNamespace]:
    """Build a Socket.IO server and namespace over an app double.

    The server runs with inline dispatch and a discarding writer, so a
    benchmark measures framing and dispatch rather than the network.

    Returns:
        The (server, namespace, app double) triple.
    """
    pytest.importorskip("socketio")
    from socketio import AsyncServer

    from reflex.socketio_namespace import _SOCKET_JSON_CODEC, EventNamespace

    sio = AsyncServer(async_mode="asgi", async_handlers=False, json=_SOCKET_JSON_CODEC)
    with mock.patch("reflex.utils.prerequisites.check_redis_used", return_value=False):
        app = _make_app(sio=sio)
        namespace = EventNamespace(NAMESPACE, app)  # pyright: ignore[reportArgumentType]
        sio.register_namespace(namespace)

    async def eio_send(_eio_sid: str, _data: str) -> None:
        pass

    sio.eio.send = eio_send
    return sio, namespace, app


@pytest_asyncio.fixture
async def socketio_inbound():  # noqa: RUF029 - async so it runs on the benchmark loop
    """Runner delivering NUM_MESSAGES event packets over Socket.IO.

    Returns:
        An async callable running one full connection lifecycle.
    """
    sio, _namespace, app = _make_socketio_transport()
    event_packet = "2" + NAMESPACE + "," + json.dumps(["event", _EVENT_FIELDS])
    counter = 0

    async def run() -> None:
        nonlocal counter
        counter += 1
        eio_sid = f"eio-{counter}"
        await sio._handle_eio_connect(
            eio_sid,
            {"QUERY_STRING": f"token={TOKEN}-{counter}", "asgi.scope": _ASGI_SCOPE},
        )
        await sio._handle_eio_message(eio_sid, "0" + NAMESPACE + ",")
        for _ in range(NUM_MESSAGES):
            await sio._handle_eio_message(eio_sid, event_packet)
        await sio._handle_eio_message(eio_sid, "1" + NAMESPACE + ",")
        # Let the disconnect cleanup task run.
        for _ in range(3):
            await asyncio.sleep(0)
        assert len(app.enqueued) >= NUM_MESSAGES

    return run


@pytest_asyncio.fixture
async def websocket_outbound():
    """Runner emitting NUM_MESSAGES state updates over the plain transport.

    Yields:
        An async callable emitting the updates.
    """
    with mock.patch("reflex.utils.prerequisites.check_redis_used", return_value=False):
        app = _make_app()
        namespace = WebsocketEventNamespace(NAMESPACE, app)  # pyright: ignore[reportArgumentType]
        websocket = FakeWebSocket([])
        namespace._sockets["sid-1"] = websocket  # pyright: ignore[reportArgumentType]
        await namespace.link_token_to_sid("sid-1", TOKEN)

        async def run() -> None:
            for _ in range(NUM_MESSAGES):
                await namespace.emit_update(_UPDATE, TOKEN)

        yield run


@pytest_asyncio.fixture
async def socketio_outbound():
    """Runner emitting NUM_MESSAGES state updates over Socket.IO.

    Returns:
        An async callable emitting the updates.
    """
    sio, namespace, _app = _make_socketio_transport()

    async def run() -> None:
        for _ in range(NUM_MESSAGES):
            await namespace.emit_update(_UPDATE, TOKEN)

    # Connect a socket.io session and link the token to its sid.
    eio_sid = "eio-emit"
    await sio._handle_eio_connect(
        eio_sid, {"QUERY_STRING": f"token={TOKEN}", "asgi.scope": _ASGI_SCOPE}
    )
    await sio._handle_eio_message(eio_sid, "0" + NAMESPACE + ",")
    assert TOKEN in namespace.token_to_sid

    return run


def _benchmark_runner(
    benchmark: BenchmarkFixture, runner: Callable[[], Awaitable[None]]
):
    """Benchmark one full run of an async transport runner.

    Args:
        benchmark: The benchmark fixture.
        runner: The async callable to measure.
    """
    loop = asyncio.get_event_loop()

    @benchmark
    def _():
        loop.run_until_complete(runner())


def test_transport_inbound_websocket(websocket_inbound, benchmark: BenchmarkFixture):
    """Benchmark inbound event handling on the plain WebSocket transport."""
    _benchmark_runner(benchmark, websocket_inbound)


def test_transport_inbound_socketio(socketio_inbound, benchmark: BenchmarkFixture):
    """Benchmark inbound event handling on the Socket.IO transport."""
    _benchmark_runner(benchmark, socketio_inbound)


def test_transport_outbound_websocket(websocket_outbound, benchmark: BenchmarkFixture):
    """Benchmark emitting state updates on the plain WebSocket transport."""
    _benchmark_runner(benchmark, websocket_outbound)


def test_transport_outbound_socketio(socketio_outbound, benchmark: BenchmarkFixture):
    """Benchmark emitting state updates on the Socket.IO transport."""
    _benchmark_runner(benchmark, socketio_outbound)
