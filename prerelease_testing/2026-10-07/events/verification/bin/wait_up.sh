#!/usr/bin/env bash
# usage: wait_up.sh <dev|prod> [timeout_s]   -- polls frontend (and backend /_health) for up to timeout (default 420 s)
MODE=$1; T=${2:-420}
if [ "$MODE" = prod ]; then FE=http://localhost:8641/; BE=http://localhost:8641/_health; else FE=http://localhost:3640/; BE=http://localhost:8640/_health; fi
start=$(date +%s)
while true; do
  a=$(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' --max-time 3 "$FE" 2>/dev/null)
  b=$(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' --max-time 3 "$BE" 2>/dev/null)
  el=$(( $(date +%s) - start ))
  if [ "$a" = 200 ] && [ "$b" = 200 ]; then echo "UP after ${el}s fe=$a be=$b"; curl --noproxy '*' -s --max-time 3 "$BE"; echo; exit 0; fi
  if [ $el -gt $T ]; then echo "TIMEOUT after ${el}s fe=$a be=$b"; exit 1; fi
  sleep 3
done
