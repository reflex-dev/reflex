"""TCP proxy adding a fixed one-way delay in both directions. Usage: latency_proxy.py LISTEN_PORT TARGET_PORT DELAY_MS"""
import asyncio
import sys

LP, TP, DELAY = int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]) / 1000


async def pump(reader, writer):
    q: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    async def sender():
        while True:
            due, data = await q.get()
            if data is None:
                break
            wait = due - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            writer.write(data)
            await writer.drain()
        try:
            writer.close()
        except Exception:
            pass

    t = asyncio.create_task(sender())
    try:
        while data := await reader.read(65536):
            q.put_nowait((loop.time() + DELAY, data))
    except Exception:
        pass
    q.put_nowait((loop.time() + DELAY, None))
    await t


async def handle(cr, cw):
    try:
        sr, sw = await asyncio.open_connection("127.0.0.1", TP)
    except Exception:
        cw.close()
        return
    await asyncio.gather(pump(cr, sw), pump(sr, cw), return_exceptions=True)


async def main():
    server = await asyncio.start_server(handle, "127.0.0.1", LP)
    print(f"proxy {LP} -> {TP} delay {DELAY*1000:.0f}ms each way", flush=True)
    async with server:
        await server.serve_forever()


asyncio.run(main())
