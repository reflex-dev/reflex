#!/bin/bash
# Usage: wait_200.sh <url> [max_seconds=420]  -- polls until HTTP 200 (client-side proxy bypass only)
URL=$1; MAX=${2:-420}; t=0
while [ $t -lt $MAX ]; do
  code=$(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' --max-time 5 "$URL" 2>/dev/null)
  if [ "$code" = "200" ]; then echo "200 after ${t}s"; exit 0; fi
  sleep 5; t=$((t+5))
done
echo "TIMEOUT after ${t}s (last code=$code)"; exit 1
