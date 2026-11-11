#!/bin/bash
# Usage: wait_up.sh <url> [timeout_s=360]  -- polls until HTTP 200.
U=$1; T=${2:-360}; S=$(date +%s)
while true; do
  c=$(NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 curl --noproxy '*' -s -o /dev/null -w '%{http_code}' "$U")
  if [ "$c" = "200" ]; then echo "UP after $(( $(date +%s) - S ))s"; exit 0; fi
  if [ $(( $(date +%s) - S )) -gt $T ]; then echo "TIMEOUT last=$c"; exit 1; fi
  sleep 3
done
