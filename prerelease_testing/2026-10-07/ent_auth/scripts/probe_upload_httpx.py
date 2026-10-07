"""httpx vs the MCP upload endpoint's early 403: same client reused after a 200 upload."""
import asyncio, sys
import httpx
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from mcp_common import call, mcp_session

BASE = sys.argv[1].rstrip("/")

async def directions(s):
    names = (await call(s, "search_events", {"query": "upload"}))["value"]["results"]
    up = await call(s, "queue_event", {"event_name": next(e["name"] for e in names if e["name"].endswith(".handle_upload")), "payload": {}})
    return up["value"]["upload"]

async def main():
    async with httpx.AsyncClient() as c:
        tok = (await c.post(BASE + "/_reflex/auth/token")).json()["access_token"]
    async with mcp_session(BASE + "/_reflex/mcp/", tok) as s:
        for variant in ("fresh-client", "reused-client"):
            spec_ok = await directions(s)
            spec_bad = await directions(s)
            async with httpx.AsyncClient(timeout=30) as client:
                if variant == "reused-client":
                    r = await client.post(spec_ok["url"], files=[("files", ("a.txt", b"hello", "text/plain"))], headers=spec_ok["headers"])
                    print(variant, "first(ok) ->", r.status_code)
                try:
                    r = await client.post(spec_bad["url"], files=[("files", ("d.txt", b"nohdr", "text/plain"))])
                    print(variant, "missing header ->", r.status_code, r.text[:80])
                except Exception as exc:
                    print(variant, "missing header -> EXC", type(exc).__name__, exc)

asyncio.run(main())
