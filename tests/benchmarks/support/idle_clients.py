"""Hold idle Socket.IO sessions from a separate process.

Memory-per-session benchmarks run the backend inside the test process, so
client-side allocations would pollute resident-memory measurements. This
module connects a number of sessions, primes each with one event so the
backend materializes its state, reports readiness on stdout, and holds the
connections until stdin closes.
"""

from __future__ import annotations

import json
import sys

import socketio

from tests.benchmarks.support.socket_client import _connect


def main() -> int:
    """Connect, prime, and hold the requested sessions.

    Returns:
        Process exit code.
    """
    url, token_prefix, count, payload_json = sys.argv[1:5]
    payload = json.loads(payload_json)
    clients: list[socketio.SimpleClient] = []
    try:
        for index in range(int(count)):
            client = socketio.SimpleClient(logger=False)
            _connect(client, url, f"{token_prefix}-{index}", "/_event", timeout=10)
            client.emit("event", payload)
            response = client.receive(timeout=10)
            while response and response[0] != "event":
                response = client.receive(timeout=10)
            clients.append(client)
        print("ready", flush=True)
        sys.stdin.read()
    finally:
        for client in clients:
            if client.connected:
                client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
