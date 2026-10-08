"""Blocking client of Reflex's event websocket used by scheduled load tests.

It speaks the plain WebSocket protocol of Reflex's default transport, and the
Socket.IO packets of a backend that refuses that endpoint (``transport="socketio"``
apps and the python-socketio baseline server), so both sides of a comparison
pay the same client cost.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import dataclasses
import functools
import json
import time
from collections.abc import Callable, Mapping
from typing import Any

from reflex_bench.drivers.events import (
    CODECS,
    CONNECT,
    DISCONNECTED,
    HANDSHAKE,
    PING,
    REFUSED,
    SIO_CONNECT_FRAME,
    Codec,
)
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.sync.client import ClientConnection, connect

# Silence window that marks the connection quiescent while draining the extra
# deltas the first event on a fresh token emits (hydrate + on_load_internal).
_PRIME_DRAIN_TIMEOUT = 0.5


@dataclasses.dataclass(frozen=True)
class ClientLoadResult:
    """Latency observations and failures for one load client."""

    token: str
    latencies_ms: tuple[float, ...]
    errors: tuple[str, ...]
    payload_bytes: tuple[int, ...] = ()


@dataclasses.dataclass(frozen=True)
class ReconnectResult:
    """Connection and first-response observations for one reconnect client."""

    token: str
    connect_ms: float
    first_response_ms: float
    errors: tuple[str, ...]


class EventClient:
    """One session on Reflex's event websocket, used from one thread at a time."""

    def __init__(self, ws: ClientConnection, codec: Codec):
        """Wrap a connected websocket.

        Args:
            ws: The websocket.
            codec: The protocol it speaks.
        """
        self._ws = ws
        self._codec = codec

    def emit(self, name: str, data: Any) -> None:
        """Send a message.

        Args:
            name: The message name.
            data: Its payload.
        """
        self._ws.send(self._codec.emit(name, data))

    def receive(self, timeout: float, name: str | None = None) -> list[Any]:
        """Wait for the next message, answering pings on the way.

        Args:
            timeout: Seconds to wait; 0 takes only what already arrived.
            name: The message name to wait for, skipping others; any if None.

        Returns:
            The message, ``[name, *args]``.

        Raises:
            ConnectionError: When the server refuses or ends the session.
        """
        codec = self._codec
        deadline = time.monotonic() + timeout
        while True:
            message = self._ws.recv(timeout=deadline - time.monotonic())
            args = codec.parse(message)
            if args is None:
                # A frame without a message, e.g. a binary one.
                continue
            if args[0] == PING:
                self._ws.send(codec.pong)
            elif args[0] in {REFUSED, DISCONNECTED}:
                msg = f"the server ended the session: {message!r}"
                raise ConnectionError(msg)
            elif name is None or args[0] == name:
                return args

    def poll(self) -> None:
        """Handle the frames that already arrived, answering pings."""
        with contextlib.suppress(TimeoutError):
            while True:
                self.receive(0)

    def close(self) -> None:
        """Leave the session and close the websocket."""
        if (leave := self._codec.leave) is not None:
            with contextlib.suppress(ConnectionClosed):
                self._ws.send(leave)
        self._ws.close()


def _open(url: str, token: str, codec: Codec, timeout: float) -> ClientConnection:
    """Open the websocket of a session.

    Args:
        url: Backend URL.
        token: Reflex client token.
        codec: The protocol.
        timeout: Maximum connection wait.

    Returns:
        The websocket.
    """
    return connect(
        codec.url(url, token),
        additional_headers={"Origin": url},
        compression=None,
        proxy=None,
        open_timeout=timeout,
        ping_interval=None,
        close_timeout=1,
        max_size=None,
    )


def _connect(url: str, token: str, timeout: float) -> EventClient:
    """Connect a client the way the Reflex frontend does, without a boot event.

    A backend that refuses the plain protocol's endpoint gets Socket.IO.

    Args:
        url: Backend URL.
        token: Reflex client token.
        timeout: Maximum wait for the connection and its handshake.

    Returns:
        The connected client.
    """
    codec = CODECS["websocket"]
    try:
        ws = _open(url, token, codec, timeout)
    except InvalidStatus:
        codec = CODECS["socketio"]
        ws = _open(url, token, codec, timeout)
    client = EventClient(ws, codec)
    try:
        ws.send(
            SIO_CONNECT_FRAME
            if codec.protocol == "socketio"
            else codec.emit(CONNECT, {})
        )
        client.receive(timeout, HANDSHAKE)
    except BaseException:
        ws.close()
        raise
    return client


def _payload_size(response: Any) -> int:
    """Approximate the wire size of a received update payload.

    Args:
        response: Decoded ``[event, payload]`` message from the client.

    Returns:
        Compact JSON byte length of the payload, excluding the protocol's framing.
    """
    payload = response[1] if len(response) > 1 else None
    return len(json.dumps(payload, separators=(",", ":"), default=str))


def _drain(client: EventClient, timeout: float) -> None:
    """Consume buffered responses until the socket is quiet for ``timeout``.

    Args:
        client: Event websocket client.
        timeout: Silence window that marks the connection quiescent.
    """
    with contextlib.suppress(TimeoutError):
        while True:
            client.receive(timeout)


def _prime(
    client: EventClient,
    event_name: str,
    payload: Mapping[str, Any],
    timeout: float,
) -> None:
    """Hydrate a fresh token so later events observe a clean 1:1 response.

    The first application event on a fresh token triggers the rehydrate path,
    which emits extra full-state and ``on_load_internal`` deltas under the same
    ``event`` message name. Sending one warmup event and draining every response
    keeps the measured loop from reading those deltas as if they answered later
    events, which would otherwise report each latency pipelined two events deep.

    Args:
        client: Event websocket client.
        event_name: Message name used for requests.
        payload: Event payload emitted to trigger hydration.
        timeout: Maximum wait bounding the drain silence window.
    """
    client.emit(event_name, dict(payload))
    _drain(client, min(timeout, _PRIME_DRAIN_TIMEOUT))


async def run_socket_client(
    url: str,
    token: str,
    payload: Mapping[str, Any],
    events: int,
    *,
    event_name: str = "event",
    response_name: str = "event",
    timeout: float = 10,
    executor: concurrent.futures.Executor | None = None,
) -> ClientLoadResult:
    """Send events sequentially and measure matching socket responses.

    Args:
        url: Backend URL.
        token: Reflex client token.
        payload: Event payload emitted for each operation.
        events: Number of operations.
        event_name: Message name used for requests.
        response_name: Message name carrying state updates.
        timeout: Maximum response wait per operation.
        executor: Optional executor that owns the blocking socket client.

    Returns:
        Per-operation latency and error observations.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        executor,
        functools.partial(
            _run_socket_client_sync,
            url,
            token,
            payload,
            events,
            event_name,
            response_name,
            timeout,
        ),
    )


def _run_socket_client_sync(
    url: str,
    token: str,
    payload: Mapping[str, Any],
    events: int,
    event_name: str,
    response_name: str,
    timeout: float,
) -> ClientLoadResult:
    """Run a load client on a blocking websocket.

    Args:
        url: Backend URL.
        token: Reflex client token.
        payload: Event payload emitted for each operation.
        events: Number of operations.
        event_name: Message name used for requests.
        response_name: Message name carrying state updates.
        timeout: Maximum response wait per operation.

    Returns:
        Per-operation latency and error observations.
    """
    client: EventClient | None = None
    latencies: list[float] = []
    payload_sizes: list[int] = []
    errors: list[str] = []

    try:
        client = _connect(url, token, timeout)
        _prime(client, event_name, payload, timeout)
        for _ in range(events):
            started = time.perf_counter_ns()
            client.emit(event_name, dict(payload))
            try:
                response = client.receive(timeout, response_name)
            except TimeoutError:
                errors.append("response_timeout")
                continue
            latencies.append((time.perf_counter_ns() - started) / 1_000_000)
            payload_sizes.append(_payload_size(response))
    except Exception as err:
        errors.append(f"{type(err).__name__}: {err}")
    finally:
        if client is not None:
            client.close()

    return ClientLoadResult(
        token, tuple(latencies), tuple(errors), tuple(payload_sizes)
    )


async def run_reconnect_client(
    url: str,
    token: str,
    payload: Mapping[str, Any],
    *,
    event_name: str = "event",
    response_name: str = "event",
    timeout: float = 10,
    executor: concurrent.futures.Executor | None = None,
) -> ReconnectResult:
    """Connect, send one event, and measure connect and first-response time.

    Args:
        url: Backend URL.
        token: Reflex client token.
        payload: Event payload emitted after connecting.
        event_name: Message name used for the request.
        response_name: Message name carrying state updates.
        timeout: Maximum connection and response wait.
        executor: Optional executor that owns the blocking socket client.

    Returns:
        Connect and first-response observations.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        executor,
        functools.partial(
            _run_reconnect_client_sync,
            url,
            token,
            payload,
            event_name,
            response_name,
            timeout,
        ),
    )


def _run_reconnect_client_sync(
    url: str,
    token: str,
    payload: Mapping[str, Any],
    event_name: str,
    response_name: str,
    timeout: float,
) -> ReconnectResult:
    """Run one reconnect client on a blocking websocket.

    Args:
        url: Backend URL.
        token: Reflex client token.
        payload: Event payload emitted after connecting.
        event_name: Message name used for the request.
        response_name: Message name carrying state updates.
        timeout: Maximum connection and response wait.

    Returns:
        Connect and first-response observations.
    """
    client: EventClient | None = None
    connect_ms = 0.0
    first_response_ms = 0.0
    errors: list[str] = []

    try:
        started = time.perf_counter_ns()
        client = _connect(url, token, timeout)
        connect_ms = (time.perf_counter_ns() - started) / 1_000_000
        started = time.perf_counter_ns()
        client.emit(event_name, dict(payload))
        client.receive(timeout, response_name)
        first_response_ms = (time.perf_counter_ns() - started) / 1_000_000
    except TimeoutError:
        errors.append("response_timeout")
    except Exception as err:
        errors.append(f"{type(err).__name__}: {err}")
    finally:
        if client is not None:
            client.close()

    return ReconnectResult(token, connect_ms, first_response_ms, tuple(errors))


async def run_clients(
    clients: int,
    factory: Callable[[int, concurrent.futures.Executor], Any],
) -> list[Any]:
    """Run a parameterized set of clients concurrently.

    Args:
        clients: Number of clients.
        factory: Callable returning an awaitable for a client index and executor.

    Returns:
        Client results in index order.
    """
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, clients))
    try:
        return list(
            await asyncio.gather(
                *(factory(index, executor) for index in range(clients))
            )
        )
    finally:
        executor.shutdown(wait=True)
