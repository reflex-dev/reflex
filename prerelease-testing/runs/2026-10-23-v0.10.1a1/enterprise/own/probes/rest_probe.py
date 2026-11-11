"""rxe 0.9.8 REST event-handler API: which client_ip does a handler see for a spoofed X-Forwarded-For?

Usage: rest_probe.py <backend_base> <tag> [--hdr 'Name: value']... [--out out.json]
Grants an anonymous token (POST /_reflex/auth/token), calls POST /_reflex/event/hnet___hnet___ip_state/rec with the
given extra headers, parses the ndjson delta stream for IPState.seen and prints the router snapshot the handler recorded.
Also reads /_reflex/retrieve_state and reports whether client_token / session_id are redacted (ENT-16) and whether any
cookie / authorization header value is echoed back. stdlib only (urllib), so it runs in any venv.
"""
import argparse
import json
import re
import urllib.error
import urllib.request

IPSTATE = "reflex___state____state.hnet___hnet___ip_state"
REST_STATE = "hnet___hnet___ip_state"  # the REST route uses the short (root-less) state name, as in the tickets demo
ap = argparse.ArgumentParser()
ap.add_argument("base")
ap.add_argument("tag")
ap.add_argument("--hdr", action="append", default=[])
ap.add_argument("--out", default=None)
a = ap.parse_args()
B = a.base.rstrip("/")
hdrs = {}
for h in a.hdr:
    k, _, v = h.partition(":")
    hdrs[k.strip()] = v.strip()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # no proxy for localhost


def post(path, headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else b""
    req = urllib.request.Request(B + path, data=data, method="POST", headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with opener.open(req, timeout=30) as r:
            return r.status, r.headers.get("content-type"), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("content-type"), e.read().decode("utf-8", "replace")


out = {"tag": a.tag, "hdrs": hdrs}
st, _, txt = post("/_reflex/auth/token", hdrs)
out["token_status"] = st
tok = json.loads(txt).get("access_token") if st == 200 else None
out["token_len"] = len(tok or "")
H = {"Authorization": f"Bearer {tok}", **hdrs}
st, ct, txt = post(f"/_reflex/event/{REST_STATE}/rec", {**H, "Cookie": "qa_cookie=COOKIEVALUE123"}, {"tag": a.tag})
out["event_status"], out["event_ct"] = st, ct
seen = None
lines = [ln for ln in txt.splitlines() if ln.strip()]
out["n_lines"] = len(lines)
for ln in lines:
    try:
        d = json.loads(ln)
    except Exception:
        out.setdefault("bad_lines", []).append(ln[:200])
        continue
    delta = d.get("delta", d) if isinstance(d, dict) else {}
    for stn, fields in (delta or {}).items():
        if stn == IPSTATE and isinstance(fields, dict):
            for k, v in fields.items():
                if k.split("_rx_state_")[0] == "seen":
                    seen = v
out["seen_raw"] = seen
snap = json.loads(seen[-1]) if seen else None
out["snap"] = snap
rst, _, rtxt = post("/_reflex/retrieve_state", H)
out["retrieve_status"] = rst
out["retrieve_len"] = len(rtxt)
out["retrieve_has_token"] = bool(tok) and tok in rtxt
out["retrieve_client_token_values"] = sorted(set(re.findall(r'"client_token[^"]*":\s*"([^"]*)"', rtxt)))
out["retrieve_session_id_values"] = sorted(set(re.findall(r'"session_id[^"]*":\s*"([^"]*)"', rtxt)))
out["retrieve_cookie_echo"] = "COOKIEVALUE123" in rtxt
out["retrieve_authz_echo"] = "Bearer" in rtxt
out["retrieve_secret_note"] = "SECRETNOTE" in rtxt
out["event_body_has_token"] = bool(tok) and tok in txt
out["event_body_cookie_echo"] = "COOKIEVALUE123" in txt
out["event_body_head"] = txt[:300]
if a.out:
    json.dump(out, open(a.out, "w"), indent=1)
print(f"{a.tag:18} tok={out['token_status']} ev={out['event_status']} ip={snap and snap.get('ip')!s:12} xff={snap and snap.get('x-forwarded-for')!r:22} asc={snap and snap.get('asgi-scope-client')} ctok_len={snap and snap.get('client_token_len')} sid_len={snap and snap.get('session_id_len')} cookie_in_router={snap and snap.get('cookie')!r} authz_in_router={snap and snap.get('authorization')!r} | retrieve={rst} ctok_vals={out['retrieve_client_token_values']} sid_vals={out['retrieve_session_id_values']} tok_leak={out['retrieve_has_token'] or out['event_body_has_token']} cookie_echo={out['retrieve_cookie_echo'] or out['event_body_cookie_echo']} secret_note_visible={out['retrieve_secret_note']}")
