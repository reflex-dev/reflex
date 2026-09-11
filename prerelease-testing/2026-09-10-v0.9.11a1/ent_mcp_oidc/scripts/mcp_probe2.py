"""Probe MCP resource naming and payload validation."""

import asyncio
import json
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

PORT = int(sys.argv[1])
BASE = f"http://localhost:{PORT}"
ROOT = "reflex___state____state"
CS = f"{ROOT}.mcpapp___mcpapp____counter_state"
CHILD = f"{CS}.mcpapp___mcpapp____child_state"


def show(t, o, n=700):
    """Print labelled blob."""
    s = o if isinstance(o, str) else json.dumps(o, default=str)
    print(f"\n--- {t} ---\n{s[:n]}")


async def rd(s, uri, n=700):
    """Read a resource, reporting errors."""
    try:
        g = await s.read_resource(uri)
        show(f"OK {uri}", g.contents[0].text if g.contents else g, n)
    except Exception as e:  # noqa: BLE001
        show(f"ERR {uri}", f"{type(e).__name__}: {e}", n)


async def main():
    """Run the probe."""
    async with httpx.AsyncClient(follow_redirects=True) as hc:
        tok = (await hc.post(f"{BASE}/_reflex/auth/token")).json()["access_token"]
    async with streamablehttp_client(f"{BASE}/_reflex/mcp", headers={"Authorization": f"Bearer {tok}"}) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            out = await s.call_tool("search_events", {"query": "add"})
            show("search_events(add) schema", out.content[0].text if out.content else out, 700)

            await rd(s, f"reflex://state/vars/{CS}")
            await rd(s, f"reflex://state/vars/{CS}/doubled", 300)
            await rd(s, f"reflex://state/vars/{CS}/uncached_marker", 300)
            await rd(s, f"reflex://state/vars/{CS}/history", 300)
            await rd(s, f"reflex://state/events/{CS}", 700)
            await rd(s, f"reflex://state/events/{CHILD}", 500)
            await rd(s, f"reflex://state/vars/{CS}/no_such_var", 400)
            await rd(s, f"reflex://state/vars/{CS}/_private_attr", 400)
            await rd(s, "reflex://event/mcpapp___mcpapp____counter_state.add", 600)

            # payload validation
            for payload in ({"amount": "not-an-int"}, {"amount": 1.5}, {"amount": None},
                            {"amount": 1, "extra": "x"}, {}):
                try:
                    out = await s.call_tool("queue_event", {
                        "event_name": "mcpapp___mcpapp____counter_state.add", "payload": payload})
                    txt = out.content[0].text if out.content else str(out)
                    show(f"add payload={payload}", txt, 400)
                except Exception as e:  # noqa: BLE001
                    show(f"add payload={payload} raised", f"{type(e).__name__}: {e}", 400)

            await rd(s, f"reflex://state/vars/{CS}/count", 200)

            # can an MCP session reach another session's state? try router/token leakage
            out = await s.call_tool("queue_event", {
                "event_name": "mcpapp___mcpapp____counter_state.set_label",
                "payload": {"value": "via-mcp"}, "query": {"foo": "bar"}})
            show("set_label with query", out.content[0].text if out.content else out, 700)


asyncio.run(main())
