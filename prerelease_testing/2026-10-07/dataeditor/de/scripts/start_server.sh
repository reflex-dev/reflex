#!/usr/bin/env bash
set -euo pipefail
SB=${REFLEX_TEST_SB:?Set REFLEX_TEST_SB to isolated scratch root}
TRAIN=${1:?alpha2, alpha, or stable}
MODE=${2:-dev}
FP=${3:?Reserved frontend port}
BP=${4:?Reserved backend port}
ROOT="$SB/apps/dataeditor"
APP="$ROOT/$TRAIN-$MODE"
if [ ! -d "$APP" ]; then
  cp -R "$ROOT/source" "$APP"
fi
mkdir -p "$ROOT/logs"
cd "$APP"
export REFLEX_EXPECT_ENV="$SB/envs/$TRAIN"
export REFLEX_TELEMETRY_ENABLED=false
export UV_CACHE_DIR="$SB/uv-cache"
if [ "$MODE" = prod ]; then
  export CLUSTER_API_URL="http://localhost:$BP"
fi
exec uv --no-config run --no-project --python "$SB/envs/$TRAIN/bin/python" reflex run --env "$MODE" --frontend-port "$FP" --backend-port "$BP" --loglevel debug
