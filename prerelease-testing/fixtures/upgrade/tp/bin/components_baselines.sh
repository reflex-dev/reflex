#!/bin/bash
# tp_components dev baselines for several venvs: components_baselines.sh "<venv>:<label> ..." (default "$NEW:new $PREV:prev")
# Each: fresh copy of apps/tp_components in run/<label>/, dev 3463/8463, drivers/drive_components.py -> out/components/<label>-dev-*.
. "$(dirname "$0")/../../bin/env.sh"; W=$(cd "$(dirname "$0")/.." && pwd)
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
mkdir -p $W/out/components $W/logs
for pair in ${1:-$NEW:new $PREV:prev}; do
  V=${pair%%:*}; L=${pair#*:}; R=$W/run/$L/tp_components
  rm -rf $R; mkdir -p $W/run/$L; cp -r $W/apps/tp_components $R
  $W/bin/start_app.sh $V $R 3463 8463 $W/logs/tp_components-$L-dev-full.log >/dev/null
  $W/bin/wait_up.sh http://localhost:3463/ 400 $W/pids/tp_components-$V.pid >/dev/null
  sleep 4
  (cd $W/drivers; timeout 600 $DPY drive_components.py http://localhost:3463 $W/out/components $L-dev > $W/out/components/$L-dev-stdout.txt 2>&1); tail -2 $W/out/components/$L-dev-stdout.txt
  $W/bin/stop_app.sh $W/pids/tp_components-$V.pid >/dev/null
  sleep 1
done
