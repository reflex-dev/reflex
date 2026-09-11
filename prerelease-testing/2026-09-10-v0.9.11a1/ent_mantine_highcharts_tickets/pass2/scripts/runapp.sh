#!/bin/bash
# runapp.sh <appdir> <venv> <dev|prod> <fport> <bport> <label> [extra reflex args...]
# Starts the enterprise demo, waits for the frontend to answer 200, leaves it running.
# Ports are the cluster's reserved range: frontend 5420-5439, backend 9820-9839.
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
E="$SB/apps/ent_mantine_highcharts_tickets"
app=$1; venv=$2; mode=$3; fport=$4; bport=$5; label=$6; shift 6
mkdir -p "$E/logs" "$E/out" "$E/shots"

# free the ports (graceful, then orphan sweep via /proc/net/tcp)
for p in $(ps aux | grep -E "frontend-port $fport|backend-port $bport" | grep -v grep | awk '{print $2}'); do
  kill "$p" 2>/dev/null
done
sleep 3
python3 - "$fport" "$bport" <<'PY'
import glob, os, sys
want = {int(sys.argv[1]), int(sys.argv[2])}
inodes = {}
for line in open('/proc/net/tcp').read().splitlines()[1:]:
    f = line.split(); port = int(f[1].split(':')[1], 16)
    if f[3] == '0A' and port in want:
        inodes[f[9]] = port
for fd in glob.glob('/proc/[0-9]*/fd/*'):
    try:
        t = os.readlink(fd)
    except OSError:
        continue
    if t.startswith('socket:[') and t[8:-1] in inodes:
        try:
            os.kill(int(fd.split('/')[2]), 9)
            print("killed orphan pid", fd.split('/')[2])
        except OSError:
            pass
PY
sleep 1

envflag=""
harness=""
if [ "$mode" = "prod" ]; then
  envflag="--env prod"
  # reflex-enterprise gates `reflex run --env prod` (and `reflex export`) behind a PAID
  # tier: CI=true only bypasses the *login* gate. check_paid_tier_for_command() returns
  # early when reflex's app-harness flag is set, which is the only way to exercise
  # enterprise prod mode without a licence. Its one side effect is TEST_MODE=true in the
  # vite build env (reflex/utils/build.py:25).
  harness="APP_HARNESS_FLAG=1"
fi
LOG="$E/logs/${label}.log"
cd "$E/$app" || exit 1
env $harness CI=true REFLEX_TELEMETRY_ENABLED=false nohup "$SB/envs/$venv/bin/reflex" run $envflag \
  --frontend-port "$fport" --backend-port "$bport" --loglevel debug "$@" > "$LOG" 2>&1 &
echo "started $app ($venv, $mode) pid=$! log=$LOG"

deadline=$(( $(date +%s) + 420 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  code=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "http://localhost:$fport/" 2>/dev/null)
  if [ "$code" = "200" ]; then
    echo "frontend up after $(( $(date +%s) - deadline + 420 ))s"
    break
  fi
  if ! pgrep -f "frontend-port $fport" > /dev/null; then
    echo "SERVER PROCESS GONE — tail of log:"; tail -25 "$LOG"; exit 1
  fi
  sleep 5
done
curl -s --noproxy '*' -o /dev/null -w "front=%{http_code} " "http://localhost:$fport/"
curl -s --noproxy '*' -o /dev/null -w "ping=%{http_code}\n" "http://localhost:$bport/ping"
