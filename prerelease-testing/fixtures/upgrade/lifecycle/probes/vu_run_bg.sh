#!/bin/bash
# verify_upgrade A3-06: run the bgt_<ver> app in dev (optionally with Redis), drive it, stop it.
# Usage: vu_run_bg.sh <venv> <appdir> <tag> [redis]
set -u
. "$(dirname "$0")/../../bin/env.sh"; L=$(cd "$(dirname "$0")/.." && pwd); FP=${FP:-3510}; BP=${BP:-8510}; SUPP=${SUPP:-8519}
W=$L
V=$1; APP=$2; TAG=$3; MODE=${4:-memory}
mkdir -p $W/out/bg
"$SB/envs/$V/bin/python" -I -c "import reflex; assert '/envs/$V/' in reflex.__file__, reflex.__file__"
EXTRA=()
RPID=""
if [ "$MODE" = redis ]; then
  redis-server --port ${RP:-8509} --save '' --appendonly no > $W/out/bg/$TAG.redis.log 2>&1 & RPID=$!
  sleep 1
  EXTRA=(env REFLEX_REDIS_URL=redis://localhost:${RP:-8509})
fi
( cd $APP && exec setsid ${EXTRA[@]+"${EXTRA[@]}"} env REFLEX_TELEMETRY_ENABLED=false $SB/envs/$V/bin/reflex run --frontend-port $FP --backend-port $BP > $W/out/bg/$TAG.server.log 2>&1 ) & SP=$!
sleep 1
for i in $(seq 1 240); do
  f=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://127.0.0.1:$FP/ 2>/dev/null); b=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://127.0.0.1:$BP/ping 2>/dev/null)
  [ "$f" = 200 ] && [ "$b" = 200 ] && break; sleep 1
done
echo "[$TAG] up after ${i}s (fe=$f be=$b)"
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $DPY $L/probes/vu_drive_bg.py http://localhost:$FP/ $W/out/bg/$TAG.json
[ -n "$RPID" ] && echo "[$TAG] redis keys: $(redis-cli -p ${RP:-8509} --scan | head -5 | tr "\n" " ")"
PG=$(ps -o sid= -p $SP 2>/dev/null | tr -d ' ')
[ -n "$PG" ] && kill -INT -- -$PG 2>/dev/null
sleep 4
[ -n "$PG" ] && kill -KILL -- -$PG 2>/dev/null
wait $SP 2>/dev/null
[ -n "$RPID" ] && kill $RPID && wait $RPID 2>/dev/null
echo "[$TAG] server log errors:"; grep -n -E "ImmutableStateError|Traceback|Error" $W/out/bg/$TAG.server.log | sed "s#$SB#\$SB#g" | head -20
