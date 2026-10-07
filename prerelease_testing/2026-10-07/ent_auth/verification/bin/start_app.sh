#!/usr/bin/env bash
# Usage: start_app.sh <venv> <appdir> <dev|prod> <logfile> [extra reflex args]
# dev: frontend 3720 / backend 8720; prod: single port 8721. Redis :8739, mock IdP :8738.
# Env passthrough: GRANIAN_WORKERS, VAUTH_PID_HEADER, NOREDIS=1 (memory state manager)
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_ent_auth_0
VENV=$1; APPDIR=$2; MODE=$3; LOG=$4; shift 4
cd $W/$APPDIR || exit 1
export CI=true REFLEX_TELEMETRY_ENABLED=false AUTHLIB_INSECURE_TRANSPORT=1
export OIDC_ISSUER_URI=http://localhost:8738 OIDC_CLIENT_ID=vauth-client OIDC_CLIENT_SECRET=vauth-secret
[ "${NOREDIS:-0}" = "1" ] || export REFLEX_REDIS_URL=redis://localhost:8739
if [ "$MODE" = prod ]; then
  export REFLEX_API_URL=http://localhost:8721
  setsid $SB/envs/$VENV/bin/reflex run --env prod --frontend-port 8721 --backend-port 8721 --loglevel debug "$@" > $LOG 2>&1 &
else
  setsid $SB/envs/$VENV/bin/reflex run --frontend-port 3720 --backend-port 8720 --loglevel debug "$@" > $LOG 2>&1 &
fi
echo $! > $W/logs/app.pid
echo "started pid $(cat $W/logs/app.pid) ($VENV $APPDIR $MODE) log=$LOG"
