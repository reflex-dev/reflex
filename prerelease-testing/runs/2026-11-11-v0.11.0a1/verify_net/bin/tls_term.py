"""Minimal TLS terminator (TCP passthrough after TLS, like stunnel / an L4 TLS load balancer):
it adds no X-Forwarded-* header and keeps Host. usage: tls_term.py <listen_port> <upstream_port> <cert> <key>"""
import asyncio, ssl, sys

LP, UP, CERT, KEY = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4]

async def pipe(r, w):
    try:
        while data := await r.read(65536):
            w.write(data); await w.drain()
    except Exception:
        pass
    finally:
        w.close()

async def handle(cr, cw):
    ur, uw = await asyncio.open_connection("127.0.0.1", UP)
    await asyncio.gather(pipe(cr, uw), pipe(ur, cw))

async def main():
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH); ctx.load_cert_chain(CERT, KEY)
    srv = await asyncio.start_server(handle, "127.0.0.1", LP, ssl=ctx)
    print("tls_term listening", LP, "->", UP, flush=True)
    async with srv: await srv.serve_forever()

asyncio.run(main())
