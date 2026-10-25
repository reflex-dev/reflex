"""Tests for reflex_bench.drivers.echo_server.

The echo server's answers are exercised by the generator's tests; these check
its handshake against reflex's and the process that the calibration runs it in.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import psutil
import pytest
from reflex_base.environment import environment
from reflex_bench.drivers import events
from reflex_bench.drivers.echo_server import EchoProcess, EchoServer
from reflex_bench.drivers.events import Endpoint, EventShape, LoadPlan, run_load
from reflex_bench.suites.events import SEQ_VAR
from starlette.websockets import WebSocket
from websockets.asyncio.server import ServerConnection

from reflex import event_namespace
from reflex.utils import prerequisites
from tests.units.reflex_bench.factories import WEBSOCKET

STATE = "reflex___state____state.playground___state____bench_state"


class _Socket:
    """Just enough of a starlette websocket for reflex to open a plain session."""

    def __init__(self) -> None:
        """Queue a connect frame without a boot event, then the disconnect."""
        self.scope = {"type": "websocket", "query_string": b"token=tok", "headers": []}
        self.headers: dict[str, str] = {}
        self.sent: list[Any] = []
        self._received = [
            {"type": "websocket.receive", "text": WEBSOCKET.join},
            {"type": "websocket.disconnect", "code": 1000},
        ]

    async def accept(self, subprotocol: str | None = None) -> None:
        """Accept the connection.

        Args:
            subprotocol: The chosen subprotocol.
        """

    async def send_text(self, text: str) -> None:
        """Record a frame.

        Args:
            text: The frame.
        """
        self.sent.append(json.loads(text))

    async def receive(self) -> dict[str, Any]:
        """Take the next queued message once the writer ran, as the network lets it.

        Returns:
            The ASGI message.
        """
        await asyncio.sleep(0)
        return self._received.pop(0)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        """Close the connection.

        Args:
            code: The close code.
            reason: The close reason.
        """


class _Sent(list[str]):
    """A server connection that records what is sent on it."""

    async def send(self, frame: str) -> None:
        """Record a frame.

        Args:
            frame: The frame.
        """
        self.append(frame)


def test_the_handshake_is_copied_from_reflex(monkeypatch: pytest.MonkeyPatch):
    # reflex_bench drives releases without reflex.event_namespace, so it keeps a
    # copy of the handshake a default-configured app sends.
    for var in (
        environment.REFLEX_SOCKET_INTERVAL,
        environment.REFLEX_SOCKET_TIMEOUT,
        environment.REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE,
    ):
        monkeypatch.delenv(var.name, raising=False)
    monkeypatch.setattr(prerequisites, "check_redis_used", lambda: False)
    app = Mock(_state=None, _channels={}, router=Mock(return_value=None))
    app.event_processor.enqueue = AsyncMock()
    namespace = event_namespace.WebsocketEventNamespace(events.NAMESPACE, app)
    socket = _Socket()
    asyncio.run(namespace.handle_websocket(cast(WebSocket, socket)))
    reflex_name, reflex_settings = socket.sent[0]
    sent = _Sent()
    server = EchoServer(delta_key=STATE, seq_var=SEQ_VAR)
    asyncio.run(server.on_connect(cast(ServerConnection, sent), "sid"))
    (frame,) = sent
    message = WEBSOCKET.parse(frame)
    assert message is not None
    name, settings = message
    assert name == reflex_name == events.HANDSHAKE
    assert settings == reflex_settings


def test_echo_process_answers_a_load_and_stops():
    echo = EchoProcess(delta_key=STATE, seq_var=SEQ_VAR)
    with pytest.raises(RuntimeError, match="not started"):
        _ = echo.pid
    url = echo.start()
    try:
        # The memory benchmarks read the server's memory by its pid.
        assert psutil.Process(echo.pid).name().startswith("python")
        shape = EventShape(
            name=f"{STATE}.set_seq",
            payload=events.seq_payload,
            delta_key=STATE,
            seq_var=SEQ_VAR,
        )
        result = run_load(
            LoadPlan(
                endpoint=Endpoint(url),
                shape=shape,
                sessions=2,
                mode="closed",
                rate=None,
                warmup_s=0.1,
                duration_s=0.3,
            )
        )
    finally:
        echo.stop()
    assert result.answered > 0
    assert result.unanswered == 0
    assert result.session_errors == []
    assert echo._proc is not None
    assert not echo._proc.is_alive()
    echo.stop()


def test_echo_process_exits_when_its_parent_goes_away():
    echo = EchoProcess(delta_key=STATE, seq_var=SEQ_VAR)
    echo.start()
    proc, conn = echo._proc, echo._conn
    assert proc is not None
    assert conn is not None
    try:
        # Closing the parent's end of the pipe is what any exit of the parent does.
        conn.close()
        proc.join(10)
        assert proc.exitcode is not None
    finally:
        echo.stop()
