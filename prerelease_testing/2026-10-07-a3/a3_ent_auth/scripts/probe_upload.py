"""Probe the MCP upload endpoint: proper POST, missing handler header, ticket reuse, wrong handler."""
import asyncio, json, subprocess, sys
import httpx
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import save
from mcp_common import AGENT, call, mcp_session, read

BASE = sys.argv[1].rstrip("/"); LABEL = sys.argv[2]
ev = {}

def curl(args):
    p = subprocess.run(["curl", "--noproxy", "*", "-sS", "-m", "30", "-o", "/dev/stdout", "-w", "\nHTTP=%{http_code}"] + args, capture_output=True, text=True)
    return (p.stdout[-600:] + " | stderr=" + p.stderr[-200:]).strip()

async def directions(s):
    names = (await call(s, "search_events", {"query": "upload"}))["value"]["results"]
    up = await call(s, "queue_event", {"event_name": next(e["name"] for e in names if e["name"].endswith(".handle_upload")), "payload": {}})
    return up["value"]["upload"]

async def main():
    async with httpx.AsyncClient() as c:
        tok = (await c.post(BASE + "/_reflex/auth/token")).json()["access_token"]
    open("/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/a3_ent_auth/logs/a.txt", "w").write("hello")
    f = "/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/a3_ent_auth/logs/a.txt"
    async with mcp_session(BASE + "/_reflex/mcp/", tok) as s:
        spec = await directions(s)
        hdr = spec["headers"]["Reflex-Event-Handler"]
        ev["post_ok"] = curl(["-X", "POST", spec["url"], "-H", f"Reflex-Event-Handler: {hdr}", "-F", f"files=@{f}"])
        ev["uploaded_after_1"] = (await read(s, f"reflex://state/vars/{AGENT}/uploaded"))["value"]
        ev["post_same_ticket_again"] = curl(["-X", "POST", spec["url"], "-H", f"Reflex-Event-Handler: {hdr}", "-F", f"files=@{f}"])
        spec2 = await directions(s)
        ev["post_missing_handler_header"] = curl(["-X", "POST", spec2["url"], "-F", f"files=@{f}"])
        spec3 = await directions(s)
        ev["post_other_handler_header"] = curl(["-X", "POST", spec3["url"], "-H", "Reflex-Event-Handler: reflex___state____state.entauth___entauth____agent_state.bump", "-F", f"files=@{f}"])
        ev["post_bad_ticket"] = curl(["-X", "POST", BASE + "/_reflex/mcp/upload?ticket=bogus", "-H", f"Reflex-Event-Handler: {hdr}", "-F", f"files=@{f}"])
        ev["post_bearer_instead_of_ticket"] = curl(["-X", "POST", BASE + "/_reflex/mcp/upload", "-H", f"Authorization: Bearer {tok}", "-H", f"Reflex-Event-Handler: {hdr}", "-F", f"files=@{f}"])
        ev["uploaded_final"] = (await read(s, f"reflex://state/vars/{AGENT}/uploaded"))["value"]

asyncio.run(main())
save(f"mcp-upload-{LABEL}.json", ev)
for k, v in ev.items():
    print(k, "=>", json.dumps(v)[:700])
