"""Check over HTTP whether the REST surface discloses the session client_token.

Copy of the campaign's ent_map_dnd_flow_mantine/verification/v_leak_http.py with
the backend port and the state name taken from argv, and the saved bodies masked
so no live token lands in the evidence directory.

Usage: v_leak_http.py <base-url> <retrieve_state.json> <event_delta.ndjson>
"""

import json
import re
import sys

import httpx

BASE = sys.argv[1]
STATE = "tickets___tickets____ticket_state"
c = httpx.Client(timeout=30.0, trust_env=False)

tok = c.post(f"{BASE}/_reflex/auth/token").json()
bearer = tok.get("access_token")
print("BEARER:", bearer[:12], "...(masked)")
H = {"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"}


def mask(text: str) -> str:
    """Replace the bearer and any UUID-shaped value with a placeholder.

    Args:
        text: The response body to scrub.

    Returns:
        The body with live credentials replaced.
    """
    text = text.replace(bearer, "<BEARER-MASKED>")
    return re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "<UUID-MASKED>",
        text,
    )


def find(obj, needle_keys=("client_token", "session_id"), path=""):
    """Collect non-empty session-secret fields anywhere in a JSON structure.

    Args:
        obj: The decoded JSON value to walk.
        needle_keys: The field names that must never carry a value.
        path: The dotted path of ``obj``.

    Returns:
        A list of ``(path, value)`` pairs for every non-empty secret found.
    """
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in needle_keys and isinstance(v, str) and v:
                hits.append((f"{path}.{k}", v))
            hits += find(v, needle_keys, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += find(v, needle_keys, f"{path}[{i}]")
    return hits


rs = c.post(f"{BASE}/_reflex/retrieve_state", headers=H)
body = rs.json()
print("retrieve_state status", rs.status_code)
root = body.get("state", body)
print("TOP KEYS:", sorted(root) if isinstance(root, dict) else type(root))
with open(sys.argv[2], "w") as f:
    f.write(mask(json.dumps(body, indent=1)))

hits = find(body)
print("SESSION-SECRET FIELDS IN retrieve_state:", hits or "NONE (redacted)")
ct = [v for p, v in hits if p.endswith("client_token")]

ev = c.post(f"{BASE}/_reflex/event/{STATE}/seed", json={}, headers=H)
print("event status", ev.status_code, "len", len(ev.text))
with open(sys.argv[3], "w") as f:
    f.write(mask(ev.text))
evhits = []
for line in ev.text.splitlines():
    try:
        d = json.loads(line)
    except Exception:
        continue
    evhits += find(d)
print("SESSION-SECRET FIELDS IN event delta:", evhits or "NONE (redacted)")

if ct:
    t = ct[0]
    print("LEAKED CLIENT TOKEN:", t[:12], "...| equals bearer?", t == bearer)
    r = c.get(f"{BASE}/_event/?token={t}&EIO=4&transport=polling")
    print("polling handshake with leaked token ->", r.status_code, r.text[:160])

print("VERDICT", "LEAK" if (hits or evhits) else "OK")
sys.exit(1 if (hits or evhits) else 0)
