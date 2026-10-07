#!/usr/bin/env bash
# Copy reusable artifacts of the a3_upgrade item into the repo DEST (plain cp/tar, no git).
set -eu
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_upgrade
DEST=/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_upgrade
mkdir -p "$DEST"
cpx() { local src=$1 dst=$2; shift 2; mkdir -p "$dst"; tar -C "$src" "$@" -cf - . | tar -C "$dst" -xf -; }
EXC=(--exclude=.web --exclude=node_modules --exclude=.states --exclude=assets/external --exclude='*.db' --exclude=reflex.lock --exclude=__pycache__ --exclude=.git --exclude='*.pyc' --exclude=uploaded_files --exclude='*.full')
for a in form-designer github-stats clock twitter twitter-redis guide jsondrain smoke311 smoke314 smoke_comp; do [ -d "$W/$a" ] && cpx "$W/$a" "$DEST/apps/$a" "${EXC[@]}"; done
for d in bin scripts patches freeze pkg logs; do [ -d "$W/$d" ] && cpx "$W/$d" "$DEST/$d" --exclude=__pycache__ --exclude='*.pid' --exclude='*.full'; done
# trim oversized logs: head + tail + most repeated lines
$SB/envs/driver/bin/python -I - "$DEST/logs" <<'PY'
import sys
from collections import Counter
from pathlib import Path
for f in Path(sys.argv[1]).rglob("*"):
    if f.is_file() and f.stat().st_size > 150_000:
        lines = f.read_text(errors="replace").splitlines()
        c = Counter(l.strip()[:160] for l in lines)
        rep = [f"  x{n}: {l}" for l, n in c.most_common(6) if n > 20]
        f.write_text("\n".join(lines[:350] + [f"... [{len(lines) - 450} lines trimmed by sync_dest.sh; most repeated lines:"] + rep + ["...]"] + lines[-100:]) + "\n")
PY
# shots: JSON (ws frames trimmed) + jpg only
$SB/envs/driver/bin/python -I - "$W/shots" "$DEST/shots" <<'PY'
import json, shutil, sys
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
for f in src.rglob("*.json"):
    out = dst / f.relative_to(src)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        d = json.loads(f.read_text())
    except Exception:
        shutil.copy2(f, out); continue
    if isinstance(d, dict):
        for k in ("ws_frames", "ws", "probe_ws"):
            v = d.get(k)
            if isinstance(v, list) and len(v) > 8:
                d[k] = [(x if len(json.dumps(x)) < 500 else (json.dumps(x)[:500] + "...")) for x in v[:8]] + [f"... {len(v) - 8} more frames trimmed"]
        for k in ("writes",):
            v = d.get(k)
            if isinstance(v, list) and len(v) > 12:
                d[k] = v[:12] + [f"... {len(v) - 12} more writes trimmed"]
    out.write_text(json.dumps(d, indent=1))
for f in src.rglob("*.jpg"):
    if f.stat().st_size < 150_000:
        out = dst / f.relative_to(src); out.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, out)
PY
[ -f "$W/NOTES.md" ] && cp "$W/NOTES.md" "$DEST/NOTES.md" || true
du -sh "$DEST"
