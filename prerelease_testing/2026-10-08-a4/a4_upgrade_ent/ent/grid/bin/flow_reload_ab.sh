#!/usr/bin/env bash
# N-026 context: alternate a4-ent / a3-ent flow demo prod servers (3478) and run scripts/probe_flow_reload.py <N> times on each.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; GW=$SB/apps/a4_upgrade_ent/ent/grid; cd $GW
N=${1:-4}; export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
for V in ${ORDER:-a4-ent a3-ent}; do
  RUN=$GW/runs/flow_demo_${V//-/}
  bin/start.sh $V $RUN $GW/logs/flow-reload-$V.log prod 3478 3478 > /dev/null || { bin/stop.sh; continue; }
  for i in $(seq 1 $N); do
    $SB/envs/driver/bin/python scripts/probe_flow_reload.py http://localhost:3478 out/flow_reload_$V $V ${TAG:-}r$i > out/flow_reload_$V-${TAG:-}r$i.txt 2>&1
    echo "$V r$i: $(grep -E '^\[(PASS|FAIL)' out/flow_reload_$V-${TAG:-}r$i.txt | tr '\n' ' ' | cut -c1-260)"
  done
  bin/stop.sh > /dev/null
done
