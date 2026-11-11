#!/bin/bash
# Usage: run_reconnect.sh <venv> [FP_REDIS=3150] [FP_MEMORY=3151] [ROUNDS=3]
#   src/hydapp prod (via scripts/srv_hydapp.sh): reconnect_driver.py with Redis (kill server with tab open -> banner,
#   restart -> token/counter/storage kept), redis_restart_loop.py (F-017: token survives N stop/start rounds, no granian
#   panic, no leftover token_manager_socket_record_* keys), token_leak_check.py, then reconnect_driver.py memory
#   --default-change (state reset by design; returning visitor sees the new default = F-002 in the full app).
. "$(dirname "$0")/env.sh"
V=$1; P1=${2:-3150}; P2=${3:-3151}; N=${4:-3}
redis_up || exit 1
$NP timeout 900 "$DRV" "$F/drivers/reconnect_driver.py" --venv "$V" --port "$P1" --manager redis --out "$W/results/reconnect-$V-redis" 2>&1 | tail -6
$NP timeout 1800 "$DRV" "$F/drivers/redis_restart_loop.py" "$V" "$P1" "$N" 2>&1 | tail -$((N+2))
$NP timeout 900 "$DRV" "$F/drivers/token_leak_check.py" "$V" "$P1" 2 2>&1 | grep -E "ROUND|hydrated"
redis_down
$NP timeout 900 "$DRV" "$F/drivers/reconnect_driver.py" --venv "$V" --port "$P2" --manager memory --out "$W/results/reconnect-$V-memory" --default-change 2>&1 | tail -6
