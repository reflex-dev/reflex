"""Focused follow-ups: (a) truncation of an over-500-char message, (b) the
no-arg client_error TypeError, (c) no-arg flood bypassing the rate limiter.

Usage: python abuse2.py <backend_url> <namespace_path>
"""

import asyncio
import sys

import socketio


async def run(backend_url: str, ns: str):
    def new_client():
        return socketio.AsyncClient(reconnection=False)

    # (a) Truncation: 600-char message on a fresh, healthy connection.
    c = new_client()
    await c.connect(
        f"{backend_url}?token=trunc-token",
        socketio_path="_event",
        namespaces=[ns],
        transports=["websocket"],
        wait_timeout=10,
    )
    await asyncio.sleep(0.3)
    await c.emit(
        "client_error",
        {"error_type": "state_update_processing_error", "message": "C" * 600},
        namespace=ns,
    )
    await asyncio.sleep(0.4)
    print("TRUNC sent 600-char message (expect '... (truncated)' in log)")
    await c.disconnect()

    # (b) No-arg emit: client_error with NO data payload. python-socketio calls
    # the handler with only sid -> TypeError (missing 'data'). Watch the log.
    c2 = new_client()
    await c2.connect(
        f"{backend_url}?token=noarg-token",
        socketio_path="_event",
        namespaces=[ns],
        transports=["websocket"],
        wait_timeout=10,
    )
    await asyncio.sleep(0.3)
    # Emit the raw event with zero data arguments.
    await c2.emit("client_error", namespace=ns)
    await asyncio.sleep(0.4)
    print(f"NOARG sent (connected={c2.connected})")

    # (c) No-arg FLOOD: 30 no-arg client_error events from ONE sid. Each raises a
    # TypeError BEFORE the per-sid/per-window rate limiter runs, so all 30 should
    # produce tracebacks -- the rate limiting does not bound this path.
    for i in range(30):
        await c2.emit("client_error", namespace=ns)
    await asyncio.sleep(0.6)
    print(f"NOARG_FLOOD sent 30 no-arg events (connected={c2.connected})")
    await c2.disconnect()
    print("DONE")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "/_event"))
