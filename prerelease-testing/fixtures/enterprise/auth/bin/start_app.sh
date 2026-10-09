#!/usr/bin/env bash
# Usage: start_app.sh <venv> <appdir> <dev|prod> <logfile> [extra reflex args]
# <appdir> is relative to $WORK/auth (copies made by fx_app). Ports: dev 3620/8620, prod single port 8621 (FP/BP/PP override).
# Redis :8629 unless NOREDIS=1 or MGR=disk|memory; mock IdP :8638 (bin/infra.sh).
# Env passthrough: GRANIAN_WORKERS, VAUTH_PID_HEADER, VAUTHD_AUDIT_FILE, VEA_INSTRUMENT, VEA_FIX, OIDC_CLIENT (default vauth-client).
. "$(dirname "$0")/../../lib.sh"; W=$WORK/auth
VENV=$1; APPDIR=$2; MODE=$3; LOG=$4; shift 4
FP=${FP:-3620}; BP=${BP:-8620}; PP=${PP:-8621}
[ -d "$W/$APPDIR" ] || { echo "no app dir $W/$APPDIR"; exit 1; }
venv_check "$VENV" || exit 1
mkdir -p "$W/run"
# version banner + venv guard (python run from a neutral dir, never from a checkout)
( cd "$W/run" && "$SB/envs/$VENV/bin/python" -c "
import reflex, importlib.metadata as m
assert '/envs/$VENV/' in reflex.__file__, reflex.__file__
def v(p):
    try: return m.version(p)
    except Exception: return '-'
print('VENV_GUARD venv=$VENV reflex', v('reflex'), 'reflex-base', v('reflex-base'), 'reflex-enterprise', v('reflex-enterprise'), 'file', reflex.__file__)
" ) > "$LOG" 2>&1 || { echo "venv guard failed"; cat "$LOG"; exit 1; }
cd "$W/$APPDIR" || exit 1
export CI=true REFLEX_TELEMETRY_ENABLED=false AUTHLIB_INSECURE_TRANSPORT=1 QA_EXPECT_VENV=$VENV
export OIDC_ISSUER_URI=http://localhost:8638 OIDC_CLIENT_ID=${OIDC_CLIENT:-vauth-client} OIDC_CLIENT_SECRET=${OIDC_CLIENT:-vauth-client}-secret
[ "${NOREDIS:-0}" = 1 ] && MGR=${MGR:-memory}
case ${MGR:-redis} in
  redis) export REFLEX_REDIS_URL=redis://localhost:8629;;
  disk|memory) export REFLEX_STATE_MANAGER_MODE=$MGR;;
esac
if [ "$MODE" = prod ]; then
  acct_stub
  export REFLEX_API_URL=http://localhost:$PP
  setsid "$SB/envs/$VENV/bin/reflex" run --env prod --frontend-port $PP --backend-port $PP --loglevel debug "$@" >> "$LOG" 2>&1 < /dev/null &
else
  setsid "$SB/envs/$VENV/bin/reflex" run --frontend-port $FP --backend-port $BP --loglevel debug "$@" >> "$LOG" 2>&1 < /dev/null &
fi
P=$!
echo $P > "$W/run/app.pgid"
echo "started pid/pgid $P ($VENV $APPDIR $MODE mgr=${MGR:-redis} workers=${GRANIAN_WORKERS:-default}) log=$LOG"
