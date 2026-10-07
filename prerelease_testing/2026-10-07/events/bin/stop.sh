#!/bin/bash
# Usage: stop.sh <label>  -- kills the reflex process group and the proxy for a run.
W=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/events2
L=$1
if [ -f "$W/pids/$L.reflex.pid" ]; then
  P=$(cat "$W/pids/$L.reflex.pid")
  kill -TERM -- -$P 2>/dev/null; sleep 3; kill -KILL -- -$P 2>/dev/null
fi
[ -f "$W/pids/$L.proxy.pid" ] && kill $(cat "$W/pids/$L.proxy.pid") 2>/dev/null
sleep 1
ss -ltnp 2>/dev/null | grep -E ":(34[67][0-9]|84[67][0-9])\b" || echo "ports clear"
