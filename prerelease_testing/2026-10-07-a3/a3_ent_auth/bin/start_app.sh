#!/usr/bin/env bash
# Usage: start_app.sh <venv> <appdir> <dev|prod> <logfile> [extra reflex args]
# a3_ent_auth ports: dev frontend 3340 / backend 8340; prod single port 8341. Redis :8349, mock IdP :8358.
# Env passthrough: GRANIAN_WORKERS, VAUTH_PID_HEADER, NOREDIS=1 (memory state manager), FP/BP/PP (port overrides),
# OIDC_CLIENT (default vauth-client).
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_ent_auth
VENV=$1; APPDIR=$2; MODE=$3; LOG=$4; shift 4
FP=${FP:-3340}; BP=${BP:-8340}; PP=${PP:-8341}
[ -d "$W/$APPDIR" ] || { echo "no app dir $W/$APPDIR"; exit 1; }
# version banner (python run from a neutral dir, never from a checkout)
( cd $W/run && $SB/envs/$VENV/bin/python -c "
import reflex, importlib.metadata as m
assert '/scratchpad/envs/$VENV/' in reflex.__file__, reflex.__file__
def v(p):
    try: return m.version(p)
    except Exception: return '-'
print('VENV_GUARD venv=$VENV reflex', v('reflex'), 'reflex-base', v('reflex-base'), 'reflex-enterprise', v('reflex-enterprise'), 'file', reflex.__file__)
" ) > $LOG 2>&1 || { echo "venv guard failed"; cat $LOG; exit 1; }
cd $W/$APPDIR || exit 1
export CI=true REFLEX_TELEMETRY_ENABLED=false AUTHLIB_INSECURE_TRANSPORT=1
export OIDC_ISSUER_URI=http://localhost:8358 OIDC_CLIENT_ID=${OIDC_CLIENT:-vauth-client} OIDC_CLIENT_SECRET=${OIDC_CLIENT:-vauth-client}-secret
[ "${NOREDIS:-0}" = "1" ] || export REFLEX_REDIS_URL=redis://localhost:8349
if [ "$MODE" = prod ]; then
  export REFLEX_API_URL=http://localhost:$PP
  setsid $SB/envs/$VENV/bin/reflex run --env prod --frontend-port $PP --backend-port $PP --loglevel debug "$@" >> $LOG 2>&1 < /dev/null &
else
  setsid $SB/envs/$VENV/bin/reflex run --frontend-port $FP --backend-port $BP --loglevel debug "$@" >> $LOG 2>&1 < /dev/null &
fi
P=$!
echo $P > $W/run/app.pgid
echo "started pid/pgid $P ($VENV $APPDIR $MODE redis=$([ "${NOREDIS:-0}" = 1 ] && echo no || echo yes) workers=${GRANIAN_WORKERS:-default}) log=$LOG"
