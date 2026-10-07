"""Decode socket.io frames from a saved capture; print deltas for states matching a filter.

Usage: decode_frames.py <capture.json> <phase> <state-substring> [<state-substring> ...]
"""
import json
import sys

d = json.load(open(sys.argv[1]))
frames = d["frames"] if "frames" in d else d["ws"]
phase = sys.argv[2]
subs = sys.argv[3:]
for f in frames:
    if f["phase"] != phase or f["dir"] == "open":
        continue
    data = f["data"]
    if data.startswith("42/_event,"):
        payload = json.loads(data[len("42/_event,"):])
        if payload[0] != "event":
            print(f["t"], f["dir"], data[:300]); continue
        if f["dir"] == "sent":
            ev = payload[1]
            print(f["t"], "sent EVENT", ev.get("name"), json.dumps(ev.get("payload", {}))[:400]); continue
        body = payload[1]
        delta = body.get("delta", {})
        out = {}
        for st, vs in delta.items():
            short = st.split(".")[-1]
            if any(s in st for s in subs) or st == "reflex___state____state":
                out[short] = {k: v for k, v in vs.items() if "router" not in k}
        extra = {k: v for k, v in body.items() if k != "delta"}
        print(f["t"], "recv DELTA", json.dumps(out)[:900], ("events=" + json.dumps(extra)[:200]) if extra.get("events") else "")
    elif data.startswith("40/_event,{\"event\""):
        ev = json.loads(data[len("40/_event,"):])["event"]
        print(f["t"], "sent CONNECT+EVENT", ev.get("name"), json.dumps(ev.get("payload", {}).get("vars", {}))[:400])
    else:
        print(f["t"], f["dir"], data[:120])
