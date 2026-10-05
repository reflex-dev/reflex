#!/bin/bash
# Phase 7 re-verify smoke: blank app, dev + prod, driven in Chromium. a2 venv, PyPI-only.
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/reverify/rv_devserver_badge
A=$W/apps/smoke; RX=$SB/envs/a2/bin/reflex; DRV=$SB/envs/driver/bin/python
DRIVE=/home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py
export REFLEX_TELEMETRY_ENABLED=false
mkdir -p $A $W/logs $W/shots
cd $A || exit 1
nap() { python3 -c "import time,sys;time.sleep(float(sys.argv[1]))" "$1"; }
wait_200() { local url=$1 n=0; until curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "$url" 2>/dev/null | grep -q '^200$'; do n=$((n+1)); [ $n -ge 360 ] && { echo "TIMEOUT waiting for $url"; return 1; }; nap 1; done; echo "200 after ${n}s: $url"; }
echo "== versions"; $SB/envs/a2/bin/python -c "import reflex; print(reflex.__file__, reflex.constants.Reflex.VERSION)" 2>&1 | tail -1
echo "== init"; $RX init --template blank --name smoke_app > $W/logs/init.log 2>&1; echo "init exit=$?"; echo "err-ish lines: $(grep -ciE 'error|traceback' $W/logs/init.log)"
echo "== dev run"; setsid $RX run --loglevel debug --frontend-port 3220 --backend-port 8220 > $W/logs/dev.log 2>&1 & DEVPID=$!
echo "DEVPID=$DEVPID"
wait_200 http://localhost:3220/ || { echo "DEV FAILED"; tail -40 $W/logs/dev.log; }
nap 3
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $DRV $DRIVE http://localhost:3220/ --actions '[{"wait":2000},{"expect_text":"Welcome to Reflex"},{"click":"text=Docs"},{"wait":500}]' --screenshot $W/shots/smoke_dev_index.png --report $W/logs/smoke_dev_report.json; echo "dev drive exit=$?"
echo -n "ping: "; curl -s --noproxy '*' http://localhost:8220/ping; echo; curl -s --noproxy '*' -o /dev/null -w 'health %{http_code}\n' http://localhost:8220/_health
cp .web/package.json $W/logs/web_package_a2.json 2>/dev/null
kill -TERM -$DEVPID 2>/dev/null; nap 4; kill -KILL -$DEVPID 2>/dev/null; nap 1
echo "== ports after dev"; uv run --no-project python $SB/bin/ports.py 3220 8220 2>&1 | tail -5
echo "== dev log summary"; grep -nE 'Bun |Node |lockfileVersion|warn|error|Error|Traceback' $W/logs/dev.log | grep -v 'npmmirror' | head -40
echo "== prod run"; setsid $RX run --env prod --loglevel debug --frontend-port 3221 --backend-port 3221 > $W/logs/prod.log 2>&1 & PRODPID=$!
echo "PRODPID=$PRODPID"
wait_200 http://localhost:3221/ || { echo "PROD FAILED"; tail -40 $W/logs/prod.log; }
nap 3
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $DRV $DRIVE http://localhost:3221/ --actions '[{"wait":2000},{"expect_text":"Welcome to Reflex"}]' --screenshot $W/shots/smoke_prod_index.png --report $W/logs/smoke_prod_report.json; echo "prod drive exit=$?"
kill -TERM -$PRODPID 2>/dev/null; nap 4; kill -KILL -$PRODPID 2>/dev/null; nap 1
echo "== ports after prod"; uv run --no-project python $SB/bin/ports.py 3221 2>&1 | tail -5
echo "== prod log summary"; grep -nE 'warn|error|Error|Traceback' $W/logs/prod.log | grep -v npmmirror | head -20
echo "SMOKE DONE"
