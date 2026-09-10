#!/bin/bash
# repro_nocompile.sh <venv> <appdir> <fp> <bp> <label>
# Shows that `reflex run --backend-only` leaves .web/nocompile behind and that the NEXT full `reflex run` then skips the
# frontend compile (a deleted compiled page is not regenerated), serving a stale frontend.
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/event_hotpath
LOGDIR=${LOGDIR:-logs3}
venv=$1; appdir=$2; fp=$3; bp=$4; label=$5
export REFLEX_TELEMETRY_ENABLED=false
cd $A/$appdir || exit 1
echo "### $label: reflex $($SB/envs/$venv/bin/python -c 'import reflex;print(reflex.constants.Reflex.VERSION)' 2>/dev/null) in $appdir"
rm -f .web/nocompile
echo "step1 marker before backend-only run: $(ls .web/nocompile 2>/dev/null || echo absent)"
setsid nohup $SB/envs/$venv/bin/reflex run --backend-only --backend-port $bp --loglevel info > $A/$LOGDIR/nocompile_${label}_backendonly.log 2>&1 &
for i in $(seq 1 120); do curl -s --noproxy '*' -o /dev/null http://localhost:$bp/ping && break; sleep 1; done; sleep 2
pid=$(pgrep -f "reflex run --backend-only --backend-port $bp" | sort -n | head -1); pgid=$(ps -o pgid= -p $pid | tr -d ' ')
echo "step1 marker while backend-only server runs: $(ls -la .web/nocompile 2>/dev/null || echo absent)"
kill -TERM -- -$pgid 2>/dev/null; sleep 3; kill -KILL -- -$pgid 2>/dev/null
echo "step1 marker after backend-only server stopped: $(ls -la .web/nocompile 2>/dev/null || echo absent)   <-- LEAK if present"
page='.web/app/routes/[ordering]._index.jsx'
ls "$page" >/dev/null 2>&1 || page=$(ls .web/app/routes/*.jsx | head -1)
rm -f "$page"; echo "step2 deleted compiled page $page; now a full dev run:"
setsid nohup $SB/envs/$venv/bin/reflex run --frontend-port $fp --backend-port $bp --loglevel info > $A/$LOGDIR/nocompile_${label}_fullrun.log 2>&1 &
sleep 8
for i in $(seq 1 120); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$fp/ 2>/dev/null | grep -q 200 && break; sleep 1; done; sleep 5
pid=$(pgrep -f "reflex run --frontend-port $fp --backend-port $bp" | sort -n | head -1); pgid=$(ps -o pgid= -p $pid | tr -d ' ')
echo "step2 marker during full run: $(ls .web/nocompile 2>/dev/null || echo 'absent (consumed)')"
echo "step2 compiled page regenerated? $(ls "$page" 2>/dev/null || echo 'NO -> frontend compile was skipped')"
echo "step2 GET /ordering -> HTTP $(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$fp/ordering)  body: $(curl -s --noproxy '*' http://localhost:$fp/ordering | grep -o -E '404[^<]{0,40}|Page not found' | head -1)"
grep -c -i "compil" $A/$LOGDIR/nocompile_${label}_fullrun.log | sed 's/^/step2 lines mentioning compile in the run log: /'
kill -TERM -- -$pgid 2>/dev/null; sleep 3; kill -KILL -- -$pgid 2>/dev/null
echo "step3 control: full run again with no marker"
setsid nohup $SB/envs/$venv/bin/reflex run --frontend-port $fp --backend-port $bp --loglevel info > $A/$LOGDIR/nocompile_${label}_fullrun2.log 2>&1 &
sleep 8
for i in $(seq 1 120); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$fp/ 2>/dev/null | grep -q 200 && break; sleep 1; done; sleep 5
pid=$(pgrep -f "reflex run --frontend-port $fp --backend-port $bp" | sort -n | head -1); pgid=$(ps -o pgid= -p $pid | tr -d ' ')
echo "step3 compiled page regenerated? $(ls "$page" 2>/dev/null || echo NO)"
echo "step3 GET /ordering -> HTTP $(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$fp/ordering)"
kill -TERM -- -$pgid 2>/dev/null; sleep 3; kill -KILL -- -$pgid 2>/dev/null
echo "### $label done"
