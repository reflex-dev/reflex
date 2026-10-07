"""Print a merged, time-ordered trace of the first in-page websocket/storage log entries of every tab of a vh_tabs.py run.
Usage: vtrace.py RESULT_JSON [MAX_LINES]"""
import json
import sys

r = json.load(open(sys.argv[1]))
mx = int(sys.argv[2]) if len(sys.argv) > 2 else 80
ev = []
for i, t in enumerate(r["per_tab"]):
    for ts, d, m in t.get("log", []):
        if d == "in" and m.startswith("0{"):
            continue
        ev.append((ts, i, d, m))
for c in r.get("clicks", []):
    ev.append((int(c[1] * 1000), 0, "CLICK", str(c)))
ev.sort()
t0 = ev[0][0]
for ts, i, d, m in ev[:mx]:
    if d in ("out", "in"):
        m = m.replace("reflex___state____state.vhsync___vhsync____", "").replace("reflex___state____state", "ROOT")
        for k in ("hydrate_and_load", "update_vars_internal", "pick", "toggle", "bump"):
            if k in m and d == "out":
                m = m[: m.find('"payload"')] + "..." + (m[m.find('"vars"'):m.find('"vars"') + 70] if '"vars"' in m else m[m.find('"payload"'):m.find('"payload"') + 40])
                break
    print(f"{ts - t0:6d} tab{i} {d:7s} {m[:150]}")
