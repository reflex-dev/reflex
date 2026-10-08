#!/bin/bash
# bisect.sh <venv> <BISECT flags> : start rtr dev with RTR_BISECT, print dispatch errors on /, stop
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_hydration_router
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"
$W/scripts/srv.sh start rtr-a5dev-t $1 dev $W/src/rtr 3142 8142 RTR_BISECT=$2 >/dev/null
$NP $SB/envs/driver/bin/python $W/drivers/waitsrv.py 300 http://localhost:3142/ http://localhost:8142/ping >/dev/null; sleep 3
echo "== $1 $2"; $NP $SB/envs/driver/bin/python $W/drivers/dbg_console.py http://localhost:3142/ 4 2>&1 | grep -E "error|PAGEERROR" | cut -c1-200
$W/scripts/srv.sh stop rtr-a5dev-t >/dev/null
