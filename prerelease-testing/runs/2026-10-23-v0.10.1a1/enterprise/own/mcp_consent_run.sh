#!/usr/bin/env bash
# usage: REDIS=1|0 mcp_consent_run.sh <venv> <label>  -- entauth dev (Redis unless REDIS=0) + own/probes/mcp_consent_probe.py (clients on $ENT_DRV)
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work; F=$SB/apps/enterprise/src; . "$F/lib.sh"; fx_sync auth; E=$WORK/auth; B=$F/auth/bin; O=$SB/apps/enterprise/own
V=$1; L=$2; venv_check "$ENT_DRV" || exit 1
"$B/infra.sh" start; redis-cli -p 8629 flushall > /dev/null
fx_app auth entauth entauth_$L
REDIS=${REDIS:-1} VENV=$V APP_DIR=entauth_$L "$F/auth/scripts/start_app.sh" dev "$E/logs/entauth-consent-$L.log"
"$B/wait_ready.sh" http://localhost:3620/ http://localhost:8620 420 || { "$B/stop_app.sh"; "$B/infra.sh" stop; exit 1; }
cp "$O/probes/mcp_consent_probe.py" "$E/scripts/"
(cd "$E/scripts" && $NP timeout 300 "$SB/envs/$ENT_DRV/bin/python" mcp_consent_probe.py http://localhost:8620 http://localhost:3620 $L 2>&1 | tail -n 8 | cut -c1-900)
"$B/stop_app.sh"; "$B/infra.sh" stop
grep -n -i "redirecting to\|Auth callback\|mismatch\|redirected_to_login\|restart" "$E/logs/entauth-consent-$L.log" | cut -c1-200 | head -8
echo "server tracebacks=$(grep -c Traceback "$E/logs/entauth-consent-$L.log")"
