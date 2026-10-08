#!/bin/bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a4_upgrade_ent/tp
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
cd $W
for pair in "thirdparty-alpha a1" "thirdparty-stable s0912"; do
  set -- $pair; V=$1; L=$2
  cp apps/tp_components/tp_components/tp_components.py run/$L/tp_components/tp_components/tp_components.py
  ./bin/start_app.sh $V $W/run/$L/tp_components 3463 8463 $W/logs/tp_components-$L-dev-full.log >/dev/null
  ./bin/wait_up.sh http://localhost:3463/ 400 $W/pids/tp_components-$V.pid >/dev/null
  sleep 4
  (cd drivers; timeout 600 $SB/envs/driver/bin/python drive_components.py http://localhost:3463 $W/out/components $L-dev > $W/out/components/$L-dev-stdout.txt 2>&1)
  ./bin/stop_app.sh $W/pids/tp_components-$V.pid >/dev/null
  sleep 1
done
echo done > $W/logs/components_baselines.done
