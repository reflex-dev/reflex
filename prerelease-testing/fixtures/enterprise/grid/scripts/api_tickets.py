"""Exercise the EventHandlerAPIPlugin of the tickets demo over HTTP (httpx).

Usage: api_tickets.py <backend_base_url> <out_json>
Prints and saves status codes / bodies for: token, api-catalog, openapi.yaml, retrieve_state,
create_ticket (valid, unauthenticated, bad token, missing arg, wrong type), set_status, unknown handler,
GET on a POST endpoint, and state isolation between two tokens.
"""
import json
import sys

import httpx

base, out = sys.argv[1], sys.argv[2]
S = "tickets___tickets____ticket_state"
res = {}
c = httpx.Client(base_url=base, timeout=30, trust_env=False)


def rec(name, r):
    body = r.text
    try:
        body = r.json()
    except Exception:
        body = body[:600]
    res[name] = {"status": r.status_code, "body": body if not isinstance(body, str) else body[:600]}
    print(f"{name:45s} {r.status_code} {json.dumps(body)[:260] if not isinstance(body, str) else body[:260]!r}")
    return r


tok = rec("token", c.post("/_reflex/auth/token")).json()["access_token"]
tok2 = c.post("/_reflex/auth/token").json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
rec("api-catalog", c.get("/.well-known/api-catalog"))
r = rec("openapi.yaml", c.get("/_reflex/events/openapi.yaml"))
res["openapi mentions create_ticket"] = "create_ticket" in r.text
rec("retrieve_state (no token)", c.post("/_reflex/retrieve_state"))
rec("retrieve_state", c.post("/_reflex/retrieve_state", headers=H))
rec("create_ticket", c.post(f"/_reflex/event/{S}/create_ticket", headers=H, json={"title": "API ticket", "priority": "high", "assignee": "api"}))
rec("create_ticket (no token)", c.post(f"/_reflex/event/{S}/create_ticket", json={"title": "x"}))
rec("create_ticket (bad token)", c.post(f"/_reflex/event/{S}/create_ticket", headers={"Authorization": "Bearer nope"}, json={"title": "x"}))
rec("create_ticket (missing title)", c.post(f"/_reflex/event/{S}/create_ticket", headers=H, json={"priority": "low"}))
rec("create_ticket (title wrong type)", c.post(f"/_reflex/event/{S}/create_ticket", headers=H, json={"title": 123}))
rec("create_ticket (unknown arg)", c.post(f"/_reflex/event/{S}/create_ticket", headers=H, json={"title": "y", "bogus": 1}))
rec("create_ticket (non-JSON body)", c.post(f"/_reflex/event/{S}/create_ticket", headers={**H, "Content-Type": "application/json"}, content=b"{not json"))
st = rec("retrieve_state after create", c.post("/_reflex/retrieve_state", headers=H)).json()
tickets = []

def find(o):
    if isinstance(o, dict):
        if "tickets" in o and isinstance(o["tickets"], list):
            tickets.extend(o["tickets"])
        for v in o.values():
            find(v)
find(st)
res["tickets in token1 state"] = [t.get("title") for t in tickets if isinstance(t, dict)]
print("tickets in token1 state:", res["tickets in token1 state"])
tid = next((t["ticket_id"] for t in tickets if isinstance(t, dict) and t.get("title") == "API ticket"), None)
if tid:
    rec("set_status closed", c.post(f"/_reflex/event/{S}/set_status", headers=H, json={"ticket_id": tid, "status": "closed"}))
    rec("set_status invalid", c.post(f"/_reflex/event/{S}/set_status", headers=H, json={"ticket_id": tid, "status": "bogus"}))
rec("unknown handler", c.post(f"/_reflex/event/{S}/nope", headers=H, json={}))
rec("private helper _reload_from_db", c.post(f"/_reflex/event/{S}/_reload_from_db", headers=H, json={}))
rec("GET on POST endpoint", c.get(f"/_reflex/event/{S}/seed", headers=H))
st2 = rec("retrieve_state token2", c.post("/_reflex/retrieve_state", headers={"Authorization": f"Bearer {tok2}"})).json()
res["token2 sees token1's q/filters?"] = "n/a"
json.dump(res, open(out, "w"), indent=1, default=str)
