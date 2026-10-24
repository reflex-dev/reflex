#!/usr/bin/env bash
# usage: pl_run.sh <venv> <label> [reps=1] [dev|prod]   -- #277 pending-login scenarios on the vauth fixture app
# infra (Redis 8629 + mock IdP 8638) must be running (auth/bin/infra.sh start). dev: 3620/8620; prod: 8621 (1 worker, account stub).
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work; F=$SB/apps/enterprise/src; . "$F/lib.sh"; fx_sync auth; E=$WORK/auth; B=$F/auth/bin
V=$1; L=$2; R=${3:-1}; M=${4:-dev}; O=$SB/apps/enterprise/own; mkdir -p "$O/out"
fx_app auth vauth vauth_$L
if [ "$M" = prod ]; then GRANIAN_WORKERS=1 "$B/start_app.sh" "$V" vauth_$L prod "$E/logs/pl-$L-prod.server.log"; U=http://localhost:8621; "$B/wait_ready.sh" $U/ $U 600
else "$B/start_app.sh" "$V" vauth_$L dev "$E/logs/pl-$L-dev.server.log"; U=http://localhost:3620; "$B/wait_ready.sh" $U/ http://localhost:8620 420; fi
HR=""; [ "$M" = dev ] && HR=$E/vauth_$L/vauth/vauth.py
cd "$O/probes" && HOT_RELOAD_FILE=$HR $NP timeout 900 "$DRVPY" pending_login.py $U $L-$M $R 2>&1 | tee "$O/out/pending_login_$L-$M.txt" | tail -n 12 | cut -c1-400
"$B/stop_app.sh"
LOGF=$E/logs/pl-$L-$M.server.log
echo "server log: tracebacks=$(grep -c Traceback "$LOGF") 'state mismatch'=$(grep -ci 'mismatch' "$LOGF") restart=$(grep -ci 'restart' "$LOGF") recovered=$(grep -ci 'Recovered by the automatic restart' "$LOGF")"
