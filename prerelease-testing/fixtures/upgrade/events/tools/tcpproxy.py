"""Pausable TCP proxy used to really drop the browser's websocket.

Usage: tcpproxy.py LISTEN_PORT TARGET_PORT STATE_FILE
  STATE_FILE contains "up" or "down". While "down", every open connection is
  closed and new connections are accepted and immediately closed, so the
  socket.io client sees a transport close and its reconnect attempts fail fast.
  Every state change and connection event is logged with a timestamp to stdout.
"""

import asyncio
import sys
import time
from pathlib import Path

LISTEN, TARGET, STATE = int(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
conns: set[asyncio.StreamWriter] = set()
state = {"down": False}


def log(msg: str) -> None:
    print(f"PROXY {time.time():.3f} {msg}", flush=True)


async def pump(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def handle(cr, cw):
    peer = cw.get_extra_info("peername")
    if state["down"]:
        log(f"refuse {peer}")
        cw.transport.abort()
        return
    try:
        tr, tw = await asyncio.open_connection("127.0.0.1", TARGET)
    except Exception as e:
        log(f"target connect failed {e!r}")
        cw.transport.abort()
        return
    conns.add(cw)
    conns.add(tw)
    log(f"open {peer} (active={len(conns) // 2})")
    await asyncio.gather(pump(cr, tw), pump(tr, cw))
    conns.discard(cw)
    conns.discard(tw)


async def watch_state():
    last = None
    while True:
        try:
            cur = STATE.read_text().strip()
        except FileNotFoundError:
            cur = "up"
        if cur != last:
            state["down"] = cur == "down"
            log(f"state={cur}")
            if state["down"]:
                n = len(conns)
                for w in list(conns):
                    w.transport.abort()
                conns.clear()
                log(f"aborted {n // 2} connection pairs")
            last = cur
        await asyncio.sleep(0.05)


async def main():
    server = await asyncio.start_server(handle, ["127.0.0.1", "::1"], LISTEN)
    log(f"listening {LISTEN} -> {TARGET}")
    async with server:
        await asyncio.gather(server.serve_forever(), watch_state())


asyncio.run(main())
