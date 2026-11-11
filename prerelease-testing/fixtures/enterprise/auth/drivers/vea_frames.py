"""Print a compact websocket timeline of one driver result: frames after mark_t (event names, delta keys/values of interest)."""
import json
import re
import sys

import playwright  # noqa: F401  (venv guard below)

assert ("/envs/" + __import__("os").environ.get("DRV_VENV", "driver") + "/") in playwright.__file__, playwright.__file__

path, rep = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0
tab = sys.argv[3] if len(sys.argv) > 3 else "tab1"
r = json.load(open(path))[rep]
t0 = r.get("mark_t", 0)
for t, d, s in r[tab]["frames"]:
    if t < t0 - 0.01:
        continue
    m = re.search(r'"name":"([^"]+)"', s)
    if d == "sent":
        print(f"{t:8.3f} SENT {m.group(1).rpartition('.')[2] if m else s[:80]}")
        continue
    body = s
    keys = []
    for k in ("user_sub", "secret_rx_state_", "draft_rx_state_", "latest_access_token_hash_ls_rx_state_", "is_hydrated_rx_state_", "has_any_token", "sub_rx_state_"):
        for mm in re.finditer(r'"(%s[^"]*)":("[^"]{0,20}|[a-z0-9]+)' % k, body):
            keys.append(f"{mm.group(1).replace('_rx_state_', '')}={mm.group(2)}")
    ev = re.findall(r'"name":"([^"]+)"', body)
    ev = [e.rpartition(".")[2] for e in ev]
    print(f"{t:8.3f} RECV {' '.join(keys)} {('events=' + ','.join(ev)) if ev else ''}"[:400])
