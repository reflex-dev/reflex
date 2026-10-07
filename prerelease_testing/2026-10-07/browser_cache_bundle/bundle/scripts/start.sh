#!/usr/bin/env bash
set -euo pipefail
SB=${REFLEX_TEST_SB:?Set scratch root}
TRAIN=${1:?alpha2,alpha,stable}
LAZY=${2:?0 or1}
PORT=${3:?Reserved production port}
ROOT="$SB/apps/browser-bundle"
APP="$ROOT/$TRAIN-lazy$LAZY"
if [ ! -d "$APP" ]; then cp -R "$ROOT/source" "$APP"; fi
cd "$APP"
export REFLEX_EXPECT_ENV="$SB/envs/forms-$TRAIN"
export REFLEX_TELEMETRY_ENABLED=false
export BUNDLE_API_URL="http://localhost:$PORT"
export BUNDLE_LAZY="$LAZY"
export UV_CACHE_DIR="$SB/uv-cache"
exec uv --no-config run --no-project --python "$REFLEX_EXPECT_ENV/bin/python" reflex run --env prod --frontend-port "$PORT" --backend-port "$PORT" --loglevel debug
