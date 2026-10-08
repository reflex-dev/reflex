"""Anonymous MCP on Redis: bg events, yields, upload, parallel hammering, auth/scope denial, rate limits.

Usage: check_mcp_anon.py <backend_base> <label> [--rate]
"""

import asyncio
import json
import sys
import time

import httpx

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import save  # noqa: E402
from mcp_common import AGENT, call, mcp_session, read  # noqa: E402

BASE = sys.argv[1].rstrip("/")
LABEL = sys.argv[2]
RATE = "--rate" in sys.argv
MCP = BASE + "/_reflex/mcp/"
ev = {}


def ename(results, handler):
    return next(e["name"] for e in results if e["name"].endswith("." + handler))


async def grant(client):
    r = await client.post(BASE + "/_reflex/auth/token")
    return r


async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        # endpoint shape probes (no bearer) -- slash and no-slash
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
        for path in ("/_reflex/mcp", "/_reflex/mcp/"):
            r = await client.post(BASE + path, json=init, headers={"Accept": "application/json, text/event-stream"})
            ev[f"probe_nobearer_{path}"] = {"status": r.status_code, "www": r.headers.get("www-authenticate"), "body": r.text[:200]}
        r = await grant(client)
        ev["grant"] = {"status": r.status_code, "keys": sorted(r.json())}
        tok = r.json()["access_token"]
        r = await client.post(BASE + "/_reflex/mcp", json=init, headers={"Accept": "application/json, text/event-stream", "Authorization": "Bearer " + tok})
        ev["probe_bearer_noslash"] = {"status": r.status_code, "body": r.text[:200]}
        tok2 = (await grant(client)).json()["access_token"]

    async with mcp_session(MCP, tok) as s:
        tools = await s.list_tools()
        ev["tools"] = [t.name for t in tools.tools]
        search = (await call(s, "search_events", {"query": ""}))["value"]
        names = search["results"]
        ev["n_handlers"] = search["total_available"]
        bump = ename(names, "bump")
        t0 = time.time()
        ev["bump"] = await call(s, "queue_event", {"event_name": bump, "payload": {"amount": 4}})
        ev["count_after_bump"] = await read(s, f"reflex://state/vars/{AGENT}/count")
        ev["doubled"] = await read(s, f"reflex://state/vars/{AGENT}/doubled")
        # handler that yields several times
        ev["multi_yield"] = await call(s, "queue_event", {"event_name": ename(names, "multi_yield"), "payload": {"n": 4}})
        ev["yields_var"] = await read(s, f"reflex://state/vars/{AGENT}/yields")
        # background event
        t_bg = time.time()
        ev["start_bg"] = await call(s, "queue_event", {"event_name": ename(names, "start_bg"), "payload": {"steps": 5}})
        ev["start_bg_latency_s"] = round(time.time() - t_bg, 2)
        polls = []
        pending_all = []
        for _ in range(30):
            await asyncio.sleep(0.5)
            pend = await call(s, "get_pending_updates")
            if not pend["is_error"]:
                pending_all.extend(pend["value"].get("updates", []))
            prog = await read(s, f"reflex://state/vars/{AGENT}/bg_progress")
            done = await read(s, f"reflex://state/vars/{AGENT}/bg_done")
            polls.append([round(time.time() - t_bg, 1), prog["value"], done["value"]])
            if isinstance(done["value"], dict) and done["value"].get("value") is True:
                break
        ev["bg_polls"] = polls
        ev["bg_pending_updates"] = pending_all
        ev["bg_pid"] = await read(s, f"reflex://state/vars/{AGENT}/bg_pid")
        # upload-backed handler
        up = await call(s, "queue_event", {"event_name": ename(names, "handle_upload"), "payload": {}})
        ev["upload_directions_status"] = up["value"].get("status") if isinstance(up["value"], dict) else up
        spec = up["value"].get("upload") if isinstance(up["value"], dict) else None
        if spec:
            async with httpx.AsyncClient(timeout=30) as client:
                url = spec["url"]
                field = spec["form_fields"][0]["name"]
                r = await client.post(url, files=[(field, ("a.txt", b"hello", "text/plain")), (field, ("b.bin", b"\x00" * 1234, "application/octet-stream"))], headers=spec.get("headers") or {})
                ev["upload_post"] = {"status": r.status_code, "body": r.text[:500]}
                try:
                    r_nohdr = await client.post(url, files=[(field, ("d.txt", b"nohdr", "text/plain"))])
                    ev["upload_ticket_reuse_without_header"] = {"status": r_nohdr.status_code, "body": r_nohdr.text[:300]}
                except Exception as exc:
                    ev["upload_ticket_reuse_without_header"] = {"exception": f"{type(exc).__name__}: {exc}"}
                try:
                    r2 = await client.post(url, files=[(field, ("c.txt", b"again", "text/plain"))], headers=spec.get("headers") or {})
                    ev["upload_ticket_replay"] = {"status": r2.status_code, "body": r2.text[:300]}
                except Exception as exc:
                    ev["upload_ticket_replay"] = {"exception": f"{type(exc).__name__}: {exc}"}
        ev["uploaded_var"] = await read(s, f"reflex://state/vars/{AGENT}/uploaded")
        # auth-required / scope-checked handlers on an anonymous session
        ev["anon_whoami"] = await call(s, "queue_event", {"event_name": ename(names, "whoami") if any(e["name"].endswith(".whoami") for e in names) else "agent_state.whoami", "payload": {}})
        ev["anon_scoped_write"] = await call(s, "queue_event", {"event_name": ename(names, "scoped_write") if any(e["name"].endswith(".scoped_write") for e in names) else "agent_state.scoped_write", "payload": {}})
        ev["anon_private_note"] = await read(s, f"reflex://state/vars/{AGENT}/private_note")
        ev["anon_scoped_view"] = await read(s, f"reflex://state/vars/{AGENT}/scoped_view")
        ev["anon_summary"] = await read(s, "state-resource://entauth___entauth____agent_state/summary/lbl")
        ev["anon_private_summary"] = await read(s, "state-resource://entauth___entauth____agent_state/private_summary")
        flow_bump = ename(names, "bump") if False else next(e["name"] for e in names if e["name"].endswith("flow_state.bump"))
        ev["anon_flow_bump"] = await call(s, "queue_event", {"event_name": flow_bump})
        ev["anon_flow_secret_after_public_bump"] = await read(s, "reflex://state/vars/reflex___state____state.entauth___entauth____flow_state/secret")
        ev["anon_flow_state_dict_secret"] = (await read(s, "reflex://state/vars/reflex___state____state.entauth___entauth____flow_state"))["value"]
        ev["root_redaction"] = '"client_token": ""' in json.dumps((await read(s, "reflex://state/vars/reflex___state____state"))["value"])
        # per-handler rate limit (3/min)
        lim = ename(names, "limited")
        ev["limited_calls"] = [await call(s, "queue_event", {"event_name": lim}) for _ in range(4)]
        ev["limited_calls"] = [{"is_error": c["is_error"], "value": str(c["value"])[:200]} for c in ev["limited_calls"]]
        ev["count_final_A"] = await read(s, f"reflex://state/vars/{AGENT}/count")

    # two MCP sessions hammering the SAME state (same bearer -> same reflex token)
    async with mcp_session(MCP, tok2) as s1, mcp_session(MCP, tok2) as s2:
        search = (await call(s1, "search_events", {"query": "bump"}))["value"]["results"]
        bump = ename(search, "bump")
        t0 = time.time()
        res = await asyncio.gather(*[call(s, "queue_event", {"event_name": bump, "payload": {"amount": 1}}) for _ in range(20) for s in (s1, s2)])
        ev["hammer_elapsed_s"] = round(time.time() - t0, 2)
        ev["hammer_errors"] = [str(r["value"])[:200] for r in res if r["is_error"]]
        ev["hammer_final_count"] = await read(s1, f"reflex://state/vars/{AGENT}/count")
        ev["hammer_pids"] = sorted({str(r["value"].get("delta", {}).get(AGENT, {}).get("last_pid")) for r in res if not r["is_error"] and isinstance(r["value"], dict)})
        ev["isolation_tok2_uploaded"] = await read(s1, f"reflex://state/vars/{AGENT}/uploaded")

    if RATE:
        # call rate limit (default 60/window per token): hammer resource reads with a fresh token
        async with httpx.AsyncClient(timeout=30) as client:
            tok3 = (await grant(client)).json()["access_token"]
        async with mcp_session(MCP, tok3) as s:
            out = []
            for i in range(70):
                r = await read(s, f"reflex://state/vars/{AGENT}/count")
                if r["is_error"]:
                    out.append([i + 1, r["value"][:200]])
                    if len(out) >= 3:
                        break
            ev["call_rate_limit_first_errors"] = out
            ev["search_after_limit"] = await call(s, "search_events", {"query": "x"})
            ev["search_after_limit"]["value"] = str(ev["search_after_limit"]["value"])[:200]
        # token grant rate limit (10/min/IP)
        async with httpx.AsyncClient(timeout=30) as client:
            statuses = []
            for _ in range(14):
                r = await grant(client)
                statuses.append([r.status_code, r.headers.get("retry-after")])
            ev["token_grant_statuses"] = statuses
            ev["token_grant_429_body"] = r.text[:300]


asyncio.run(main())
save(f"mcp-anon-{LABEL}.json", ev)
print(json.dumps(ev, default=str)[:12000])
