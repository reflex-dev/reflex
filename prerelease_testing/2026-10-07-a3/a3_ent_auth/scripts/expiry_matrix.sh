#!/usr/bin/env bash
# For each expiry scenario: restart the mock IdP with that scenario's token lifetime, THEN restart the app
# (it caches the IdP JWKS), then run drive_expiry.py for that one scenario.
# Usage: expiry_matrix.sh <venv> <appdir> <label> <scenario...>
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_ent_auth
VENV=$1; APPD=$2; LABEL=$3; shift 3
for sc in "$@"; do
  case $sc in
    proactive) AGE=75; NR=;; expire_norefresh) AGE=30; NR=1;; expire_closed_tab) AGE=40; NR=;; *) AGE=3600; NR=;;
  esac
  $W/scripts/stop_app.sh > /dev/null
  pkill -f "$W/scripts/mock_oidc.py"; sleep 1
  (cd $W/scripts && MOCK_OIDC_MAX_AGE=$AGE MOCK_OIDC_NO_REFRESH=$NR setsid $SB/envs/alpha2-ent/bin/python $W/scripts/mock_oidc.py > $W/logs/mock-oidc-$LABEL-$sc.log 2>&1 < /dev/null &)
  for i in $(seq 1 40); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:8358/.well-known/openid-configuration | grep -q 200 && break; sleep 0.5; done
  redis-cli -p 8349 flushall > /dev/null
  VENV=$VENV APP_DIR=$APPD $W/scripts/start_app.sh dev $W/logs/entauth-dev-redis-$LABEL-expiry-$sc.log > /dev/null
  $W/scripts/wait_ready.sh http://localhost:3340/ http://localhost:8340 360 || continue
  (cd $W/scripts && EXPIRY_MOCK_EXTERNAL=1 NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 900 $SB/envs/driver/bin/python drive_expiry.py http://localhost:3340 $LABEL $sc)
done
$W/scripts/stop_app.sh > /dev/null
pkill -f "$W/scripts/mock_oidc.py"
echo EXPIRY_MATRIX_DONE
