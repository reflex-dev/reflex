"""Post-process ws_frames.txt into a per-step router-delta matrix."""
import json, sys, collections
from pathlib import Path

path = Path(sys.argv[1])
rows = []
for line in path.read_text().splitlines():
    if not line.startswith("["):
        continue
    lab, rest = line[1:].split("] ", 1)
    direction, payload = rest.split(": ", 1)
    i = payload.find("[")
    if i < 0:
        continue
    try:
        obj = json.loads(payload[i:])
    except Exception:
        continue
    if not isinstance(obj, list) or len(obj) < 2 or obj[0] != "event":
        continue
    body = obj[1]
    if direction == "sent":
        rows.append((lab, "SENT", payload.encode().__len__(), body.get("name", "?"),
                     body.get("router_data"), None))
        continue
    delta = body.get("delta")
    if delta is None:
        continue
    root = delta.get("reflex___state____state", {})
    rkeys = sorted(k for k in root if k.startswith("rx_router_") or k.startswith("router_"))
    rbytes = len(json.dumps({k: root[k] for k in rkeys}, separators=(",", ":")))
    rows.append((lab, "DELTA", len(payload.encode()), None, None,
                 (rkeys, rbytes, {k: sorted(v) for k, v in delta.items() if v})))

cur = None
for lab, kind, nbytes, name, rdata, d in rows:
    if lab != cur:
        print(f"\n########## {lab}")
        cur = lab
    if kind == "SENT":
        print(f"  -> SENT {nbytes}B {name} router_data={json.dumps(rdata)[:160] if rdata else None}")
    else:
        rkeys, rbytes, alls = d
        short = [k.replace("_rx_state_", "").replace("rx_router_", "") for k in rkeys]
        print(f"  <- DELTA {nbytes}B  ROUTER={short} routerbytes={rbytes}")
        for st, ks in alls.items():
            print(f"        {st.split('.')[-1]}: {[k.replace('_rx_state_','') for k in ks]}")
