#!/usr/bin/env bash
# Run deploy_driver.py (hosting CLI deploy() with canned archives) against the fake control plane.
# Usage: run_driver.sh <new|prev> <label> '<json kwargs>' [VAR=val ...]
# Env: CP_PORT (default 8260), CP_PREFIX (e.g. /proxy/v2), SCENARIO (stub scenario JSON), ARCHIVES (dir with the zips)
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
ROOT=$SB/apps/cloud_cli
VENV_NAME=$1; LABEL=$2; KWARGS=$3; shift 3
VENV=$SB/envs/cloud_cli-$VENV_NAME
CP_PORT=${CP_PORT:-8260}
CP_PREFIX=${CP_PREFIX:-}
ARCHIVES=${ARCHIVES:-$ROOT/archives/$VENV_NAME}
mkdir -p $ROOT/logs $ROOT/xdg-$VENV_NAME
printf '%s' "${SCENARIO:-{\}}" > $ROOT/logs/$LABEL.$VENV_NAME.scenario.json
curl -sS --noproxy '*' -X POST -H 'Content-Type: application/json' --data-binary @$ROOT/logs/$LABEL.$VENV_NAME.scenario.json http://127.0.0.1:$CP_PORT/__control/reset > $ROOT/logs/$LABEL.$VENV_NAME.scenario.ack || { echo "scenario POST failed"; exit 98; }
cd $ROOT/app-$VENV_NAME
start=$(date +%s.%N)
env REFLEX_TELEMETRY_ENABLED=false REFLEX_CHECK_LATEST_VERSION=false XDG_DATA_HOME=$ROOT/xdg-$VENV_NAME \
    REFLEX_CLOUD_BACKEND_URL=http://127.0.0.1:$CP_PORT$CP_PREFIX REFLEX_CLOUD_URL=http://127.0.0.1:$CP_PORT$CP_PREFIX \
    EXPECT_VENV=cloud_cli-$VENV_NAME "$@" \
    $VENV/bin/python -I $ROOT/deploy_driver.py $ARCHIVES "$KWARGS" > $ROOT/logs/$LABEL.$VENV_NAME.out 2> $ROOT/logs/$LABEL.$VENV_NAME.err < /dev/null
rc=$?
end=$(date +%s.%N)
echo $rc > $ROOT/logs/$LABEL.$VENV_NAME.rc
curl -sS --noproxy '*' http://127.0.0.1:$CP_PORT/__control/log > $ROOT/logs/$LABEL.$VENV_NAME.requests.json
printf '[%s/%s] rc=%s elapsed=%.1fs\n' "$LABEL" "$VENV_NAME" "$rc" "$(echo "$end - $start" | bc)"
