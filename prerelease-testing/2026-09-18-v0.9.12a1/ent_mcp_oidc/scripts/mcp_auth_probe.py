"""Probe MCPPlugin + AuthPlugin together: OAuth metadata and anon-session scoping.

Usage: python mcp_auth_probe.py <backend_port>
"""

import asyncio
import json
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

PORT = int(sys.argv[1])
BASE = f"http://localhost:{PORT}"
ROOT = "reflex___state____state"
PS = f"{ROOT}.authapp___authapp____public_state"


def show(t, o, n=800):
    """Print labelled blob."""
    s = o if isinstance(o, str) else json.dumps(o, default=str)
    print(f"\n--- {t} ---\n{s[:n]}")


async def main():
    """Run the probe."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as hc:
        for path in (
            "/.well-known/oauth-protected-resource/_reflex/mcp",
            "/.well-known/oauth-authorization-server",
            "/.well-known/openid-configuration",
        ):
            r = await hc.get(BASE + path)
            show(f"GET {path}", f"{r.status_code} {r.text[:500]}")

        r = await hc.post(f"{BASE}/_reflex/mcp", headers={
            "Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                             "clientInfo": {"name": "x", "version": "1"}}})
        show("unauth MCP", f"{r.status_code} WWW-Authenticate={r.headers.get('www-authenticate')} {r.text[:200]}")

        # dynamic client registration (RFC 7591)
        r = await hc.post(f"{BASE}/register", json={
            "client_name": "probe", "redirect_uris": ["http://localhost:1/cb"],
            "grant_types": ["authorization_code"], "response_types": ["code"]})
        show("POST /register", f"{r.status_code} {r.text[:300]}")

        r = await hc.post(f"{BASE}/_reflex/auth/token")
        show("anon token", f"{r.status_code} {r.text[:200]}")
        if r.status_code != 200:
            return
        tok = r.json()["access_token"]

    async with streamablehttp_client(f"{BASE}/_reflex/mcp", headers={"Authorization": f"Bearer {tok}"}) as (rr, w, _):
        async with ClientSession(rr, w) as s:
            await s.initialize()
            out = await s.call_tool("search_events", {"query": ""})
            names = []
            try:
                names = [x["name"] for x in json.loads(out.content[0].text)["results"]]
            except Exception:  # noqa: BLE001
                pass
            show("events visible to anon MCP session", names)

            for ev, payload in (
                ("authapp___authapp____public_state.bump", {}),
                ("authapp___authapp____public_state.poison_field", {}),
                ("authapp___authapp____public_state.set_secret", {"value": "mcp-set"}),
                ("authapp___authapp____public_state.slow_secret", {}),
            ):
                try:
                    o = await s.call_tool("queue_event", {"event_name": ev, "payload": payload})
                    show(f"queue {ev}", (o.content[0].text if o.content else str(o)), 500)
                except Exception as e:  # noqa: BLE001
                    show(f"queue {ev} raised", f"{type(e).__name__}: {e}", 400)

            for uri in (f"reflex://state/vars/{PS}",
                        f"reflex://state/vars/{PS}/hits",
                        f"reflex://state/vars/{PS}/secret_note",
                        f"reflex://state/vars/{PS}/secret_label",
                        f"reflex://state/vars/{PS}/shared_label",
                        f"reflex://state/vars/{PS}/note_echo",
                        f"reflex://state/vars/{ROOT}.reflex_enterprise___auth___user_state____auth_user_state"):
                try:
                    g = await s.read_resource(uri)
                    show(f"read {uri.split('/')[-1]}", g.contents[0].text if g.contents else g, 500)
                except Exception as e:  # noqa: BLE001
                    show(f"read {uri.split('/')[-1]} ERR", f"{type(e).__name__}: {e}", 300)


asyncio.run(main())
