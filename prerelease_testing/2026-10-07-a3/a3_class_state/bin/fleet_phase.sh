#!/bin/bash
# Usage: [MODE=new] [FLEET_DEFAULT=n] [CHAIN=chain] fleet_phase.sh <venv> <label>
# Stops the previous prod server, starts run/fleet/fleet_<venv> in prod on 3107 with redis 8109, resumes out/fleet/<chain>-token.txt
# (MODE=new starts a session and writes the token), logs in + increments, appends one JSON line, dumps the redis pickles.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_class_state
V=$1; L=$2; CH=${CHAIN:-chain}; TAG="${CH}-${L//[^A-Za-z0-9._-]/_}"
[ -f $W/pids/fleet.pid ] && $W/bin/stop_app.sh $W/pids/fleet.pid
FLEET_API_URL=http://localhost:3107 REFLEX_REDIS_URL=redis://localhost:8109 PIDTAG=fleet \
  $W/bin/start_app.sh $V $W/run/fleet/fleet_$V 3107 3107 $W/run/logs/fleet-$TAG.raw.log --env prod --loglevel debug >/dev/null
$W/bin/wait_up.sh http://localhost:3107/ 500 $W/pids/fleet.pid || exit 1
sleep 3
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/bin/drive_fleet.py http://localhost:3107 $W/out/fleet/$CH-token.txt "$L" ${MODE:-resume} $W/out/fleet/$CH.jsonl > $W/run/logs/drive-fleet-$TAG.txt 2>&1 \
  && $SB/envs/driver/bin/python -c "import json,sys; r=json.load(open('$W/run/logs/drive-fleet-$TAG.txt')); print(f\"{r['label']:<34} arrival: {r['on_arrival']} | after: {r['after_login_incr']['count']} {r['after_login_incr']['history']!r} | console: {r['console_non_benign']} bad: {r['bad_responses']}\")" \
  || tail -n 20 $W/run/logs/drive-fleet-$TAG.txt
sleep 1
(cd $W && $SB/envs/a3/bin/python -I $W/probes/redis_dump.py 8109) > $W/out/fleet/$TAG.redis.txt 2>&1
grep -v 'DEBUG\|^Debug' $W/run/logs/fleet-$TAG.raw.log | grep -i -E 'error|traceback|exception|mismatch|schema' | grep -v 'Unexpected exit from worker' | sort | uniq -c | head -5
