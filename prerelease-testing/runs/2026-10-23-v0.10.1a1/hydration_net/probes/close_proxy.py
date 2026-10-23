"""Forwarding proxy that closes the connection when a client->server chunk exceeds a size (a proxy frame limit).

Usage: close_proxy.py LISTEN_PORT TARGET_PORT MAX_CLIENT_CHUNK_BYTES
Everything is passed through byte for byte; a websocket upgrade is detected only for stats. When one client->server
read exceeds the limit, both sides are closed (what a proxy with a frame/message limit does). Prints stats every 5 s.
"""

import asyncio
import os
import sys
import time

import playwright  # noqa: F401  venv guard

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in playwright.__file__, playwright.__file__

LISTEN, TARGET, LIMIT = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
STATS = {"conns": 0, "closed_over_limit": 0, "upgrades": 0, "conn_times": []}


async def pipe(r, w, limit=None, other=None):
    try:
        while chunk := await r.read(262144):
            if limit is not None and len(chunk) > limit:
                STATS["closed_over_limit"] += 1
                print(f"{time.time():.3f} chunk {len(chunk)} > {limit}: closing", flush=True)
                break
            if limit is not None and b"Upgrade: websocket" in chunk:
                STATS["upgrades"] += 1
            w.write(chunk)
            await w.drain()
    except Exception:  # noqa: BLE001
        pass
    finally:
        for s in (w, other):
            try:
                s.close()
            except Exception:  # noqa: BLE001
                pass


async def handle(cr, cw):
    STATS["conns"] += 1
    STATS["conn_times"].append(round(time.time(), 3))
    try:
        sr, sw = await asyncio.open_connection("127.0.0.1", TARGET)
    except Exception:  # noqa: BLE001
        cw.close()
        return
    await asyncio.gather(pipe(cr, sw, LIMIT, cw), pipe(sr, cw, None, sw))


async def main():
    srv = await asyncio.start_server(handle, "127.0.0.1", LISTEN)
    print(f"close_proxy {LISTEN} -> {TARGET} limit={LIMIT}", flush=True)
    async with srv:
        while True:
            await asyncio.sleep(5)
            print("stats", {k: v for k, v in STATS.items() if k != "conn_times"}, "last_conns", STATS["conn_times"][-12:], flush=True)


asyncio.run(main())
