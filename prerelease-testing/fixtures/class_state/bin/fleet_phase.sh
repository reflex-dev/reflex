#!/bin/bash
# N-004 "mixed fleet / rollback" chain, one phase per call. Usage: [MODE=new] [FLEET_DEFAULT=n] [CHAIN=chain] bin/fleet_phase.sh <venv> <label>
# Stops the previous fleet server, starts a copy of apps/fleet_app ($W/run/fleet/fleet_<venv>) in prod on $FLEET_PORT (3307) with
# redis $REDIS_PORT, resumes the session in $W/out/fleet/<chain>-token.txt (MODE=new starts one and writes the token), logs in +
# increments, appends one JSON line to $W/out/fleet/<chain>.jsonl and prints a summary. Start redis and `redis-cli flushall` first.
. "$(cd "$(dirname "$0")/.." && pwd)/env.sh"
V=$1; L=$2; CH=${CHAIN:-chain}; TAG="${CH}-${L//[^A-Za-z0-9._-]/_}"; P=${FLEET_PORT:-3307}
mkdir -p "$W/out/fleet" "$W/logs/fleet" "$W/run/fleet"
[ -d "$W/run/fleet/fleet_$V" ] || cp -r "$CS/apps/fleet_app" "$W/run/fleet/fleet_$V"
[ -f "$W/pids/fleet.pid" ] && "$CS/bin/stop_app.sh" "$W/pids/fleet.pid"
FLEET_API_URL=http://localhost:$P REFLEX_REDIS_URL=redis://localhost:$REDIS_PORT PIDTAG=fleet \
  "$CS/bin/start_app.sh" "$V" "$W/run/fleet/fleet_$V" "$P" "$P" "$W/logs/fleet/fleet-$TAG.raw.log" --env prod --loglevel debug >/dev/null
"$CS/bin/wait_up.sh" "http://localhost:$P/" 500 "$W/pids/fleet.pid" || exit 1
sleep 3
env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 "$SB/envs/$DRIVER/bin/python" "$CS/bin/drive_fleet.py" "http://localhost:$P" "$W/out/fleet/$CH-token.txt" "$L" "${MODE:-resume}" "$W/out/fleet/$CH.jsonl" > "$W/logs/fleet/drive-fleet-$TAG.txt" 2>&1 \
  && "$SB/envs/$DRIVER/bin/python" -c "import json,sys; r=json.load(open(sys.argv[1])); print(f\"{r['label']:<34} arrival: {r['on_arrival']} | after: {r['after_login_incr']['count']} {r['after_login_incr']['history']!r} | console: {r['console_non_benign']} bad: {r['bad_responses']}\")" "$W/logs/fleet/drive-fleet-$TAG.txt" \
  || tail -n 20 "$W/logs/fleet/drive-fleet-$TAG.txt"
grep -v 'DEBUG\|^Debug' "$W/logs/fleet/fleet-$TAG.raw.log" | grep -i -E 'error|traceback|exception|mismatch|schema' | grep -v 'Unexpected exit from worker' | sort | uniq -c | head -5
# leave the server up for the next phase; stop it with: bin/stop_app.sh $W/pids/fleet.pid
