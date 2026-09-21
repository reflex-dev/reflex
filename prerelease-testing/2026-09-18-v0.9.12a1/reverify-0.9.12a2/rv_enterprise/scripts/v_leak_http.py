"""Check over HTTP whether the REST surface discloses the session client_token."""
import json, sys
import httpx

BASE = "http://localhost:8140"
STATE = "tickets___tickets____ticket_state"
c = httpx.Client(timeout=30.0, trust_env=False)

tok = c.post(f"{BASE}/_reflex/auth/token").json()
bearer = tok.get("access_token")
print("BEARER:", bearer[:40], "...")
H = {"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"}

rs = c.post(f"{BASE}/_reflex/retrieve_state", headers=H)
body = rs.json()
print("retrieve_state status", rs.status_code)
root = body.get("state", body)
print("TOP KEYS:", list(root)[:6] if isinstance(root, dict) else type(root))
txt = json.dumps(body)
open(sys.argv[1], "w").write(json.dumps(body, indent=1))

def find(obj, needle_keys=("client_token", "session_id"), path=""):
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

hits = find(body)
print("SESSION-SECRET FIELDS IN retrieve_state:", hits or "NONE (redacted)")
ct = [v for p, v in hits if p.endswith("client_token")]

# event endpoint delta
ev = c.post(f"{BASE}/_reflex/event/{STATE}/seed", json={}, headers=H)
print("event status", ev.status_code, "len", len(ev.text))
open(sys.argv[2], "w").write(ev.text)
evhits = []
for line in ev.text.splitlines():
    try:
        d = json.loads(line)
    except Exception:
        continue
    evhits += find(d)
print("SESSION-SECRET FIELDS IN event delta:", evhits or "NONE")

# Is the leaked client_token actually usable on the websocket path?
if ct:
    t = ct[0]
    print("LEAKED CLIENT TOKEN:", t, "| equals bearer?", t == bearer)
    r = c.get(f"{BASE}/_event/?token={t}&EIO=4&transport=polling")
    print("polling handshake with leaked token ->", r.status_code, r.text[:160])
