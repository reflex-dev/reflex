# source me: shared vars/helpers for the db_upgrade cluster
export SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
export W=$SB/apps/db_upgrade
export REFLEX_TELEMETRY_ENABLED=false
DPY=$SB/envs/driver/bin/python
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 900 $DPY"
venv() { echo "$SB/envs/db_upgrade-$1"; }
# rx <key> <appdir> <args...>: run the venv's reflex in appdir, print rc
rx() { local V; V=$(venv "$1"); local A=$2; shift 2; (cd "$A" && "$V/bin/reflex" "$@"); local rc=$?; echo "[rc=$rc] reflex $*"; return 0; }
al() { local V; V=$(venv "$1"); local A=$2; shift 2; (cd "$A" && "$V/bin/alembic" "$@"); local rc=$?; echo "[rc=$rc] alembic $*"; return 0; }
http_code() { curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 "$1"; }
port_busy() { curl -s --noproxy "*" -o /dev/null --max-time 2 "http://localhost:$1/" && return 0; lsof -nP -iTCP:$1 -sTCP:LISTEN -t >/dev/null 2>&1; }
sha() { sha256sum "$@" | cut -c1-16; }
cpapp () 
{ 
    mkdir -p "$2";
    ( cd "$1" && tar --exclude=./.web --exclude=./reflex.lock --exclude=./.states --exclude=__pycache__ -cf - . ) | ( cd "$2" && tar xf - )
}
