"""Hold idle event websocket sessions from a separate process.

Memory-per-session benchmarks run the backend inside the test process, so
client-side allocations would pollute resident-memory measurements. This
module connects a number of sessions, primes each with one event so the
backend materializes its state, reports readiness on stdout, and holds the
connections, answering the server's pings, until stdin closes.
"""

from __future__ import annotations

import contextlib
import json
import sys
import threading

from websockets.exceptions import ConnectionClosed

from tests.benchmarks.support.socket_client import EventClient, _connect

# Seconds between checks for pings while the sessions are held.
_KEEPALIVE_INTERVAL = 1.0


def _keep_alive(clients: list[EventClient], stop: threading.Event) -> None:
    """Answer the server's pings until stopped.

    Args:
        clients: The held sessions.
        stop: Set when the sessions are released.
    """
    while not stop.wait(_KEEPALIVE_INTERVAL):
        for client in clients:
            # A session the server ended stays ended; keep the others alive.
            with contextlib.suppress(ConnectionClosed, ConnectionError):
                client.poll()


def main() -> int:
    """Connect, prime, and hold the requested sessions.

    Returns:
        Process exit code.
    """
    url, token_prefix, count, payload_json = sys.argv[1:5]
    payload = json.loads(payload_json)
    clients: list[EventClient] = []
    try:
        for index in range(int(count)):
            client = _connect(url, f"{token_prefix}-{index}", timeout=10)
            clients.append(client)
            client.emit("event", payload)
            client.receive(10, "event")
        print("ready", flush=True)
        stop = threading.Event()
        keeper = threading.Thread(target=_keep_alive, args=(clients, stop))
        keeper.start()
        try:
            sys.stdin.read()
        finally:
            stop.set()
            keeper.join()
    finally:
        for client in clients:
            client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
