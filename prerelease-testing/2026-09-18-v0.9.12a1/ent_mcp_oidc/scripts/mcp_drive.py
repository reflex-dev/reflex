"""Drive the reflex-enterprise MCP endpoint end-to-end as an agent would.

Usage: python mcp_drive.py <backend_port>
"""

import asyncio
import json
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

PORT = int(sys.argv[1])
BASE = f"http://localhost:{PORT}"


def show(title, obj, limit=1200):
    """Print a labelled, truncated blob."""
    s = obj if isinstance(obj, str) else json.dumps(obj, default=str, indent=1)
    print(f"\n--- {title} ---\n{s[:limit]}")


async def main():
    """Run the MCP drive."""
    # 1. anonymous token
    async with httpx.AsyncClient(follow_redirects=True) as hc:
        r = await hc.post(f"{BASE}/_reflex/auth/token")
        print("token endpoint:", r.status_code, r.text[:300])
        tok = r.json()["access_token"]

        # unauthenticated MCP must be rejected
        r2 = await hc.post(
            f"{BASE}/_reflex/mcp",
            headers={"Accept": "application/json, text/event-stream",
                     "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-06-18",
                             "capabilities": {}, "clientInfo": {"name": "x", "version": "1"}}},
        )
        print("unauth MCP:", r2.status_code, dict(r2.headers).get("www-authenticate"), r2.text[:200])

        # caller-invented bearer must be rejected
        r3 = await hc.post(
            f"{BASE}/_reflex/mcp",
            headers={"Accept": "application/json, text/event-stream",
                     "Content-Type": "application/json",
                     "Authorization": "Bearer 11111111-1111-1111-1111-111111111111"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-06-18",
                             "capabilities": {}, "clientInfo": {"name": "x", "version": "1"}}},
        )
        print("invented-bearer MCP:", r3.status_code, r3.text[:200])

    hdrs = {"Authorization": f"Bearer {tok}"}
    async with streamablehttp_client(f"{BASE}/_reflex/mcp", headers=hdrs) as (r, w, _):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            show("initialize.instructions", (init.instructions or "")[:1500])
            tools = await s.list_tools()
            show("tools", [t.name for t in tools.tools])
            res = await s.list_resources()
            show("resources", [str(x.uri) for x in res.resources])
            tmpl = await s.list_resource_templates()
            show("resource_templates", [x.uriTemplate for x in tmpl.resourceTemplates])

            out = await s.call_tool("search_events", {"query": "increment"})
            show("search_events(increment)", out.content[0].text if out.content else out)

            out = await s.call_tool("search_events", {"query": "note"})
            show("search_events(note)", out.content[0].text if out.content else out)

            # queue a plain event
            out = await s.call_tool(
                "queue_event",
                {"event_name": "mcpapp___mcpapp____counter_state.increment", "payload": {}},
            )
            show("queue_event increment", out.content[0].text if out.content else out)

            # queue an event with an argument
            out = await s.call_tool(
                "queue_event",
                {"event_name": "mcpapp___mcpapp____counter_state.add", "payload": {"amount": 5}},
            )
            show("queue_event add(5)", out.content[0].text if out.content else out)

            # background event
            out = await s.call_tool(
                "queue_event",
                {"event_name": "mcpapp___mcpapp____counter_state.slow_bump", "payload": {}},
            )
            show("queue_event slow_bump (background)", out.content[0].text if out.content else out)
            await asyncio.sleep(1.0)

            # sibling substate
            out = await s.call_tool(
                "queue_event",
                {"event_name": "mcpapp___mcpapp____profile_state.rename", "payload": {"name": "zoe"}},
            )
            show("queue_event rename(zoe)", out.content[0].text if out.content else out)

            # nested child state
            out = await s.call_tool(
                "queue_event",
                {"event_name": "mcpapp___mcpapp____counter_state.mcpapp___mcpapp____child_state.set_note",
                 "payload": {"note": "hi"}},
            )
            show("queue_event child set_note", out.content[0].text if out.content else out)

            for uri in ("reflex://state", "reflex://event"):
                got = await s.read_resource(uri)
                show(f"read {uri}", got.contents[0].text if got.contents else got, 900)

            for uri in (
                "reflex://state/vars/mcpapp___mcpapp____counter_state",
                "reflex://state/vars/mcpapp___mcpapp____counter_state/doubled",
                "reflex://state/vars/mcpapp___mcpapp____counter_state/uncached_marker",
                "reflex://state/vars/mcpapp___mcpapp____profile_state/greeting",
                "reflex://state/events/mcpapp___mcpapp____child_state",
            ):
                try:
                    got = await s.read_resource(uri)
                    show(f"read {uri}", got.contents[0].text if got.contents else got, 900)
                except Exception as e:  # noqa: BLE001
                    show(f"read {uri} FAILED", f"{type(e).__name__}: {e}", 600)

            # error paths
            try:
                out = await s.call_tool("queue_event", {"event_name": "does.not.exist", "payload": {}})
                show("queue_event bogus", out.content[0].text if out.content else out, 600)
            except Exception as e:  # noqa: BLE001
                show("queue_event bogus raised", f"{type(e).__name__}: {e}", 600)

            try:
                out = await s.call_tool(
                    "queue_event",
                    {"event_name": "mcpapp___mcpapp____counter_state.add", "payload": {"amount": "not-an-int"}},
                )
                show("queue_event bad payload", out.content[0].text if out.content else out, 800)
            except Exception as e:  # noqa: BLE001
                show("queue_event bad payload raised", f"{type(e).__name__}: {e}", 600)

            try:
                got = await s.read_resource("reflex://state/events/totally___bogus___state")
                show("read events of BOGUS state", got.contents[0].text if got.contents else got, 500)
            except Exception as e:  # noqa: BLE001
                show("read events of BOGUS state raised", f"{type(e).__name__}: {e}", 500)

            try:
                got = await s.read_resource("reflex://state/vars/nope___nope")
                show("read bogus state", got.contents[0].text if got.contents else got, 500)
            except Exception as e:  # noqa: BLE001
                show("read bogus state raised", f"{type(e).__name__}: {e}", 500)


asyncio.run(main())
