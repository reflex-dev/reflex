"""rxe 0.9.8 REST event-handler API: which client_ip does a handler see for a spoofed X-Forwarded-For?

Usage: rest_probe.py <backend_base> <tag> [--hdr 'Name: value']... [--out out.json]
Grants an anonymous token (POST /_reflex/auth/token), calls POST /_reflex/event/hnet___hnet___ip_state/rec with the
given extra headers, parses the ndjson delta stream for IPState.seen and prints the router snapshot the handler recorded.
Also reads /_reflex/retrieve_state and reports whether client_token / session_id are redacted (ENT-16) and whether any
cookie / authorization header value is echoed back.
"""
import argparse
import json
import os
import sys

import httpx
import playwright  # noqa: F401  venv guard

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in playwright.__file__, playwright.__file__
IPSTATE = "reflex___state____state.hnet___hnet___ip_state"
ap = argparse.ArgumentParser()
ap.add_argument("base")
ap.add_argument("tag")
ap.add_argument("--hdr", action="append", default=[])
ap.add_argument("--out", default=None)
a = ap.parse_args()
hdrs = {}
for h in a.hdr:
    k, _, v = h.partition(":")
    hdrs[k.strip()] = v.strip()
c = httpx.Client(base_url=a.base, timeout=30, trust_env=False)
out = {"tag": a.tag, "hdrs": hdrs}
r = c.post("/_reflex/auth/token", headers=hdrs)
out["token_status"] = r.status_code
tok = r.json().get("access_token") if r.status_code == 200 else None
out["token_len"] = len(tok or "")
H = {"Authorization": f"Bearer {tok}", **hdrs}
r = c.post(f"/_reflex/event/{IPSTATE}/rec", headers={**H, "Cookie": "qa_cookie=COOKIEVALUE123"}, json={"tag": a.tag})
out["event_status"] = r.status_code
out["event_ct"] = r.headers.get("content-type")
seen = None
lines = [ln for ln in r.text.splitlines() if ln.strip()]
out["n_lines"] = len(lines)
for ln in lines:
    try:
        d = json.loads(ln)
    except Exception:
        out.setdefault("bad_lines", []).append(ln[:200])
        continue
    delta = d.get("delta", d) if isinstance(d, dict) else {}
    for st, fields in (delta or {}).items():
        if st == IPSTATE and isinstance(fields, dict):
            for k, v in fields.items():
                if k.split("_rx_state_")[0] == "seen":
                    seen = v
out["seen_raw"] = seen
snap = json.loads(seen[-1]) if seen else None
out["snap"] = snap
rs = c.post("/_reflex/retrieve_state", headers=H)
out["retrieve_status"] = rs.status_code
txt = rs.text
out["retrieve_len"] = len(txt)
out["retrieve_has_token"] = bool(tok) and tok in txt
out["retrieve_client_token_values"] = sorted({m for m in __import__("re").findall(r'"client_token[^"]*":\s*"([^"]*)"', txt)})
out["retrieve_session_id_values"] = sorted({m for m in __import__("re").findall(r'"session_id[^"]*":\s*"([^"]*)"', txt)})
out["retrieve_cookie_echo"] = "COOKIEVALUE123" in txt
out["retrieve_authz_echo"] = "Bearer" in txt
out["retrieve_secret_note"] = "SECRETNOTE" in txt
out["event_body_has_token"] = bool(tok) and tok in r.text
out["event_body_cookie_echo"] = "COOKIEVALUE123" in r.text
if a.out:
    json.dump(out, open(a.out, "w"), indent=1)
print(f"{a.tag:28} tok={out['token_status']} ev={out['event_status']} ip={snap and snap.get('ip')!s:14} xff={snap and snap.get('x-forwarded-for')!r:30} asc={snap and snap.get('asgi-scope-client')} ctok_len={snap and snap.get('client_token_len')} sid_len={snap and snap.get('session_id_len')} cookie_in_router={snap and snap.get('cookie')!r} authz_in_router={snap and snap.get('authorization')!r} | retrieve={rs.status_code} ctok_vals={out['retrieve_client_token_values']} sid_vals={out['retrieve_session_id_values']} tok_leak={out['retrieve_has_token'] or out['event_body_has_token']} cookie_echo={out['retrieve_cookie_echo'] or out['event_body_cookie_echo']}")
