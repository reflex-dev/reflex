#!/usr/bin/env bash
# N-026 A/B: alternate flow-demo prod servers (3608) per venv and run scripts/probe_flow_reload.py <N> times on each.
# Usage: ORDER="<venv> <venv>" TAG=<tag> flow_reload_ab.sh [N=4]   (default ORDER="$ENT_NEW ${ENT_PREV:-}"; run demo.sh <venv> flow prod once first)
. "$(dirname "$0")/../../lib.sh"; fx_sync grid; GW=$WORK/grid; B=$FX/grid/bin; cd "$GW"
N=${1:-4}
for V in ${ORDER:-$ENT_NEW ${ENT_PREV:-}}; do
  RUN=$GW/runs/flow_demo_${V//-/}
  [ -d "$RUN" ] || { echo "no $RUN (run bin/demo.sh $V flow prod <label> once)"; continue; }
  "$B/start.sh" $V "$RUN" "$GW/logs/flow-reload-$V.log" prod 3608 3608 > /dev/null || { "$B/stop.sh"; continue; }
  for i in $(seq 1 $N); do
    $NP "$DRVPY" scripts/probe_flow_reload.py http://localhost:3608 out/flow_reload_$V $V ${TAG:-}r$i > out/flow_reload_$V-${TAG:-}r$i.txt 2>&1
    echo "$V r$i: $(grep -E '^\[(PASS|FAIL)' out/flow_reload_$V-${TAG:-}r$i.txt | tr '\n' ' ' | cut -c1-260)"
  done
  "$B/stop.sh" > /dev/null
done
