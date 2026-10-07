#!/usr/bin/env bash
# Copy reusable artifacts of the upgrade_sweep cluster into the repo DEST (plain cp/rsync, no git).
set -eu
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/upgrade_sweep
DEST=/home/user/reflex/prerelease_testing/2026-10-07/upgrade_sweep
mkdir -p "$DEST"
cpx() { # cpx <srcdir> <destdir> [tar --exclude args...]
  local src=$1 dst=$2; shift 2; mkdir -p "$dst"; tar -C "$src" "$@" -cf - . | tar -C "$dst" -xf -; }
EXC=(--exclude=.web --exclude=node_modules --exclude=.states --exclude=assets/external --exclude='*.db' --exclude=reflex.lock --exclude=__pycache__ --exclude=.git --exclude='*.pyc' --exclude=uploaded_files)
for a in form-designer github-stats clock twitter twitter-redis; do [ -d "$W/$a" ] && cpx "$W/$a" "$DEST/$a" "${EXC[@]}"; done
cpx "$W/bin" "$DEST/bin" --exclude=__pycache__
cpx "$W/scripts" "$DEST/scripts" --exclude=__pycache__
cpx "$W/patches" "$DEST/patches"
cpx "$W/freeze" "$DEST/freeze" --exclude='*.lock.dir'
cpx "$W/pkg" "$DEST/pkg" --exclude='*.lock.dir'
cpx "$W/logs" "$DEST/logs" --exclude='*.pid'
[ -d "$W/baseline_a1" ] && cpx "$W/baseline_a1" "$DEST/baseline_a1" || true
mkdir -p "$DEST/shots"
# JSON (trim ws frames) + a handful of PNGs
$SB/envs/driver/bin/python -I - "$W/shots" "$DEST/shots" <<'PY'
import json, shutil, sys
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
for f in src.rglob("*.json"):
    out = dst / f.relative_to(src)
    out.parent.mkdir(parents=True, exist_ok=True)
    d = json.loads(f.read_text())
    for k in ("ws_frames", "ws", "probe_ws"):
        v = d.get(k)
        if isinstance(v, list) and len(v) > 8:
            d[k] = [(x if len(json.dumps(x)) < 500 else (json.dumps(x)[:500] + "...")) for x in v[:8]] + [f"... {len(v) - 8} more frames trimmed"]
    for k in ("writes",):
        v = d.get(k)
        if isinstance(v, list) and len(v) > 12:
            d[k] = v[:12] + [f"... {len(v) - 12} more writes trimmed"]
    out.write_text(json.dumps(d, indent=1))
keep = ("fd-up-up_home.png", "fd-up-entry_responses.png", "gh-up-firstload-home.png", "gh-up_01", "ck-up_01_initial", "ck-session-up-a2_N_new_tab", "tw-up_", "smoke-dev-dark", "smoke-prod-index", "f1combo-a1-dev-fresh", "dt-a2-inplace_02")
n = 0
for f in src.rglob("*.png"):
    if any(k in f.name for k in keep) and f.stat().st_size < 90_000:
        out = dst / f.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
        n += 1
print("png copied:", n)
PY
[ -f "$W/NOTES.md" ] && cp "$W/NOTES.md" "$DEST/NOTES.md" || true
du -sh "$DEST"
