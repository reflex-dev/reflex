#!/bin/bash
# Usage: wait_up.sh <url> [timeout_s]  -- polls until HTTP 200
URL=$1; T=${2:-420}; S=$(date +%s)
while true; do
  c=$(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' --max-time 10 "$URL")
  if [ "$c" = "200" ]; then echo "UP after $(( $(date +%s) - S ))s"; exit 0; fi
  if [ $(( $(date +%s) - S )) -gt $T ]; then echo "TIMEOUT last=$c"; exit 1; fi
  sleep 5
done
