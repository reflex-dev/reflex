#!/usr/bin/env bash
# usage: xff_run.sh <venv> <reflex_hops> <label> [ws_version=0.10.1a1]
# Starts the own hnet app (dev, 3610/8610) on <venv> with REFLEX_TRUSTED_PROXY_HOPS=<reflex_hops>, runs the REST and
# websocket XFF probes, stops the server. Output: $O/out/xff_<label>.txt (+ json per case).
set -u
SB=${SB:?}; O=$SB/apps/enterprise/own; W=$SB/apps/enterprise/work/xff; mkdir -p "$W" "$O/out"
VENV=$1; HOPS=$2; L=$3; VER=${4:-0.10.1a1}
DRV=$SB/envs/driver/bin/python; NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"
RUN=$W/hnet_$VENV; mkdir -p "$RUN"; (cd "$O/hnet" && tar --exclude=.web --exclude=__pycache__ -cf - .) | (cd "$RUN" && tar -xf -)
cd "$RUN" || exit 1
LOG=$W/hnet_$L.log
env CI=true REFLEX_TELEMETRY_ENABLED=false QA_EXPECT_VENV=$VENV REFLEX_TRUSTED_PROXY_HOPS=$HOPS XFF_RXE_HOPS=${XFF_RXE_HOPS:-0} \
  setsid "$SB/envs/$VENV/bin/reflex" run --frontend-port 3610 --backend-port 8610 --loglevel debug > "$LOG" 2>&1 < /dev/null &
PID=$!; PGID=$(ps -o pgid= -p $PID | tr -d ' '); echo "started pid=$PID pgid=$PGID hops=$HOPS venv=$VENV"
for i in $(seq 1 150); do
  a=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:3610/ip); b=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:8610/ping)
  [ "$a" = 200 ] && [ "$b" = 200 ] && { echo "ready after $((i*2))s"; break; }; kill -0 $PID 2>/dev/null || { echo "server exited"; tail -20 "$LOG"; }; sleep 2
done
OUT=$O/out/xff_$L.txt; : > "$OUT"
{
  echo "## $L venv=$VENV REFLEX_TRUSTED_PROXY_HOPS=$HOPS XFF_RXE_HOPS=${XFF_RXE_HOPS:-0} $(date -u +%FT%TZ)"
  echo "## REST (rxe EventHandlerAPIPlugin) -> 8610"
  cd "$O/probes"
  $NP "$DRV" rest_probe.py http://localhost:8610 rest_none --out "$O/out/xff_${L}_rest_none.json"
  $NP "$DRV" rest_probe.py http://localhost:8610 rest_spoof_one --hdr "X-Forwarded-For: 6.6.6.6" --out "$O/out/xff_${L}_rest_one.json"
  $NP "$DRV" rest_probe.py http://localhost:8610 rest_spoof_chain --hdr "X-Forwarded-For: 6.6.6.6, 7.7.7.7" --out "$O/out/xff_${L}_rest_chain.json"
  $NP "$DRV" rest_probe.py http://localhost:8610 rest_spoof_junk --hdr "X-Forwarded-For: not an ip <script>" --out "$O/out/xff_${L}_rest_junk.json"
  echo "## websocket (reflex core) -> 8610"
  for c in "ws_none|" "ws_spoof_one|X-Forwarded-For: 6.6.6.6" "ws_spoof_chain|X-Forwarded-For: 6.6.6.6, 7.7.7.7"; do
    n=${c%%|*}; h=${c#*|}; args=(); [ -n "$h" ] && args=(--hdr "$h")
    res=$($NP "$DRV" ws_probe.py --port 8610 --version "$VER" --tag "$n" --out "$O/out/xff_${L}_$n.json" "${args[@]}" 2>&1 | tail -1)
    "$DRV" -I ws_summ.py "$n" "$res"
  done
} 2>&1 | tee -a "$OUT"
kill -TERM -- -$PGID 2>/dev/null; for i in $(seq 1 15); do pgrep -g $PGID >/dev/null || break; sleep 1; done; pgrep -g $PGID >/dev/null && kill -KILL -- -$PGID 2>/dev/null
echo "stopped; tracebacks=$(grep -c Traceback "$LOG") xff-warnings=$(grep -ci 'forwarded' "$LOG")" | tee -a "$OUT"
