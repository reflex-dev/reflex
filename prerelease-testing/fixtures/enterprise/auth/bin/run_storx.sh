#!/usr/bin/env bash
# A3-10 (protected client storage blanked on client nav with Redis), explorer fixture: vauthx app + drivers/storx.py.
# Usage: run_storx.sh <venv>:[<appdir>:]<label> ...   (dev, Redis unless NOREDIS=1; one server at a time; infra must be started)
# <appdir> (default vauthx_<label>) is the copy of src/vauthx under $WORK/auth.
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; W=$WORK/auth; B=$FX/auth/bin
for spec in "$@"; do
  IFS=: read V A L <<< "$spec"; [ -z "$L" ] && { L=$A; A=vauthx_$L; }
  fx_app auth vauthx "$A"
  "$B/stop_app.sh" > /dev/null; redis-cli -p 8629 flushall > /dev/null
  "$B/start_app.sh" "$V" "$A" dev "$W/logs/$L-storx.server.log"
  "$B/wait_ready.sh" http://localhost:3620/ http://localhost:8620 400 || continue
  (cd "$W/drivers" && $NP timeout 900 "$DRVPY" storx.py http://localhost:3620 "$L" 2 > "$W/logs/$L-storx.out" 2>&1)
  echo "$L tracebacks: $(grep -c Traceback "$W/logs/$L-storx.server.log")"
done
"$B/stop_app.sh" > /dev/null
echo RUN_STORX_DONE
