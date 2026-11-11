#!/usr/bin/env bash
# Run a reflex CLI command in one of the cloud_cli venvs against the fake control plane.
# Usage: run_cli.sh <new|prev> <label> [env VAR=val ...] -- <reflex args...>
#   e.g. run_cli.sh new whoami-401 REFLEX_ACCESS_TOKEN=bad -- cloud whoami
# Output: logs/<label>.<venv>.{out,err,rc}; stub request log snapshot in logs/<label>.<venv>.requests.json
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
ROOT=$SB/apps/cloud_cli
VENV_NAME=$1; shift
LABEL=$1; shift
VENV=$SB/envs/cloud_cli-$VENV_NAME
CP_PORT=${CP_PORT:-8260}
CP_PREFIX=${CP_PREFIX:-}
declare -a ENVS=()
while [ "$1" != "--" ]; do ENVS+=("$1"); shift; done; shift
mkdir -p $ROOT/logs $ROOT/xdg-$VENV_NAME
# Guard: the venv that runs this really is the published package set we think it is.
$VENV/bin/python -I -c "import reflex_cli, reflex, importlib.metadata as m; assert '/envs/cloud_cli-$VENV_NAME/' in reflex_cli.__file__, reflex_cli.__file__; assert '/envs/cloud_cli-$VENV_NAME/' in reflex.__file__, reflex.__file__; print('venv ok:', m.version('reflex'), 'hosting-cli', m.version('reflex-hosting-cli'), 'build-sdk', m.version('reflex-build-sdk'))" || exit 99
cd ${CWD:-$ROOT/app-$VENV_NAME}
printf '%s' "${SCENARIO:-{\}}" > $ROOT/logs/$LABEL.$VENV_NAME.scenario.json
# NO_STUB=1: the CLI is pointed at a port nobody listens on (connection refused); nothing to reset.
if [ -z "${NO_STUB:-}" ]; then
  curl -sS --noproxy '*' -X POST -H 'Content-Type: application/json' --data-binary @$ROOT/logs/$LABEL.$VENV_NAME.scenario.json http://127.0.0.1:$CP_PORT/__control/reset > $ROOT/logs/$LABEL.$VENV_NAME.scenario.ack || { echo "scenario POST failed"; exit 98; }
fi
start=$(date +%s.%N)
env REFLEX_TELEMETRY_ENABLED=false REFLEX_CHECK_LATEST_VERSION=false XDG_DATA_HOME=$ROOT/xdg-$VENV_NAME \
    REFLEX_CLOUD_BACKEND_URL=http://127.0.0.1:$CP_PORT$CP_PREFIX REFLEX_CLOUD_URL=http://127.0.0.1:$CP_PORT$CP_PREFIX \
    "${ENVS[@]}" $VENV/bin/reflex "$@" > $ROOT/logs/$LABEL.$VENV_NAME.out 2> $ROOT/logs/$LABEL.$VENV_NAME.err < ${STDIN_FILE:-/dev/null}
rc=$?
end=$(date +%s.%N)
echo $rc > $ROOT/logs/$LABEL.$VENV_NAME.rc
if [ -z "${NO_STUB:-}" ]; then
  curl -sS --noproxy '*' http://127.0.0.1:$CP_PORT/__control/log > $ROOT/logs/$LABEL.$VENV_NAME.requests.json
else
  echo '[]' > $ROOT/logs/$LABEL.$VENV_NAME.requests.json
fi
printf '[%s/%s] rc=%s elapsed=%.1fs\n' "$LABEL" "$VENV_NAME" "$rc" "$(echo "$end - $start" | bc)"
