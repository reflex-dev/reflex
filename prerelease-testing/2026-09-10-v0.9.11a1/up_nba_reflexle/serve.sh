#!/bin/bash
# Start a reflex-examples app for the up_upload_traversal_quiz upgrade cluster and wait for the
# frontend to answer 200.
#
# usage: serve.sh <app_dir> <venv_dir> <frontend_port> <backend_port> <log_path> [extra `reflex run` args]
#   e.g. serve.sh $SB/apps/up_upload_traversal_quiz/quiz $SB/envs/up_upload_traversal_quiz_quiz 4142 9142 logs/run_0910.log
#        serve.sh ... 4142 4142 logs/run_0911_prod.log --env prod      (prod: SAME port for both)
#
# Environment choices (deliberate, see NOTES.md):
#   REFLEX_DIR=$SB/reflex_dirs/<app>   isolates reflex's own bun install per app, so the 0.9.10.post2
#                                      baseline picks the system bun 1.3.11 from PATH (min 1.3.0) and the
#                                      0.9.11a1 run performs the real bun 1.4.0 install/migration itself,
#                                      instead of reusing a bun 1.4.0 another agent's alpha run left in
#                                      ~/.local/share/reflex.
#   REFLEX_TELEMETRY_ENABLED=false     no telemetry.
#   NO_PROXY is NOT exported into the server env (it breaks bun installs through the proxy); only curl
#   (client side) bypasses the proxy.
# The server is started with setsid so `stop.sh` can kill the whole process group (reflex + bun + node).
set -u
APP=$1; VENV=$2; FP=$3; BP=$4; LOG=$5; shift 5
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
cd "$APP" || exit 2
mkdir -p logs
REFLEX_DIR="$SB/reflex_dirs/$(basename "$APP")" REFLEX_TELEMETRY_ENABLED=false \
  setsid "$VENV/bin/reflex" run --frontend-port "$FP" --backend-port "$BP" --loglevel debug "$@" > "$LOG" 2>&1 &
PID=$!
echo "$PID" > logs/server.pid
echo "started reflex pid/pgid=$PID log=$LOG"
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --noproxy '*' "http://localhost:$FP/" 2>/dev/null)
  if [ "$code" = "200" ]; then echo "UP (HTTP 200) after ~$((i*5))s"; exit 0; fi
  if ! kill -0 "$PID" 2>/dev/null; then echo "SERVER EXITED"; tail -40 "$LOG"; exit 1; fi
  sleep 5
done
echo "TIMEOUT waiting for http://localhost:$FP/"; tail -40 "$LOG"; exit 1
