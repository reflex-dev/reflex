"""Read the router vars over MCP and check the session identifiers are blanked."""
import asyncio, json, sys
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
PORT = int(sys.argv[1]); BASE = f"http://localhost:{PORT}"
ROOT = "reflex___state____state"

async def main():
    async with httpx.AsyncClient(trust_env=False) as c:
        tok = (await c.post(f"{BASE}/_reflex/auth/token")).json()["access_token"]
    H = {"Authorization": f"Bearer {tok}"}
    async with streamablehttp_client(f"{BASE}/_reflex/mcp", headers=H) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            # make the session real so router data is populated
            await s.call_tool("queue_event", {"event_name": "mcpapp___mcpapp____counter_state.increment", "payload": {}})
            for var in ("rx_router_session", "rx_router_headers", "rx_router_page"):
                try:
                    res = await s.read_resource(f"reflex://state/vars/{ROOT}/{var}")
                    print(f"--- {var} ---"); print(res.contents[0].text[:600])
                except Exception as e:
                    print(f"--- {var} FAILED --- {type(e).__name__}: {e}")
            try:
                res = await s.read_resource(f"reflex://state/vars/{ROOT}")
                txt = res.contents[0].text
                print("--- all root vars ---"); print(txt[:1500])
                print("TOKEN-IN-BODY:", tok in txt)
            except Exception as e:
                print("all root vars FAILED", e)
asyncio.run(main())
