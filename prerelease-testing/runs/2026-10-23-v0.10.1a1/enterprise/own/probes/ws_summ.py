"""One-line summary of a ws_probe.py JSON result line. Usage: ws_summ.py <name> <json-line>"""
import json, sys
n, raw = sys.argv[1], sys.argv[2]
try:
    d = json.loads(raw)
except Exception:
    print(f"{n:28} RAW {raw[:300]}"); sys.exit()
s = d["seen"][-1] if d.get("seen") else {}
print(f"{n:28} status={str(d.get('status'))[:12]} ip={s.get('ip')!s:14} xff={s.get('x-forwarded-for')!r:30} asc={s.get('asgi-scope-client')} ctok_len={s.get('client_token_len')} sid_len={s.get('session_id_len')} err={(d.get('errors') or [])[:1]}")
