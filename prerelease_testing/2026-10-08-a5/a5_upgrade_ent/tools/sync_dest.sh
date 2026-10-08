#!/usr/bin/env bash
# Copy reusable artifacts of a5_upgrade_ent into the repo DEST (plain tar, no git). Excludes .web/node_modules/.states/db/lock/venvs/caches,
# trims big logs, keeps report JSONs (ws frames trimmed) and small JPEG/PNG screenshots.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent
DEST=/home/user/reflex/prerelease_testing/2026-10-08-a5/a5_upgrade_ent
mkdir -p $DEST
EXC=(--exclude=.web --exclude=node_modules --exclude=.states --exclude=assets/external --exclude='*.db' --exclude=reflex.lock --exclude=__pycache__
     --exclude='*.pyc' --exclude=uploaded_files --exclude=profiles --exclude='*.pid' --exclude='*.pgid' --exclude=pids --exclude='*.png' --exclude='*.webm'
     --exclude='*.zip' --exclude=.git --exclude=runs --exclude=screenshots --exclude=a3ref)
tar -C $W "${EXC[@]}" --exclude='up/run' --exclude='tp/run' --exclude='ent/auth/run' --exclude='ent/auth/vauth_*' --exclude='ent/auth/entauth_a*' --exclude='ent/auth/vauthd_*' --exclude='./a4ref' --exclude='./inst/run' --exclude='./tp/grep7360' --exclude='./ent/grid/runs' --exclude='*.log.1' -cf - . | tar -C $DEST -xf -
# screenshots: jpg only, small
find $DEST -name "*.jpg" -size +120k -delete
find $DEST/up/shots -name "*.jpg" \( -path "*attempt1*" -o -name "*base*" -o -name "*rollback*" \) -delete 2>/dev/null
find $DEST/up/shots -name "*.jpg" ! -name "*firstload*" ! -name "*end*" ! -name "*final*" -delete 2>/dev/null
$SB/envs/driver/bin/python -I - "$DEST" <<'PY'
import json, sys
from collections import Counter
from pathlib import Path
for f in Path(sys.argv[1]).rglob("*"):
    if not f.is_file():
        continue
    if f.suffix in (".log", ".txt", ".out") and f.stat().st_size > 150_000:
        lines = f.read_text(errors="replace").splitlines()
        c = Counter(l.strip()[:160] for l in lines)
        rep = [f"  x{n}: {l}" for l, n in c.most_common(6) if n > 20]
        f.write_text("\n".join(lines[:300] + [f"... [{len(lines) - 400} lines trimmed by sync_dest.sh; most repeated:"] + rep + ["...]"] + lines[-100:]) + "\n")
    elif f.suffix == ".json" and f.stat().st_size > 200_000:
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        def trim(o, depth=0):
            if isinstance(o, list) and len(o) > 40:
                return [trim(x, depth + 1) for x in o[:40]] + [f"... {len(o) - 40} more trimmed"]
            if isinstance(o, list):
                return [trim(x, depth + 1) for x in o]
            if isinstance(o, dict):
                return {k: trim(v, depth + 1) for k, v in o.items()}
            if isinstance(o, str) and len(o) > 600:
                return o[:600] + "...(trimmed)"
            return o
        f.write_text(json.dumps(trim(d), indent=1))
PY
du -sh $DEST
# size trim: grid screenshots only for the N-025 run, flow reload probes keep their txt (JSON gzipped), big JSONs gzipped
find $DEST/ent/grid/out -name '*.jpg' ! -path '*entv_a5ent_prod*' -delete
find $DEST/ent/grid/out/entv_a5ent_prod -name '*.jpg' | sort | tail -n +7 | xargs -r rm -f
rm -rf $DEST/ent/auth/vauthx_a4e $DEST/ent/auth/vauthx_a5e
find $DEST \( -name '*.json' -o -name '*.log' \) -size +30k -exec gzip -f {} \;
du -sh $DEST
