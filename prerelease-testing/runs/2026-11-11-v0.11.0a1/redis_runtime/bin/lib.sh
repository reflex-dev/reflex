# redis_runtime helpers. Source it. Ports: fe 3220-3239, be 8220-8239, redis 8236-8239.
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
W=$SB/apps/redis_runtime
export REFLEX_TELEMETRY_ENABLED=false
mkdir -p $W/pids $W/logs $W/run
_chkport() { local p=$1; if ! { [ $p -ge 3220 ] && [ $p -le 3239 ]; } && ! { [ $p -ge 8220 ] && [ $p -le 8239 ]; }; then echo "port $p outside range" >&2; return 1; fi
  if curl -s --noproxy '*' -m 1 -o /dev/null localhost:$p; then echo "port $p busy" >&2; return 1; fi; }
# redis_up <port>
redis_up() { _chkport $1 || return 1; setsid sh -c 'echo $$ > "$0"; mkdir -p /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/redis_runtime/run/redisdata-$1; exec redis-server --port "$1" --save "" --appendonly no --dir /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/redis_runtime/run/redisdata-$1' $W/pids/redis-$1.pid $1 > $W/logs/redis-$1.log 2>&1 < /dev/null & sleep 0.2; for i in $(seq 20); do redis-cli -p $1 ping >/dev/null 2>&1 && return 0; sleep 0.2; done; return 1; }
redis_down() { redis-cli -p $1 shutdown nosave >/dev/null 2>&1; sleep 0.3; [ -f $W/pids/redis-$1.pid ] && kill -9 $(cat $W/pids/redis-$1.pid) 2>/dev/null; rm -f $W/pids/redis-$1.pid; }
# start_app <tag> <venv> <appdir> <fp> <bp> <log> [reflex run args...]   (env vars passed through the caller's env)
start_app() { local tag=$1 v=$2 app=$3 fp=$4 bp=$5 log=$6; shift 6; _chkport $fp || return 1; [ $fp = $bp ] || _chkport $bp || return 1
  ( cd $app && EXPECT_VENV=$v setsid sh -c 'echo $$ > "$0"; exec "$@"' $W/pids/$tag.pid "$SB/envs/$v/bin/reflex" run --frontend-port $fp --backend-port $bp "$@" > $log 2>&1 < /dev/null & ); sleep 0.5
  echo "started $tag pgid=$(cat $W/pids/$tag.pid) venv=$v fp=$fp bp=$bp log=$log"; }
# stop_app <tag> [signal]  -> prints seconds to stop
stop_app() { local f=$W/pids/$1.pid sig=${2:-TERM}; [ -f $f ] || return 0; local pid=$(cat $f) t0=$(date +%s.%N)
  kill -$sig -- -$pid 2>/dev/null
  for i in $(seq 1 60); do kill -0 -- -$pid 2>/dev/null || { echo "stopped $1 in $(echo "$(date +%s.%N) - $t0" | bc)s"; rm -f $f; return 0; }; sleep 0.5; done
  kill -KILL -- -$pid 2>/dev/null; echo "KILLED $1 after 30s (did not stop on $sig)"; rm -f $f; }
# wait_up <url> [timeout_s]
wait_up() { local t=${2:-400}; for i in $(seq 1 $t); do [ "$(curl -s --noproxy '*' -m 2 -o /dev/null -w '%{http_code}' $1)" = 200 ] && { echo "up after ${i}s"; return 0; }; sleep 1; done; echo "NOT UP: $1"; return 1; }
CLIENT_ENV="NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"
