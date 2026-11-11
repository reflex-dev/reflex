# phase7 server/net helpers. Source it. Ports: fe 3340-3359/3220-3239, be 8340-8359/8220-8239; redis 6391.
OLDSB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
W=$OLDSB/p7/work/net; P7=$OLDSB/p7/envs
PW=$P7/driver/bin/python          # playwright driver
SD=$W/envs/drv/bin/python         # socket.io/aiohttp driver
RP=6391
export REFLEX_TELEMETRY_ENABLED=false PYTHONDONTWRITEBYTECODE=1
vpath() { case $1 in new) echo $P7/new;; prev) echo $P7/prev;; a1) echo $OLDSB/p7/work/cm/envs/ctrl;; *) echo BADVENV; return 1;; esac; }
chkport() { local p=$1
  { [ $p -ge 3340 ] && [ $p -le 3359 ]; } || { [ $p -ge 3220 ] && [ $p -le 3239 ]; } || { [ $p -ge 8340 ] && [ $p -le 8359 ]; } || { [ $p -ge 8220 ] && [ $p -le 8239 ]; } || { echo "port $p outside range" >&2; return 1; }
  curl -s --noproxy '*' -m 1 -o /dev/null localhost:$p && { echo "port $p busy" >&2; return 1; }; return 0; }
redis_up() { redis-cli -p $RP ping >/dev/null 2>&1 && return 0; mkdir -p $W/run/redis; (cd $W/run/redis && setsid redis-server --port $RP --save '' --appendonly no --dir $W/run/redis > $W/logs/redis.log 2>&1 < /dev/null & echo $! > $W/pids/redis.pid); for i in $(seq 25); do redis-cli -p $RP ping >/dev/null 2>&1 && return 0; sleep 0.2; done; return 1; }
redis_down() { redis-cli -p $RP shutdown nosave >/dev/null 2>&1; sleep 0.3; [ -f $W/pids/redis.pid ] && kill -9 $(cat $W/pids/redis.pid) 2>/dev/null; rm -f $W/pids/redis.pid; }
# mkapp <src> <venv> <label> -> echoes app dir (fresh copy)
mkapp() { local d=$W/run/$2/$3; rm -rf $d; mkdir -p $d; cp -a $W/src/$1/. $d/; echo $d; }
# start <label> <venv> <appdir> <log> [ENV=VAL...] -- <reflex run args...>
start() { local label=$1 v=$2 app=$3 log=$4; shift 4; local envs=(); while [ $# -gt 0 ] && [ "$1" != "--" ]; do envs+=("$1"); shift; done; [ $# -gt 0 ] && shift
  local vp; vp=$(vpath $v) || return 1
  ( cd $app && export EXPECT_VENV=$vp PATH=$vp/bin:$PATH ${envs[@]+"${envs[@]}"}; setsid sh -c 'echo $$ > "$0"; exec "$@"' $W/pids/$label.pid reflex run "$@" > $log 2>&1 < /dev/null & ); sleep 0.5
  echo "started $label pgid=$(cat $W/pids/$label.pid) venv=$v log=$log"; }
stop() { local f=$W/pids/$1.pid sig=${2:-INT}; [ -f $f ] || return 0; local pid=$(cat $f)
  kill -$sig -- -$pid 2>/dev/null; for i in $(seq 40); do kill -0 -- -$pid 2>/dev/null || { rm -f $f; echo "stopped $1"; return 0; }; sleep 0.5; done
  kill -9 -- -$pid 2>/dev/null; rm -f $f; echo "KILLED $1"; }
wait_up() { local t=${2:-400}; for i in $(seq 1 $t); do [ "$(curl -s --noproxy '*' -m 2 -o /dev/null -w '%{http_code}' $1)" = 200 ] && { echo "up after ${i}s"; return 0; }; sleep 1; done; echo "NOT UP: $1"; return 1; }
# hs <port> <Host> <Origin|-> [Header: value ...]: raw websocket upgrade to /_event
hs() { local P=$1 H=$2 O=$3; shift 3; local args=(-H "Host: $H" -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==")
  [ "$O" != "-" ] && args+=(-H "Origin: $O"); local h; for h in "$@"; do args+=(-H "$h"); done
  local code=$(curl --noproxy '*' -s -o /dev/null -m 3 -w '%{http_code}' "${args[@]}" "http://127.0.0.1:$P/_event/?EIO=4&transport=websocket"); echo "$code  Host=$H Origin=$O $*"; }
# browse <label> <url>: Chromium clicks inc twice; count must reach 2
browse() { (cd $W && NO_PROXY=localhost,127.0.0.1,.test no_proxy=localhost,127.0.0.1,.test timeout 120 $PW $W/bin/drv.py "$2" $W/res/$1.json $W/res/$1.png 2>&1 | head -4 | sed "s/^/  [$1] /"); }
