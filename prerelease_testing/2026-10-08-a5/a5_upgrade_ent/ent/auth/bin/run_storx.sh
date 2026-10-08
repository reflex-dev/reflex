#!/usr/bin/env bash
# Usage: run_storx.sh <venv>:<appdir>:<label> ...   (dev, Redis; one server at a time)
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent/ent/auth
for spec in "$@"; do
  IFS=: read V A L <<< "$spec"
  $W/bin/stop_app.sh > /dev/null; redis-cli -p 8629 flushall > /dev/null
  $W/bin/start_app.sh $V $A dev $W/logs/$L-storx.server.log
  $W/bin/wait_ready.sh http://localhost:3620/ http://localhost:8620 400 || continue
  (cd $W/drivers && env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 900 $SB/envs/driver/bin/python storx.py http://localhost:3620 $L 2 > $W/logs/$L-storx.out 2>&1)
  echo "$L tracebacks: $(grep -c Traceback $W/logs/$L-storx.server.log)"
done
$W/bin/stop_app.sh > /dev/null
echo RUN_STORX_DONE
