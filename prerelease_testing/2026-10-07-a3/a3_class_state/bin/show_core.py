"""Summarize a drive_core.py JSON: show_core.py <json> [pages]."""
import json, sys
r = json.load(open(sys.argv[1]))
pages = sys.argv[2].split(",") if len(sys.argv) > 2 else [k for k in r if isinstance(r[k], dict)]
for p in pages:
    if p not in r:
        continue
    print(f"== {p}")
    for k, v in r[p].items():
        print(f"  {k}: {json.dumps(v)[:420]}")
for k in ("console", "bad", "ws_frames"):
    if k in r:
        v = r[k]
        if k == "console":
            v = [c for c in v if "Hey developer" not in c and "[vite]" not in c and "DevTools" not in c]
        print(f"{k}: {json.dumps(v)[:1500]}")
