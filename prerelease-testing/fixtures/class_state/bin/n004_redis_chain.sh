#!/bin/bash
# N-004 e2e: one Redis ($REDIS_PORT), apps/cse2e in prod on one port (default 3303), alternating versions on ONE session token.
# Usage: bin/n004_redis_chain.sh [venv...]      default chain: $PREV $NEW $PREV $NEW  (each phase must arrive with the previous phase's values)
. "$(cd "$(dirname "$0")/.." && pwd)/env.sh"
P=${CHAIN_PORT:-3303}; [ $# -gt 0 ] || set -- "$PREV" "$NEW" "$PREV" "$NEW"
OUT=$W/logs/n004/redis_chain.txt; mkdir -p "$W/logs/n004" "$W/out/e2e" "$W/run/e2e"; : > "$OUT"; TOK=$W/out/e2e/n004-token.txt
redis-cli -p "$REDIS_PORT" ping >/dev/null 2>&1 || { setsid redis-server --port "$REDIS_PORT" --save '' --appendonly no > "$W/logs/redis.log" 2>&1 & sleep 1; STARTED_REDIS=1; }
redis-cli -p "$REDIS_PORT" flushall >/dev/null
i=0
for V in "$@"; do
  i=$((i+1)); MODE=resume; [ $i = 1 ] && MODE=new
  A=$W/run/e2e/n004-$V; rm -rf "$A"; cp -r "$CS/apps/cse2e" "$A"
  [ -d "$A-web" ] && mv "$A-web" "$A/.web"
  CSE2E_API_URL=http://localhost:$P REFLEX_REDIS_URL=redis://localhost:$REDIS_PORT PIDTAG=n004 "$CS/bin/start_app.sh" "$V" "$A" "$P" "$P" "$W/logs/n004/phase-$i-$V.raw.log" --env prod > /dev/null
  "$CS/bin/wait_up.sh" "http://localhost:$P/" 500 "$W/pids/n004.pid" > /dev/null || { echo "phase $i $V not up" >> "$OUT"; "$CS/bin/stop_app.sh" "$W/pids/n004.pid"; break; }
  env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 "$SB/envs/$DRIVER/bin/python" "$CS/bin/drive_resume.py" "http://localhost:$P" "$TOK" "$MODE" "$i:$V" >> "$OUT" 2>&1
  echo "   server log errors: $(grep -i -E 'traceback|mismatch|error' "$W/logs/n004/phase-$i-$V.raw.log" | grep -v -E 'react-error-boundary|errorBoundaries|Unexpected exit from worker' | head -3 | tr '\n' ' ')" >> "$OUT"
  "$CS/bin/stop_app.sh" "$W/pids/n004.pid" > /dev/null
  mv "$A/.web" "$A-web" 2>/dev/null
done
[ -n "${STARTED_REDIS:-}" ] && redis-cli -p "$REDIS_PORT" shutdown nosave >/dev/null 2>&1
cat "$OUT"
