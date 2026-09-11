#!/bin/bash
# repro_paid_gate.sh <venv-name>   e.g. ent (0.9.11a1+rxe0.9.5) | entbase (0.9.10.post2+rxe0.9.5)
# Minimal repro for the reflex-enterprise prod/export paid-tier gate:
#   - the refusal is preceded by a reflex-base `console.error` DeprecationWarning
#   - the refusal exits with status 0 (no artifacts produced)
#   - the same warning precedes the dev-mode login gate (logged out, no CI)
#   - APP_HARNESS_FLAG=1 is the only non-paid escape hatch
# Requires: no reflex login token on the machine (anonymous tier).
set -u
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
VENV=${1:-ent}
APP=$(dirname "$0")/../minimal_rxe
cd "$APP" || exit 1
export REFLEX_TELEMETRY_ENABLED=false

echo "### venv=$VENV  reflex=$("$SB/envs/$VENV/bin/python" -c 'import importlib.metadata as m;print(m.version("reflex"))')  rxe=$("$SB/envs/$VENV/bin/python" -c 'import importlib.metadata as m;print(m.version("reflex-enterprise"))')"

echo; echo "### 1. reflex run --env prod  (CI=true, logged out) ###"
CI=true timeout 600 "$SB/envs/$VENV/bin/reflex" run --env prod --frontend-port 6124 --backend-port 6124
echo "EXIT=$?"

echo; echo "### 2. reflex export --no-zip  (CI=true, logged out) ###"
CI=true timeout 600 "$SB/envs/$VENV/bin/reflex" export --no-zip
echo "EXIT=$?"
ls -1 ./*.zip .web/build 2>/dev/null || echo "(no export artifacts)"

echo; echo "### 3. reflex run  (dev, logged out, NO CI -> rxe login gate) ###"
timeout 300 "$SB/envs/$VENV/bin/reflex" run --frontend-port 6125 --backend-port 10525
echo "EXIT=$?"

echo; echo "### 4. APP_HARNESS_FLAG=1 prod (escape hatch) — starts a real server, Ctrl-C / kill it ###"
echo "APP_HARNESS_FLAG=1 CI=true $SB/envs/$VENV/bin/reflex run --env prod --frontend-port 6124 --backend-port 6124"
