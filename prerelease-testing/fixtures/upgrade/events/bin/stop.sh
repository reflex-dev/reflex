#!/bin/bash
# Usage: stop.sh <label>  -- kills the reflex process group and the proxy for a run.
W=$(cd "$(dirname "$0")/.." && pwd)
L=$1
if [ -f "$W/pids/$L.reflex.pid" ]; then
  P=$(cat "$W/pids/$L.reflex.pid")
  kill -TERM -- -$P 2>/dev/null; sleep 3; kill -KILL -- -$P 2>/dev/null
fi
[ -f "$W/pids/$L.proxy.pid" ] && kill $(cat "$W/pids/$L.proxy.pid") 2>/dev/null
sleep 1
bash "$W/../bin/ports.sh" $(seq 3460 3479) $(seq 8460 8479)
