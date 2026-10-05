#!/bin/bash
# --backend-only + --frontend-only pairing on a2
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/reverify/rv_devserver_badge
export REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=http://localhost:8228
nap() { python3 -c "import time,sys;time.sleep(float(sys.argv[1]))" "$1"; }
cd $W/apps/dsc_a2 || exit 1
setsid $SB/envs/a2/bin/reflex run --backend-only --backend-port 8228 --loglevel debug > $W/logs/split_backend.log 2>&1 &
BPID=$!; echo "BPID=$BPID"
n=0; until curl -s --noproxy '*' -m 3 -o /dev/null -w '%{http_code}' http://localhost:8228/ping 2>/dev/null | grep -q '^200$'; do n=$((n+1)); [ $n -ge 240 ] && { echo "BACKEND TIMEOUT"; break; }; nap 1; done; echo "backend /ping 200 after ${n}s"
echo "nocompile_exists=$([ -f .web/nocompile ] && echo yes || echo no)"
setsid $SB/envs/a2/bin/reflex run --frontend-only --frontend-port 3228 --loglevel debug > $W/logs/split_frontend.log 2>&1 &
FPID=$!; echo "FPID=$FPID"
n=0; until curl -s --noproxy '*' -m 3 -o /dev/null -w '%{http_code}' http://localhost:3228/ 2>/dev/null | grep -q '^200$'; do n=$((n+1)); [ $n -ge 150 ] && { echo "FRONTEND TIMEOUT"; break; }; nap 1; done; echo "frontend 200 after ${n}s"
nap 3
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python \
  /home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py http://localhost:3228/ \
  --actions '[{"wait":2500},{"expect_text":"dsc v5-reload"},{"click":"#inc"},{"wait":900},{"click":"#add"},{"wait":900}]' \
  --screenshot $W/shots/split-frontend.png --report $W/out/split_a2.json
echo "drive exit=$?"
kill -TERM -$FPID 2>/dev/null; kill -TERM -$BPID 2>/dev/null; nap 4
kill -KILL -$FPID 2>/dev/null; kill -KILL -$BPID 2>/dev/null; nap 2
echo "== ports after =="; cd $SB && uv run --no-project python $SB/bin/ports.py 3228 8228 2>&1 | grep -v UV_NATIVE; echo "(empty=free)"
echo "SPLIT DONE"
