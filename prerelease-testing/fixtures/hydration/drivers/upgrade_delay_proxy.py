"""TCP proxy that delays ONLY websocket upgrade requests for /_event by DELAY_MS before connecting upstream.

Everything else (HTML, JS, /ping, ...) passes through immediately. Models a backend (or LB/proxy) that is slow to
accept websocket connections while the static frontend is served fast.
Usage: upgrade_delay_proxy.py LISTEN_PORT TARGET_PORT DELAY_MS [PIDFILE]
"""
import asyncio
import os
import sys
import time

LP, TP, DELAY = int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]) / 1000
if len(sys.argv) > 4:
    with open(sys.argv[4], "w") as f:
        f.write(str(os.getpid()))


async def pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except Exception:  # noqa: BLE001
        pass
    finally:
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass


async def handle(cr, cw):
    try:
        first = await cr.read(65536)
    except Exception:  # noqa: BLE001
        cw.close()
        return
    if not first:
        cw.close()
        return
    line = first.split(b"\r\n", 1)[0]
    is_ws = line.startswith(b"GET /_event") and b"upgrade: websocket" in first.lower()
    if is_ws and DELAY > 0:
        print(f"{time.time():.3f} delaying ws upgrade {DELAY*1000:.0f}ms: {line[:80]!r}", flush=True)
        await asyncio.sleep(DELAY)
    try:
        sr, sw = await asyncio.open_connection("127.0.0.1", TP)
    except Exception:  # noqa: BLE001
        cw.close()
        return
    sw.write(first)
    await sw.drain()
    await asyncio.gather(pipe(cr, sw), pipe(sr, cw), return_exceptions=True)


async def main():
    server = await asyncio.start_server(handle, "127.0.0.1", LP)
    print(f"upgrade-delay proxy {LP} -> {TP}, /_event upgrade delay {DELAY*1000:.0f}ms", flush=True)
    async with server:
        await server.serve_forever()


asyncio.run(main())
