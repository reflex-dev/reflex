#!/usr/bin/env bash
# #7693 matrix: rxconfig sets frontend_port=3357 backend_port=8357 (NA_CFG_*); run each variant, report what listens.
#   ports.sh <venv>
set -u
SB=${SB:?}; W=${W:-$SB/apps/server_net}
venv=$1
export NA_CFG_FRONTEND_PORT=3357 NA_CFG_BACKEND_PORT=8357
run() { # run <label> <args...>
  local label=$1; shift
  $W/bin/srv.sh start $label $venv netapp "$@" >/dev/null
  local pid; pid=$(cat $W/logs/$label.pid)
  local up=""
  for i in $(seq 1 ${WAITS:-90}); do
    kill -0 $pid 2>/dev/null || break
    up=$(for p in 3357 8357 3000 8000 3001 8001; do lsof -iTCP:$p -sTCP:LISTEN -t >/dev/null 2>&1 && echo -n "$p "; done)
    [ -n "$up" ] && { sleep 3; up=$(for p in 3357 8357 3000 8000 3001 8001; do lsof -iTCP:$p -sTCP:LISTEN -t >/dev/null 2>&1 && echo -n "$p "; done); break; }
    sleep 1
  done
  local alive; alive=$(kill -0 $pid 2>/dev/null && echo running || echo exited)
  echo "$venv | $* | $alive | listening: [${up}] | $(grep -i -E 'cannot|error|must' $W/logs/$label.log | grep -v -i deprecat | head -1 | cut -c1-120)"
  $W/bin/srv.sh stop $label >/dev/null
}
run pt_be --backend-only
run pt_fe --frontend-only
run pt_be_fp --backend-only --frontend-port 3358
run pt_prod_fe --env prod --frontend-only
run pt_prod_be --env prod --backend-only
run pt_prod --env prod
