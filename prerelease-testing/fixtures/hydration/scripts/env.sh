# Sourced by every script of the hydration area. Sets:
#   F    fixture root (this directory's parent: src/ drivers/ cv/ vh/ scripts/ probes/)
#   SB   scratch root holding envs/ (required)
#   W    work dir for run dirs, logs and results (WORK, default $SB/apps/hydration)
#   DRV  driver python ($SB/envs/$DRV_VENV, default venv "driver": playwright, httpx, websockets)
#   NP   prefix that keeps client-side requests to localhost off the agent proxy (never used for servers)
#   REDIS_PORT (default 8149), PORT_RANGES (ports srv.sh accepts)
F=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
: "${SB:?set SB to the scratch root that holds envs/<venv> (e.g. export SB=/tmp/.../scratchpad)}"
W=${WORK:-$SB/apps/hydration}
DRV_VENV=${DRV_VENV:-driver}
DRV=$SB/envs/$DRV_VENV/bin/python
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"
REDIS_PORT=${REDIS_PORT:-8149}
PORT_RANGES=${PORT_RANGES:-"3140-3159 8140-8159 3660-3679 8660-8679"}
export SB WORK=$W DRV_VENV REDIS_PORT PORT_RANGES
export PYTHONDONTWRITEBYTECODE=1   # keep __pycache__ out of the fixture tree
mkdir -p "$W/run" "$W/logs" "$W/results"

# redis_up / redis_down: a throwaway redis-server on $REDIS_PORT (no persistence).
redis_up() {
  for _ in $(seq 1 40); do lsof -iTCP:"$REDIS_PORT" -sTCP:LISTEN -P -n > /dev/null 2>&1 || break; sleep 0.5; done
  redis-server --port "$REDIS_PORT" --save '' --appendonly no > "$W/logs/redis-$REDIS_PORT.log" 2>&1 &
  echo $! > "$W/run/redis-$REDIS_PORT.pid"
  for _ in $(seq 1 40); do redis-cli -p "$REDIS_PORT" ping 2>/dev/null | grep -q PONG && return 0; sleep 0.25; done
  echo "redis on $REDIS_PORT not up"; return 1
}
redis_down() {
  [ -f "$W/run/redis-$REDIS_PORT.pid" ] || return 0
  kill "$(cat "$W/run/redis-$REDIS_PORT.pid")" 2>/dev/null
  for _ in $(seq 1 40); do lsof -iTCP:"$REDIS_PORT" -sTCP:LISTEN -P -n > /dev/null 2>&1 || break; sleep 0.5; done
  rm -f "$W/run/redis-$REDIS_PORT.pid"
}
cd "$W" || exit 1   # neutral cwd for every driver / server (never a checkout)
