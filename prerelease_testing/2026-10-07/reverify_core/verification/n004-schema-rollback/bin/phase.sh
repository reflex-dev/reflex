#!/bin/bash
# Usage: phase.sh <venv> <label> [env FLEET_DEFAULT=..]  -- stop current prod server, start fleet_<venv> prod on 3600 (redis 8603), resume the chain token
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/verify_core_a2
V=$1; L=$2; CH=${CHAIN:-chain}
[ -f $W/pids/prod.pid ] && $W/bin/stop_app.sh $W/pids/prod.pid
$W/bin/prod.sh $V "${CH}-${L//[^A-Za-z0-9._-]/_}" || exit 1
echo "redis keys: $(redis-cli -p 8603 keys '*' | tr '\n' ' ')"
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/drivers/drive_fleet.py http://localhost:3600 $W/out/$CH-token.txt "$L" ${MODE:-resume} $W/out/$CH.jsonl \
  | $SB/envs/driver/bin/python -c "import json,sys; r=json.load(sys.stdin); print(r['label'], '| arrival:', r['on_arrival'], '| after:', r['after_login_incr']['count'], r['after_login_incr']['history'], '| console:', r['console_non_benign'])"
