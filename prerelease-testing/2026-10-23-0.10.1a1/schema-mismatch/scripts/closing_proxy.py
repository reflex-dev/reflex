"""A fake backend that completes the Engine.IO websocket handshake and then closes
the connection when the client's socket.io CONNECT packet arrives (what a proxy with
a frame size limit does). Logs every connection with a timestamp.

Usage: closing_proxy.py <port> <logfile>
"""
import asyncio
import sys
import time

from websockets.asyncio.server import serve
from websockets.http11 import Response
from websockets.datastructures import Headers

port, logfile = int(sys.argv[1]), sys.argv[2]
t0 = time.time()
n = 0


def log(msg):
    with open(logfile, "a") as f:
        f.write(f"{time.time() - t0:8.3f} {msg}\n")


async def handler(ws):
    global n
    n += 1
    log(f"ws #{n} open path={ws.request.path}")
    await ws.send('0{"sid":"fake%d","upgrades":[],"pingInterval":25000,"pingTimeout":20000,"maxPayload":1000000}' % n)
    try:
        msg = await ws.recv()
        log(f"ws #{n} got {str(msg)[:80]!r} -> closing transport")
    except Exception as e:
        log(f"ws #{n} recv error {e!r}")
    # close like a proxy that rejects an oversized frame
    await ws.close(1009, "message too big")


def process_request(connection, request):
    # Allow any non-upgrade probe (e.g. polling) to fail fast with 400.
    if request.headers.get("Upgrade", "").lower() != "websocket":
        log(f"http {request.path} -> 400")
        return Response(400, "Bad Request", Headers(), b"no polling here")
    return None


async def main():
    # The reflex client offers its version as a websocket subprotocol; the browser
    # aborts the handshake unless the server echoes one of the offered ones.
    async with serve(
        handler, "127.0.0.1", port, process_request=process_request,
        select_subprotocol=lambda conn, offered: offered[0] if offered else None,
    ):
        log(f"listening on {port}")
        await asyncio.Future()


asyncio.run(main())
