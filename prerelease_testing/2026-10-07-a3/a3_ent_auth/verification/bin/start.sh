#!/usr/bin/env bash
# Usage: start.sh <venv> <appdir> <dev|prod> <logfile> [extra reflex args]
# Ports: dev 3620/8620, prod single port 8621. Redis :8629 unless MGR=disk|memory. Mock IdP :8638.
# Env passthrough: GRANIAN_WORKERS, MGR (redis|disk|memory; default redis), VEA_INSTRUMENT, VEA_FIX.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_ent_auth
VENV=$1; APPDIR=$2; MODE=$3; LOG=$4; shift 4
( cd $W/run && $SB/envs/$VENV/bin/python -c "
import reflex, importlib.metadata as m
assert '/scratchpad/envs/$VENV/' in reflex.__file__, reflex.__file__
print('VENV_GUARD venv=$VENV reflex', m.version('reflex'), 'reflex-base', m.version('reflex-base'), 'reflex-enterprise', m.version('reflex-enterprise'))
" ) > $LOG 2>&1 || { echo "venv guard failed"; cat $LOG; exit 1; }
cd $W/$APPDIR || exit 1
export CI=true REFLEX_TELEMETRY_ENABLED=false AUTHLIB_INSECURE_TRANSPORT=1
export OIDC_ISSUER_URI=http://localhost:8638 OIDC_CLIENT_ID=vea-client OIDC_CLIENT_SECRET=vea-client-secret
case ${MGR:-redis} in
  redis) export REFLEX_REDIS_URL=redis://localhost:8629;;
  disk) export REFLEX_STATE_MANAGER_MODE=disk;;
  memory) export REFLEX_STATE_MANAGER_MODE=memory;;
esac
echo "START venv=$VENV app=$APPDIR mode=$MODE mgr=${MGR:-redis} workers=${GRANIAN_WORKERS:-default} instrument=${VEA_INSTRUMENT:-0} fix=${VEA_FIX:-0}" >> $LOG
if [ "$MODE" = prod ]; then
  export REFLEX_API_URL=http://localhost:8621
  setsid $SB/envs/$VENV/bin/reflex run --env prod --frontend-port 8621 --backend-port 8621 --loglevel debug "$@" >> $LOG 2>&1 < /dev/null &
else
  setsid $SB/envs/$VENV/bin/reflex run --frontend-port 3620 --backend-port 8620 --loglevel debug "$@" >> $LOG 2>&1 < /dev/null &
fi
echo $! > $W/run/app.pgid
echo "started pgid $(cat $W/run/app.pgid) log=$LOG"
