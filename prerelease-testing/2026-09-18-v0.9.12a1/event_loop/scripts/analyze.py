"""Summarize a frames.jsonl: per-inbound delta keys + byte totals."""

import json
import re
import sys

path = sys.argv[1]
rows = [json.loads(line) for line in open(path) if line.strip()]
total_in = 0
delta_bytes = 0
n_delta = 0
for f in rows:
    p = f["payload"]
    if f["dir"] == "in":
        total_in += len(p)
    m = re.match(r"^\d+(?:/[^,]*,)?(\[.*)$", p)
    if not m:
        continue
    try:
        parsed = json.loads(m.group(1))
    except Exception:
        continue
    if not (isinstance(parsed, list) and len(parsed) >= 2):
        continue
    name, payload = parsed[0], parsed[1]
    if f["dir"] == "out":
        print(f"{f['ctx']} OUT {payload.get('name', name)}")
        continue
    d = payload.get("delta") if isinstance(payload, dict) else None
    ev = payload.get("events") if isinstance(payload, dict) else None
    if d:
        n_delta += 1
        delta_bytes += len(p)
        short = {
            k.replace("reflex___state____state", "S").replace(
                "elapp___elapp___", ""
            ): sorted(x.replace("_rx_state_", "") for x in v)
            for k, v in d.items()
        }
        print(f"{f['ctx']} IN  delta({len(p)}B) {short}")
    if ev:
        print(f"{f['ctx']} IN  events {json.dumps(ev)[:300]}")
print(f"\n-- inbound frames bytes: {total_in}; delta frames: {n_delta} ({delta_bytes}B)")
