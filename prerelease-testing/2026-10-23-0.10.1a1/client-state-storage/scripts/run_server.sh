#!/bin/bash
# Usage: run_server.sh <env: shared|prev> <frontend-port> <backend-port> <logname> [extra reflex run args...]
# Extra env (e.g. REFLEX_REDIS_TOKEN_EXPIRATION=4 REFLEX_STATE_MANAGER_MODE=memory) can be set in the caller's environment.
SB=/tmp/claude-0/-home-user-reflex/7eb9e30f-e96c-5de5-9b0e-4a12be91e0f3/scratchpad/prt
A=$SB/apps/client-state-storage
ENV=$1; FP=$2; BP=$3; LOG=$4; shift 4
cd $A/${APPDIR:-app}
REFLEX_TELEMETRY_ENABLED=false $SB/envs/$ENV/bin/reflex run --frontend-port $FP --backend-port $BP --loglevel debug "$@" > $A/logs/$LOG.log 2>&1 &
echo $! > $A/logs/$LOG.pid
echo "started pid $(cat $A/logs/$LOG.pid) log $A/logs/$LOG.log"
