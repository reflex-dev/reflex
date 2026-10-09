#!/usr/bin/env bash
# Run xtab_probe N times against each venv sequentially (entauth, dev, Redis; one server at a time; infra must be started).
# Usage: xtab_matrix.sh <N> <venv>:[<appdir>:]<label> ...
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; W=$WORK/auth; B=$FX/auth/bin
N=$1; shift
for spec in "$@"; do
  IFS=: read VENV APPD LABEL <<< "$spec"; [ -z "$LABEL" ] && { LABEL=$APPD; APPD=entauth_$LABEL; }
  fx_app auth entauth "$APPD"
  "$B/stop_app.sh" > /dev/null
  redis-cli -p 8629 flushall > /dev/null
  VENV=$VENV APP_DIR=$APPD "$FX/auth/scripts/start_app.sh" dev "$W/logs/entauth-dev-redis-$LABEL.log"
  "$B/wait_ready.sh" http://localhost:3620/ http://localhost:8620 || continue
  sleep 3
  (cd "$W/scripts" && $NP timeout 1200 "$DRVPY" xtab_probe.py http://localhost:3620 $LABEL-rep $N 2>&1 | tail -n $((N+1)))
done
"$B/stop_app.sh" > /dev/null
