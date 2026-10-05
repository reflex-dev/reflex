"""Exercise the tickets demo's EventHandlerAPIPlugin REST surface.

Usage: python probe_tickets_api.py <backend_base_url> [out.json]
Run with the driver venv (httpx installed). Prints one line per check.
"""

import json
import sys
import uuid

import httpx

BASE = sys.argv[1].rstrip("/")
OUT = sys.argv[2] if len(sys.argv) > 2 else None
STATE = "tickets___tickets____ticket_state"
R = {}
client = httpx.Client(timeout=30.0, trust_env=False, follow_redirects=True)


def record(name, resp, body_head=400):
    """Record one HTTP check.

    Args:
        name: Check name.
        resp: The httpx response.
        body_head: How much of the body to keep.

    Returns:
        The parsed JSON body when possible, else the text head.
    """
    try:
        payload = resp.json()
        head = json.dumps(payload)[:body_head]
    except Exception:  # noqa: BLE001
        payload = None
        head = resp.text[:body_head]
    R[name] = {"status": resp.status_code, "body": head}
    print(f"[{name}] {resp.status_code} {head[:240]}", flush=True)
    return payload if payload is not None else resp.text


# 1. an app-issued anonymous token (the API accepts nothing else)
tok = record("auth_token", client.post(f"{BASE}/_reflex/auth/token"))
token = tok.get("access_token") if isinstance(tok, dict) else None
H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# 2. no token at all / a bogus token
record("create_no_auth", client.post(
    f"{BASE}/_reflex/event/{STATE}/create_ticket", json={"title": "no auth"}))
record("create_bad_auth", client.post(
    f"{BASE}/_reflex/event/{STATE}/create_ticket",
    json={"title": "bad auth"}, headers={"Authorization": "Bearer nonsense"}))

# 3. the documented catalog + OpenAPI document
record("api_catalog", client.get(f"{BASE}/.well-known/api-catalog"))
record("openapi_yaml", client.get(f"{BASE}/_reflex/events/openapi.yaml"))

# 4. retrieve_state
record("retrieve_state", client.post(f"{BASE}/_reflex/retrieve_state", headers=H))

# 5. create a ticket through the REST endpoint
title = f"api ticket {uuid.uuid4().hex[:8]}"
record("create_ticket", client.post(
    f"{BASE}/_reflex/event/{STATE}/create_ticket",
    json={"title": title, "priority": "high", "assignee": "api-bot"}, headers=H))
R["created_title"] = title

# 6. wrong state-name spelling (three underscores) and a bogus handler
record("create_wrong_state", client.post(
    f"{BASE}/_reflex/event/tickets___tickets___ticket_state/create_ticket",
    json={"title": "x"}, headers=H))
record("nonexistent_handler", client.post(
    f"{BASE}/_reflex/event/{STATE}/no_such_handler", json={}, headers=H))

# 7. validation: bad payload types and a missing required arg
record("create_missing_title", client.post(
    f"{BASE}/_reflex/event/{STATE}/create_ticket", json={"priority": "high"}, headers=H))
record("create_wrong_type", client.post(
    f"{BASE}/_reflex/event/{STATE}/create_ticket",
    json={"title": 12345, "priority": ["high"]}, headers=H))
record("set_status_bad_id", client.post(
    f"{BASE}/_reflex/event/{STATE}/set_status",
    json={"ticket_id": "does-not-exist", "status": "closed"}, headers=H))
record("set_status_bad_status", client.post(
    f"{BASE}/_reflex/event/{STATE}/set_status",
    json={"ticket_id": "does-not-exist", "status": "not-a-status"}, headers=H))

# 8. a handler that returns an EventSpec rather than mutating state
record("apply_query", client.post(
    f"{BASE}/_reflex/event/{STATE}/apply_query", json={"query": "api"}, headers=H))

# 9. seed + load through the API, then read the list back
record("seed", client.post(f"{BASE}/_reflex/event/{STATE}/seed", json={}, headers=H))
record("load_tickets", client.post(f"{BASE}/_reflex/event/{STATE}/load_tickets", json={}, headers=H))

# 10. a private (underscore-prefixed) helper must not be exposed
record("private_helper", client.post(
    f"{BASE}/_reflex/event/{STATE}/_reload_from_db", json={}, headers=H))

# 11. the docs-style endpoints the demo's docstring advertises
record("openapi_json", client.get(f"{BASE}/_reflex/events/openapi.json"))
record("docs", client.get(f"{BASE}/docs"))

if OUT:
    with open(OUT, "w") as fh:
        json.dump(R, fh, indent=1)
    print("saved", OUT)
