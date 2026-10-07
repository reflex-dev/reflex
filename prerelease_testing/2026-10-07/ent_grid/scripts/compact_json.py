"""Compact driver JSON reports copied to DEST: drop benign console lines and keep at most 60 requests / ws samples.

Usage: compact_json.py <dir>   (rewrites *.json in place; the full reports stay in the scratchpad out/)
"""
import json
import sys
from pathlib import Path

for f in Path(sys.argv[1]).rglob("*.json"):
    try:
        d = json.loads(f.read_text())
    except Exception:
        continue
    if not isinstance(d, dict) or "checks" not in d:
        continue
    if isinstance(d.get("console_all"), list):
        d["console_all"] = [c for c in d["console_all"] if not c.get("benign")][:200]
    if isinstance(d.get("requests"), list) and len(d["requests"]) > 60:
        d["requests_truncated_from"] = len(d["requests"])
        d["requests"] = d["requests"][:60]
    ws = d.get("websockets")
    if isinstance(ws, dict):
        for v in ws.values():
            if isinstance(v, dict):
                for k in ("sent", "recv", "frames", "samples"):
                    if isinstance(v.get(k), list) and len(v[k]) > 20:
                        v[k] = v[k][:20]
    f.write_text(json.dumps(d, indent=1)[:400000])
