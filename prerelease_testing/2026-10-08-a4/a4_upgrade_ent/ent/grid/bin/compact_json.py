"""Copy driver JSON outputs into DEST in compact form (drops raw_ws/pw_frames, caps timeline/console lists).

Usage: driver-python -I compact_json.py <src-out-dir> <dest-out-dir>
"""
import json
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
for f in src.rglob("*.json"):
    t = dst / f.relative_to(src)
    if t.exists() and t.stat().st_mtime >= f.stat().st_mtime:
        continue
    t.parent.mkdir(parents=True, exist_ok=True)
    try:
        d = json.loads(f.read_text())
    except Exception:
        t.write_bytes(f.read_bytes())
        continue
    if isinstance(d, dict):
        for k in ("raw_ws", "pw_frames", "requests", "websockets"):
            d.pop(k, None)
        for k, cap in (("timeline", 160), ("console", 60), ("console_all", 60), ("boot_frames", 30)):
            if isinstance(d.get(k), list) and len(d[k]) > cap:
                d[k] = d[k][:cap] + [f"... {len(d[k]) - cap} more (full file in the scratch out dir)"]
    t.write_text(json.dumps(d, indent=0))
