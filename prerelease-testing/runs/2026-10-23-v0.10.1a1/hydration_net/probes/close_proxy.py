"""Forwarding proxy with a websocket MESSAGE size limit: closes the connection when a client->server frame's payload
exceeds the limit (what a proxy / load balancer with a frame or message limit does, e.g. nginx `client_max_body_size`
style limits on websocket frames).

Usage: close_proxy.py LISTEN_PORT TARGET_PORT MAX_CLIENT_FRAME_BYTES
HTTP traffic passes through untouched; on a connection whose first request is a websocket upgrade, every
client->server frame header is parsed (RFC 6455) and a payload longer than the limit closes both sides at once.
Prints one line per close and stats every 5 s.
"""

import asyncio
import os
import struct
import sys
import time

import playwright  # noqa: F401  venv guard

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in playwright.__file__, playwright.__file__

LISTEN, TARGET, LIMIT = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
STATS = {"conns": 0, "closed_over_limit": 0, "upgrades": 0, "frames": 0, "conn_times": []}


def close_all(*ws):
    for s in ws:
        try:
            s.close()
        except Exception:  # noqa: BLE001
            pass


async def s2c(r, w, other):
    try:
        while chunk := await r.read(262144):
            w.write(chunk)
            await w.drain()
    except Exception:  # noqa: BLE001
        pass
    finally:
        close_all(w, other)


async def c2s(r, w, other):
    try:
        head = await r.readuntil(b"\r\n\r\n")
        w.write(head)
        await w.drain()
        if b"upgrade: websocket" not in head.lower():
            while chunk := await r.read(262144):
                w.write(chunk)
                await w.drain()
            return
        STATS["upgrades"] += 1
        while True:
            hdr = await r.readexactly(2)
            n = hdr[1] & 0x7F
            ext = b""
            if n == 126:
                ext = await r.readexactly(2)
                n = struct.unpack(">H", ext)[0]
            elif n == 127:
                ext = await r.readexactly(8)
                n = struct.unpack(">Q", ext)[0]
            mask = await r.readexactly(4) if hdr[1] & 0x80 else b""
            STATS["frames"] += 1
            if n > LIMIT:
                STATS["closed_over_limit"] += 1
                print(f"{time.time():.3f} client frame payload {n} > {LIMIT}: closing", flush=True)
                return
            w.write(hdr + ext + mask)
            left = n
            while left:
                chunk = await r.read(min(left, 262144))
                if not chunk:
                    return
                w.write(chunk)
                left -= len(chunk)
            await w.drain()
    except Exception:  # noqa: BLE001
        pass
    finally:
        close_all(w, other)


async def handle(cr, cw):
    STATS["conns"] += 1
    STATS["conn_times"].append(round(time.time(), 3))
    try:
        sr, sw = await asyncio.open_connection("127.0.0.1", TARGET)
    except Exception:  # noqa: BLE001
        cw.close()
        return
    await asyncio.gather(c2s(cr, sw, cw), s2c(sr, cw, sw))


async def main():
    srv = await asyncio.start_server(handle, "127.0.0.1", LISTEN)
    print(f"close_proxy {LISTEN} -> {TARGET} limit={LIMIT}", flush=True)
    async with srv:
        while True:
            await asyncio.sleep(5)
            print("stats", {k: v for k, v in STATS.items() if k != "conn_times"}, "last_conns", STATS["conn_times"][-12:], flush=True)


asyncio.run(main())
