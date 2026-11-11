#!/usr/bin/env bash
# Deploy retry / instance-bounds matrix (#7463, #7452) through deploy_driver.py against the fake control plane.
# Usage: CP_PORT=8260 deploy_matrix.sh <new|prev> [only-label]
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
ROOT=$SB/apps/cloud_cli
V=$1; ONLY=${2:-}
export CP_PORT=${CP_PORT:-8260}
APP=00000000-0000-0000-0000-000000000a01
DEP=00000000-0000-0000-0000-00000000d001
BASE_KW="\"app_id\": \"$APP\", \"token\": \"good-token\""
KW="{$BASE_KW}"
KW_BOUNDS="{$BASE_KW, \"min_instances\": 1, \"max_instances\": 2}"
KW_INTERACTIVE="{$BASE_KW, \"interactive\": true}"
SCALING='{"status":409,"headers":{"x-reflex-error-code":"app_scaling"},"json":{"detail":"The scale is finishing."}}'
LEGACY='{"status":409,"headers":{"x-reflex-error-code":"app_busy"},"json":{"detail":"the app is currently being scaled; wait for the scale to finish, then deploy again"}}'
BUSY_OTHER='{"status":409,"headers":{"x-reflex-error-code":"app_busy"},"json":{"detail":"a deployment is already in progress for this app"}}'
OK_SUBMIT="{\"status\":200,\"json\":\"$DEP\"}"
BSCALING='{"status":409,"headers":{"x-reflex-error-code":"instance_bounds_scale_conflict"},"json":{"detail":"The scale is finishing."}}'
BOK='{"status":200,"json":{"status":"ok","applied_now":false}}'
BOUNDS_KEY="POST apps/$APP/instance_bounds"
run() { # label kwargs scenario [extra env...]
  local label=$1 kw=$2 sc=$3; shift 3
  if [ -n "$ONLY" ] && [ "$ONLY" != "$label" ]; then return; fi
  SCENARIO="$sc" $ROOT/run_driver.sh $V $label "$kw" "$@"
}
run d01-scaling-retry2       "$KW" "{\"responses\":{\"POST deployments\":[$SCALING,$SCALING,$OK_SUBMIT]}}"
run d02-legacy-busy-detail   "$KW" "{\"responses\":{\"POST deployments\":[$LEGACY,$OK_SUBMIT]}}"
run d03-busy-other           "$KW" "{\"responses\":{\"POST deployments\":[$BUSY_OTHER]}}"
run d04-submit-500           "$KW" '{"responses":{"POST deployments":[{"status":500,"headers":{"x-reflex-error-code":"app_scaling"},"json":{"detail":"internal"}}]}}'
run d05-submit-drop          "$KW" '{"responses":{"POST deployments":[{"drop":true}]}}'
run d07-bounds-retry2        "$KW_BOUNDS" "{\"responses\":{\"$BOUNDS_KEY\":[$BSCALING,$BSCALING,$BOK]}}"
run d08-bounds-500           "$KW_BOUNDS" "{\"responses\":{\"$BOUNDS_KEY\":[{\"status\":500,\"json\":{\"detail\":\"internal\"}}]}}"
run d09-bounds-undecodable   "$KW_BOUNDS" "{\"responses\":{\"$BOUNDS_KEY\":[{\"status\":200,\"json\":\"ok\"}]}}"
run d10-bounds-400           "$KW_BOUNDS" "{\"responses\":{\"$BOUNDS_KEY\":[{\"status\":400,\"json\":{\"detail\":\"min_instances must be <= max_instances\"}}]}}"
run d11-bounds-drop          "$KW_BOUNDS" "{\"responses\":{\"$BOUNDS_KEY\":[{\"drop\":true}]}}"
run d12-bounds-ok-submit-busy "$KW_BOUNDS" "{\"responses\":{\"POST deployments\":[$BUSY_OTHER]}}"
CP_PREFIX=/proxy/v2  run d13-prefix-scaling-retry  "$KW" "{\"responses\":{\"POST deployments\":[$SCALING,$OK_SUBMIT]}}"
CP_PREFIX=/proxy/v2/ run d14-prefix-slash-scaling  "$KW" "{\"responses\":{\"POST deployments\":[$SCALING,$OK_SUBMIT]}}"
CP_PREFIX=/proxy/v2  run d15-prefix-bounds-retry   "$KW_BOUNDS" "{\"responses\":{\"$BOUNDS_KEY\":[$BSCALING,$BOK]}}"
run d16-interactive-gcp-probe "$KW_INTERACTIVE" '{}'
run d17-submit-429-then-ok   "$KW" "{\"responses\":{\"POST deployments\":[{\"status\":429,\"headers\":{\"Retry-After\":\"1\"},\"json\":{\"detail\":\"slow\"}},$SCALING,$OK_SUBMIT]}}"
run d18-bounds-scaling-exhaust "$KW_BOUNDS" "{\"responses\":{\"$BOUNDS_KEY\":[$BSCALING]}}"
run d06-submit-scaling-exhaust "$KW" "{\"responses\":{\"POST deployments\":[$SCALING]}}"
