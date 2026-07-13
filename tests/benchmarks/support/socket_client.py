"""Protocol-aware Socket.IO client used by scheduled load tests."""

from __future__ import annotations

import asyncio
import concurrent.futures
import dataclasses
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

    Returns:
        Per-operation latency and error observations.
    """
    return await asyncio.to_thread(
        _run_socket_client_sync,
        url,
        token,
        payload,
        events,
        event_name,
        response_name,
        namespace,
        timeout,
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
    errors: list[str] = []

    try:
        separator = "&" if "?" in url else "?"
        client.connect(
            f"{url}{separator}token={quote(token)}",
            transports=["websocket"],
            socketio_path="_event",
            headers={"Origin": url},
            namespace=namespace,
            wait_timeout=max(1, int(timeout)),
        )
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
    except Exception as err:
        errors.append(f"{type(err).__name__}: {err}")
    finally:
        if client.connected:
            client.disconnect()

    return ClientLoadResult(token, tuple(latencies), tuple(errors))


async def run_clients(
    clients: int,
    factory: Callable[[int], Any],
) -> list[Any]:
    """Run a parameterized set of clients concurrently.

    Args:
        clients: Number of clients.
        factory: Callable returning an awaitable for a client index.

    Returns:
        Client results in index order.
    """
    loop = asyncio.get_running_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, clients))
    loop.set_default_executor(executor)
    try:
        return list(await asyncio.gather(*(factory(index) for index in range(clients))))
    finally:
        executor.shutdown(wait=True)
