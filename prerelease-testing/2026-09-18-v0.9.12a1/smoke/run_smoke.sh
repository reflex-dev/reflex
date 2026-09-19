#!/bin/bash
# Phase 1 smoke: blank app, dev + prod, driven in Chromium. PyPI-only shared venv.
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
A=$SB/apps/smoke; RX=$SB/envs/shared/bin/reflex; DRV=$SB/envs/driver/bin/python
DRIVE=/home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py
export REFLEX_TELEMETRY_ENABLED=false
cd $A || exit 1
mkdir -p logs shots
wait_200() { local url=$1 n=0; until curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "$url" 2>/dev/null | grep -q '^200$'; do n=$((n+1)); [ $n -ge 360 ] && { echo "TIMEOUT waiting for $url"; return 1; }; sleep 1; done; echo "200 after ${n}s: $url"; }
killtree() { local pid=$1; pkill -TERM -P $pid 2>/dev/null; kill -TERM $pid 2>/dev/null; sleep 3; pkill -KILL -P $pid 2>/dev/null; kill -KILL $pid 2>/dev/null; }
echo "== versions"; $SB/envs/shared/bin/python -c "import reflex, reflex_base; print(reflex.__file__, reflex.constants.Reflex.VERSION)" 2>&1 | tail -1
echo "== init"; $RX init --template blank --name smoke_app > logs/init.log 2>&1; echo "init exit=$?"; grep -ciE 'error|traceback' logs/init.log
echo "== dev run"; setsid $RX run --loglevel debug --frontend-port 3050 --backend-port 8050 > logs/dev.log 2>&1 & DEVPID=$!
wait_200 http://localhost:3050/ || { echo "DEV FAILED"; tail -40 logs/dev.log; }
sleep 3
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $DRV $DRIVE http://localhost:3050/ --actions '[{"wait":2000},{"expect_text":"Welcome to Reflex"},{"click":"text=Docs"},{"wait":500}]' --screenshot shots/dev_index.png --report logs/dev_report.json; echo "dev drive exit=$?"
curl -s --noproxy '*' http://localhost:8050/ping; echo; curl -s --noproxy '*' -o /dev/null -w 'health %{http_code}\n' http://localhost:8050/_health
killtree $DEVPID; sleep 2; ss -ltnp 2>/dev/null | grep -E ':3050|:8050' && echo "PORT STILL BOUND"
echo "== dev log summary"; grep -nE 'Bun |Node |lockfileVersion|warn|error|Error|Traceback' logs/dev.log | grep -v 'npmmirror' | head -40
cp .web/package.json logs/web_package.json 2>/dev/null; echo "== package.json pins"; python3 -c "import json;d=json.load(open('logs/web_package.json'));print(json.dumps(d.get('dependencies',{}),indent=0));print('overrides',d.get('overrides'))" 2>&1 | head -60
echo "== prod run"; setsid $RX run --env prod --loglevel debug --frontend-port 3051 --backend-port 3051 > logs/prod.log 2>&1 & PRODPID=$!
wait_200 http://localhost:3051/ || { echo "PROD FAILED"; tail -40 logs/prod.log; }
sleep 3
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $DRV $DRIVE http://localhost:3051/ --actions '[{"wait":2000},{"expect_text":"Welcome to Reflex"}]' --screenshot shots/prod_index.png --report logs/prod_report.json; echo "prod drive exit=$?"
killtree $PRODPID; sleep 2; ss -ltnp 2>/dev/null | grep -E ':3051' && echo "PORT STILL BOUND"
echo "== prod log summary"; grep -nE 'warn|error|Error|Traceback' logs/prod.log | grep -v npmmirror | head -20
echo "== leftover procs"; ps aux | grep -E 'reflex run|vite|granian' | grep -v grep | head
echo "== resolution check: bare reflex==0.9.12a1 with --prerelease=allow"; cd $SB && uv venv $SB/envs/tmp_resolve --python 3.11 >/dev/null 2>&1 && uv pip install --python $SB/envs/tmp_resolve/bin/python --prerelease=allow --dry-run 'reflex==0.9.12a1' 2>&1 | grep -iE '^ \+ reflex' ; echo "== resolution: pip-style without prerelease flag (should fail to find 0.9.12a1)"; uv pip install --python $SB/envs/tmp_resolve/bin/python --dry-run 'reflex==0.9.12a1' 2>&1 | tail -3; rm -rf $SB/envs/tmp_resolve
echo "SMOKE DONE"
