"""Extra probes around the MCP/API-token surface of an rxe app.

* the anonymous token endpoint's per-IP rate limit,
* the ``rest_path`` that ``search_events`` advertises,
* the legacy SSE transport against the streamable-HTTP mount,
* a revoked/garbage bearer.

Usage: python mcp_extra_probe.py <backend_port> <label> <outfile>
"""

import asyncio
import json
import sys

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

BPORT = int(sys.argv[1])
LABEL, OUTFILE = sys.argv[2], sys.argv[3]
BASE = f"http://localhost:{BPORT}"
OUT = {"label": LABEL, "steps": []}


def step(name, **kw):
    """Record and print one step."""
    OUT["steps"].append({"step": name, **kw})
    print(f"[{name}] " + json.dumps(kw, default=str)[:400], flush=True)


async def main():
    """Run the probes."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as hc:
        codes = []
        tok = ""
        for i in range(13):
            r = await hc.post(f"{BASE}/_reflex/auth/token")
            codes.append(r.status_code)
            if r.status_code == 200 and not tok:
                tok = r.json()["access_token"]
        step("anon_token_rate_limit", codes=codes,
             last_body=r.text[:200], retry_after=r.headers.get("retry-after"))

        # the REST path search_events advertises
        for hdrs in ({}, {"Authorization": f"Bearer {tok}"}):
            r = await hc.post(
                f"{BASE}/_reflex/event/authapp___authapp____public_state/bump",
                json={}, headers=hdrs,
            )
            step("rest_event_path", authed=bool(hdrs), status=r.status_code,
                 body=r.text[:200])

        # garbage bearer
        r = await hc.post(
            f"{BASE}/_reflex/mcp/",
            headers={"Accept": "application/json, text/event-stream",
                     "Content-Type": "application/json",
                     "Authorization": "Bearer not-a-real-token"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                             "clientInfo": {"name": "x", "version": "1"}}},
        )
        step("garbage_bearer", status=r.status_code, body=r.text[:200])

    # legacy SSE transport
    try:
        async with asyncio.timeout(20):
            async with sse_client(f"{BASE}/_reflex/mcp",
                                  headers={"Authorization": f"Bearer {tok}"}) as (r, w):
                async with ClientSession(r, w) as s:
                    init = await s.initialize()
                    step("sse_transport", ok=True, server=init.serverInfo.name)
    except Exception as e:  # noqa: BLE001
        step("sse_transport", ok=False, error=f"{type(e).__name__}: {e}"[:250])

    # streamable-http with the same token still fine (control)
    try:
        async with streamablehttp_client(
            f"{BASE}/_reflex/mcp", headers={"Authorization": f"Bearer {tok}"},
            timeout=30,
        ) as (r, w, _):
            async with ClientSession(r, w) as s:
                init = await s.initialize()
                step("streamable_control", ok=True, server=init.serverInfo.name)
    except Exception as e:  # noqa: BLE001
        step("streamable_control", ok=False, error=f"{type(e).__name__}: {e}"[:250])


asyncio.run(main())
with open(OUTFILE, "w") as fh:
    json.dump(OUT, fh, indent=1)
