#!/bin/bash
# Re-run only the second dev case (frontend already compiled once) after fixing the port cleanup.
source "$(dirname "$0")/run_case_lib.sh"
run_case dev_second
echo "=== hot reload case: edit a page while running, expect a trigger=hot_reload tree"
rm -rf $O/dumps/dev_hot; mkdir -p $O/dumps/dev_hot
cd $APP && OTEL_TEST_MODE=programmatic OTEL_DUMP_DIR=$O/dumps/dev_hot setsid $OT/reflex run --frontend-port 3052 --backend-port 8052 --loglevel debug > $O/logs/dev_hot.log 2>&1 &
n=0; until curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:3052/ 2>/dev/null | grep -q '^200$'; do n=$((n+1)); [ $n -ge 240 ] && break; sleep 1; done; echo "[dev_hot] 200 after ${n}s"; sleep 3
sed -i 's/rx.heading("otel test app")/rx.heading("otel test app HOTRELOAD")/' otelapp/otelapp.py; sleep 12
curl -s --noproxy '*' http://localhost:8052/otel/flush >/dev/null; sleep 6
for p in $(python3 $SB/bin/ports.py 3052 8052 | grep -oE 'pids=[0-9,]+' | cut -d= -f2 | tr ',' ' '); do pkill -KILL -P $p 2>/dev/null; kill -KILL $p 2>/dev/null; done
sed -i 's/rx.heading("otel test app HOTRELOAD")/rx.heading("otel test app")/' otelapp/otelapp.py
echo "[dev_hot] triggers:"; grep -hoE '"reflex.compile.trigger": "[a-z_]+"' $O/dumps/dev_hot/spans-*.jsonl | sort | uniq -c
$OT/python $O/scripts/spantree.py "$O/dumps/dev_hot/spans-*.jsonl" > $O/logs/dev_hot-spantree.txt 2>&1; grep -c 'reflex.compile' $O/logs/dev_hot-spantree.txt
python3 $SB/bin/ports.py 3052 8052 && echo "ports free at end"
echo "SECOND DONE"
