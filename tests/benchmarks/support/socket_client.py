"""Protocol-aware Socket.IO client used by scheduled load tests."""

from __future__ import annotations

import asyncio
import concurrent.futures
import dataclasses
import functools
import json
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import quote

import socketio
from socketio.exceptions import TimeoutError as SocketTimeoutError


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


def _payload_size(response: Any) -> int:
    """Approximate the wire size of a received update payload.

    Args:
        response: Decoded ``[event, payload]`` message from the client.

    Returns:
        Compact JSON byte length of the payload, excluding Socket.IO framing.
    """
    payload = response[1] if len(response) > 1 else None
    return len(json.dumps(payload, separators=(",", ":"), default=str))


def _connect(
    client: socketio.SimpleClient,
    url: str,
    token: str,
    namespace: str,
    timeout: float,
) -> None:
    """Connect a client the way the Reflex frontend does.

    Args:
        client: Blocking Socket.IO client.
        url: Backend Socket.IO URL.
        token: Reflex client token.
        namespace: Reflex Socket.IO namespace.
        timeout: Maximum connection wait.
    """
    separator = "&" if "?" in url else "?"
    client.connect(
        f"{url}{separator}token={quote(token)}",
        transports=["websocket"],
        socketio_path="_event",
        headers={"Origin": url},
        namespace=namespace,
        wait_timeout=max(1, int(timeout)),
    )


async def run_socket_client(
    url: str,
    token: str,
    payload: Mapping[str, Any],
    events: int,
    *,
    event_name: str = "event",
    response_name: str = "event",
    namespace: str = "/_event",
    timeout: float = 10,
    executor: concurrent.futures.Executor | None = None,
) -> ClientLoadResult:
    """Send events sequentially and measure matching socket responses.

    Args:
        url: Backend Socket.IO URL.
        token: Reflex client token.
        payload: Event payload emitted for each operation.
        events: Number of operations.
        event_name: Socket event name used for requests.
        response_name: Socket event name carrying state updates.
        namespace: Reflex Socket.IO namespace.
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
            namespace,
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
    namespace: str,
    timeout: float,
) -> ClientLoadResult:
    """Run a load client with the websocket-client transport.

    Args:
        url: Backend Socket.IO URL.
        token: Reflex client token.
        payload: Event payload emitted for each operation.
        events: Number of operations.
        event_name: Socket event name used for requests.
        response_name: Socket event name carrying state updates.
        namespace: Reflex Socket.IO namespace.
        timeout: Maximum response wait per operation.

    Returns:
        Per-operation latency and error observations.
    """
    client = socketio.SimpleClient(logger=False)
    latencies: list[float] = []
    payload_sizes: list[int] = []
    errors: list[str] = []

    try:
        _connect(client, url, token, namespace, timeout)
        for _ in range(events):
            started = time.perf_counter_ns()
            client.emit(event_name, dict(payload))
            try:
                response = client.receive(timeout=timeout)
                while response and response[0] != response_name:
                    response = client.receive(timeout=timeout)
            except SocketTimeoutError:
                errors.append("response_timeout")
                continue
            latencies.append((time.perf_counter_ns() - started) / 1_000_000)
            payload_sizes.append(_payload_size(response))
    except Exception as err:
        errors.append(f"{type(err).__name__}: {err}")
    finally:
        if client.connected:
            client.disconnect()

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
    namespace: str = "/_event",
    timeout: float = 10,
    executor: concurrent.futures.Executor | None = None,
) -> ReconnectResult:
    """Connect, send one event, and measure connect and first-response time.

    Args:
        url: Backend Socket.IO URL.
        token: Reflex client token.
        payload: Event payload emitted after connecting.
        event_name: Socket event name used for the request.
        response_name: Socket event name carrying state updates.
        namespace: Reflex Socket.IO namespace.
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
            namespace,
            timeout,
        ),
    )


def _run_reconnect_client_sync(
    url: str,
    token: str,
    payload: Mapping[str, Any],
    event_name: str,
    response_name: str,
    namespace: str,
    timeout: float,
) -> ReconnectResult:
    """Run one reconnect client with the websocket-client transport.

    Args:
        url: Backend Socket.IO URL.
        token: Reflex client token.
        payload: Event payload emitted after connecting.
        event_name: Socket event name used for the request.
        response_name: Socket event name carrying state updates.
        namespace: Reflex Socket.IO namespace.
        timeout: Maximum connection and response wait.

    Returns:
        Connect and first-response observations.
    """
    client = socketio.SimpleClient(logger=False)
    connect_ms = 0.0
    first_response_ms = 0.0
    errors: list[str] = []

    try:
        started = time.perf_counter_ns()
        _connect(client, url, token, namespace, timeout)
        connect_ms = (time.perf_counter_ns() - started) / 1_000_000
        started = time.perf_counter_ns()
        client.emit(event_name, dict(payload))
        response = client.receive(timeout=timeout)
        while response and response[0] != response_name:
            response = client.receive(timeout=timeout)
        first_response_ms = (time.perf_counter_ns() - started) / 1_000_000
    except SocketTimeoutError:
        errors.append("response_timeout")
    except Exception as err:
        errors.append(f"{type(err).__name__}: {err}")
    finally:
        if client.connected:
            client.disconnect()

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
