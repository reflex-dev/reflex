#!/usr/bin/env bash
# Token expiry / proactive refresh / revocation on the entauth app (dev, Redis). For each scenario: restart the mock IdP
# with that scenario's token lifetime, THEN restart the app (it caches the IdP JWKS), then run drive_expiry.py.
# Usage: expiry_matrix.sh <venv> <label> <scenario...>   scenarios: proactive expire_norefresh expire_closed_tab revoke
# (the old form expiry_matrix.sh <venv> <appdir> <label> <scenario...> still works). Redis must be running (bin/infra.sh start).
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; W=$WORK/auth; B=$FX/auth/bin
VENV=$1; shift
case $2 in proactive|expire_norefresh|expire_closed_tab|revoke|restart_provider) APPD=$1; LABEL=$1; shift;; *) APPD=$1; LABEL=$2; shift 2;; esac
[ "$APPD" = "$LABEL" ] && APPD=entauth_$LABEL
fx_app auth entauth "$APPD"
for sc in "$@"; do
  case $sc in
    proactive) AGE=75; NR=;; expire_norefresh) AGE=30; NR=1;; expire_closed_tab) AGE=40; NR=;; *) AGE=3600; NR=;;
  esac
  "$B/stop_app.sh" > /dev/null
  pkill -f "$W/scripts/mock_oidc.py"; sleep 1
  (cd "$W/run" || exit 1; MOCK_OIDC_MAX_AGE=$AGE MOCK_OIDC_NO_REFRESH=$NR setsid "$SB/envs/$IDP_VENV/bin/python" "$W/scripts/mock_oidc.py" > "$W/logs/mock-oidc-$LABEL-$sc.log" 2>&1 < /dev/null &)
  for i in $(seq 1 40); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:8638/.well-known/openid-configuration | grep -q 200 && break; sleep 0.5; done
  redis-cli -p 8629 flushall > /dev/null
  VENV=$VENV APP_DIR=$APPD "$FX/auth/scripts/start_app.sh" dev "$W/logs/entauth-dev-redis-$LABEL-expiry-$sc.log" > /dev/null
  "$B/wait_ready.sh" http://localhost:3620/ http://localhost:8620 360 || continue
  (cd "$W/scripts" && EXPIRY_MOCK_EXTERNAL=1 $NP timeout 900 "$DRVPY" drive_expiry.py http://localhost:3620 "$LABEL" "$sc")
done
"$B/stop_app.sh" > /dev/null
pkill -f "$W/scripts/mock_oidc.py"
echo EXPIRY_MATRIX_DONE
