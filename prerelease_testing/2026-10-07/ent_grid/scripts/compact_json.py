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
    def trim(o, depth=0):
        """Keep websocket capture structure but cap lists at 6 items and strings at 400 chars."""
        if isinstance(o, str):
            return o if len(o) <= 400 else o[:400] + f"...[{len(o)} chars]"
        if isinstance(o, list):
            return [trim(x, depth + 1) for x in o[:6]] + ([f"...[{len(o)} items]"] if len(o) > 6 else [])
        if isinstance(o, dict):
            return {k: trim(v, depth + 1) for k, v in o.items()}
        return o

    if "websockets" in d:
        d["websockets"] = trim(d["websockets"])
    f.write_text(json.dumps(d, indent=1)[:400000])
