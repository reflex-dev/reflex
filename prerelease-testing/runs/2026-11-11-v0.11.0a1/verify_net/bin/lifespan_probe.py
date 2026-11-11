"""Drive the ASGI lifespan of rx.App()() in-process, then GET /api/greeting.
usage: <venv>/bin/python -I lifespan_probe.py <venv> <app_dir>   (env VN_TX selects the transformer)"""
import asyncio, os, sys
venv, app_dir = sys.argv[1], sys.argv[2]
os.chdir(app_dir); sys.path.insert(0, app_dir)
import reflex as rx
assert f"/envs/{venv}/" in rx.__file__, rx.__file__
import httpx
from vapp import vapp as mod

asgi = mod.app()
print("type(app()) =", type(asgi).__module__, type(asgi).__qualname__)
print("has add_middleware/routes/mount:", [hasattr(asgi, a) for a in ("add_middleware", "routes", "mount")])

async def main():
    rq: asyncio.Queue = asyncio.Queue(); sq: asyncio.Queue = asyncio.Queue()
    scope = {"type": "lifespan", "asgi": {"version": "3.0", "spec_version": "2.0"}, "state": {}}
    task = asyncio.create_task(asgi(scope, rq.get, sq.put))
    await rq.put({"type": "lifespan.startup"})
    print("startup ->", (await asyncio.wait_for(sq.get(), 30))["type"])
    print("lifespan log after startup:", getattr(mod, "LIFESPAN_LOG", None))
    # Requests share the server's lifespan state, as uvicorn passes scope["state"] copies.
    async def app_with_state(s, r, se):
        if s["type"] == "http":
            s = {**s, "state": dict(scope["state"])}
        await asgi(s, r, se)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_with_state), base_url="http://t") as c:
        r = await c.get("/api/greeting"); print("GET /api/greeting", r.status_code, r.text)
        r = await c.get("/ping"); print("GET /ping", r.status_code, r.text)
    await rq.put({"type": "lifespan.shutdown"})
    print("shutdown ->", (await asyncio.wait_for(sq.get(), 30))["type"])
    print("lifespan log at end:", getattr(mod, "LIFESPAN_LOG", None))
    await task

asyncio.run(main())
