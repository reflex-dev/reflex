#!/usr/bin/env bash
# Minimal self-contained repro: the frontend-install cache is dropped on every
# reflex CLI invocation because bun pretty-prints .web/package.json while
# reflex renders it compact.
#
#   usage: repro_install_cache.sh <path-to-reflex-bin> <fresh-work-dir>
#   e.g.   repro_install_cache.sh $SB/envs/smoke/bin/reflex /tmp/repro_a1
set -eu
BIN=$1; WORK=$2
APP=$WORK/rapp
mkdir -p "$APP/rapp" "$APP/assets" "$WORK/logs"
cat > "$APP/rxconfig.py" <<'PY'
import reflex as rx

config = rx.Config(app_name="rapp", telemetry_enabled=False)
PY
: > "$APP/rapp/__init__.py"
cat > "$APP/rapp/rapp.py" <<'PY'
import reflex as rx


def index():
    return rx.text("hello")


app = rx.App()
app.add_page(index)
PY
cat > "$WORK/normalize_pkgjson.py" <<'PY'
from pathlib import Path

import reflex

assert "/envs/" in reflex.__file__, reflex.__file__
from reflex.utils import frontend_skeleton as fs  # noqa: E402

p = Path(".web/package.json")
before = p.read_text()
p.write_text(fs._compile_package_json())
print("normalized (was different):", before != p.read_text() or True)
PY

PY_BIN=$(dirname "$BIN")/python
cd "$APP"
echo "### phase 1: three compiles, nothing changed between them"
for i in 1 2 3; do
  REFLEX_TELEMETRY_ENABLED=false "$BIN" compile --loglevel debug > "$WORK/logs/compile_$i.log" 2>&1
  printf '  compile %s: reinstall=%s cache_hit=%s bun_invocations=%s\n' "$i" \
    "$(grep -c 'Installing frontend packages' "$WORK/logs/compile_$i.log")" \
    "$(grep -c 'Using cached value for _install_frontend_packages' "$WORK/logs/compile_$i.log")" \
    "$(grep -c 'Running command.*bun' "$WORK/logs/compile_$i.log")"
done
echo "### why: .web/package.json (written by bun) vs what reflex renders"
"$PY_BIN" - <<'PY'
import json
from pathlib import Path

import reflex

from reflex.utils import frontend_skeleton as fs

disk = Path(".web/package.json").read_text()
rendered = fs._compile_package_json()
print("  byte-identical:", disk == rendered, " JSON-equal:", json.loads(disk) == json.loads(rendered))
print("  on disk :", disk.count("\n") + 1, "lines (bun, 2-space indent)")
print("  rendered:", rendered.count("\n") + 1, "line  (json.dumps, compact)")
PY
echo "### phase 2: normalise the formatting only, then compile twice more"
"$PY_BIN" "$WORK/normalize_pkgjson.py" > /dev/null
for i in 4 5; do
  REFLEX_TELEMETRY_ENABLED=false "$BIN" compile --loglevel debug > "$WORK/logs/compile_$i.log" 2>&1
  printf '  compile %s: reinstall=%s cache_hit=%s bun_invocations=%s\n' "$i" \
    "$(grep -c 'Installing frontend packages' "$WORK/logs/compile_$i.log")" \
    "$(grep -c 'Using cached value for _install_frontend_packages' "$WORK/logs/compile_$i.log")" \
    "$(grep -c 'Running command.*bun' "$WORK/logs/compile_$i.log")"
done
echo "### phase 3: backend-only config change with the cache alive (this is what #7050 promises)"
cat > "$APP/rxconfig.py" <<'PY'
import reflex as rx

config = rx.Config(
    app_name="rapp",
    telemetry_enabled=False,
    backend_host="0.0.0.0",
    cors_allowed_origins=["http://localhost:3000"],
)
PY
REFLEX_TELEMETRY_ENABLED=false "$BIN" compile --loglevel debug > "$WORK/logs/compile_6_backendcfg.log" 2>&1
printf '  compile 6: reinstall=%s cache_hit=%s bun_invocations=%s\n' \
  "$(grep -c 'Installing frontend packages' "$WORK/logs/compile_6_backendcfg.log")" \
  "$(grep -c 'Using cached value for _install_frontend_packages' "$WORK/logs/compile_6_backendcfg.log")" \
  "$(grep -c 'Running command.*bun' "$WORK/logs/compile_6_backendcfg.log")"
echo "### expected on 0.9.11a1: phase 1 = 0 cache hits, phase 2/3 = cache hit + 0 bun runs"
