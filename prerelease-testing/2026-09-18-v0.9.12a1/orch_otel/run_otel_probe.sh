#!/bin/bash
# #7155 probe: is the initial dev `reflex.compile` span tree exported now? (prev campaign FINDING-028 said it was lost)
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
O=$SB/apps/orch_otel; APP=$O/otelapp; OT=$SB/envs/otel/bin; DRV=$SB/envs/driver/bin/python
export REFLEX_TELEMETRY_ENABLED=false
run_case() { # name  env-assignments...
  local name=$1; shift
  rm -rf $O/dumps/$name $APP/.web/_compile_marker 2>/dev/null; mkdir -p $O/dumps/$name
  cd $APP && env "$@" OTEL_TEST_MODE=programmatic OTEL_DUMP_DIR=$O/dumps/$name setsid $OT/reflex run --frontend-port 3052 --backend-port 8052 --loglevel debug > $O/logs/$name.log 2>&1 & local pid=$!
  local n=0; until curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:3052/ 2>/dev/null | grep -q '^200$'; do n=$((n+1)); [ $n -ge 360 ] && { echo "TIMEOUT $name"; break; }; sleep 1; done; echo "[$name] frontend 200 after ${n}s"
  sleep 2
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $DRV /home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py http://localhost:3052/ --actions '[{"wait":2500}]' --report $O/logs/$name-drive.json > $O/logs/$name-drive.txt 2>&1; echo "[$name] drive exit=$? $(grep -c . $O/logs/$name-drive.txt) lines"
  curl -s --noproxy '*' http://localhost:8052/otel/flush; echo
  sleep 6   # let the batch processor timer fire in any surviving process
  pkill -TERM -P $pid 2>/dev/null; kill -TERM $pid 2>/dev/null; sleep 4; pkill -KILL -P $pid 2>/dev/null; kill -KILL $pid 2>/dev/null
  for p in $(python3 /tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad/bin/ports.py 3052 8052 | grep -oE 'pids=[0-9,]+' | cut -d= -f2 | tr ',' ' '); do pkill -KILL -P $p 2>/dev/null; kill -KILL $p 2>/dev/null; done
  echo "[$name] span files: $(ls $O/dumps/$name/ | tr '\n' ' ')"
  $OT/python $O/scripts/spantree.py "$O/dumps/$name/spans-*.jsonl" > $O/logs/$name-spantree.txt 2>&1
  echo "[$name] reflex.compile spans by trigger:"; grep -hoE '"reflex.compile.trigger": "[a-z_]+"' $O/dumps/$name/spans-*.jsonl | sort | uniq -c
  echo "[$name] compile-tree roots + stage children (from spantree):"; grep -nE 'reflex\.compile' $O/logs/$name-spantree.txt | head -30
  echo "[$name] orphans (parent never exported):"; $OT/python - "$O/dumps/$name" <<'PY'
import json,glob,sys
spans=[json.loads(l) for f in glob.glob(sys.argv[1]+"/spans-*.jsonl") for l in open(f) if l.strip()]
ids={s["context"]["span_id"] for s in spans}
orph=[s for s in spans if s.get("parent_id") and s["parent_id"] not in ids]
print(len(spans),"spans;",len(orph),"orphans:",sorted({s["name"] for s in orph})[:10])
PY
}
echo "=== versions"; $OT/python -c "import reflex, reflex_otel; print(reflex.__file__); print('reflex', reflex.constants.Reflex.VERSION)"
run_case dev_initial
echo "=== cold second run (frontend already compiled; compile still runs in the worker)"; run_case dev_second
echo "=== export --frontend-only (in-process compile, control)"; rm -rf $O/dumps/export; mkdir -p $O/dumps/export; cd $APP && OTEL_TEST_MODE=programmatic OTEL_DUMP_DIR=$O/dumps/export $OT/reflex export --frontend-only --loglevel info > $O/logs/export.log 2>&1; echo "export exit=$?"; grep -hoE '"reflex.compile.trigger": "[a-z_]+"' $O/dumps/export/spans-*.jsonl | sort | uniq -c
echo "OTEL PROBE DONE"
