#!/usr/bin/env bash
# Usage: wait_ready.sh <frontend_url> <backend_url> [timeout_s=360]
FU=$1; BU=$2; TO=${3:-360}
for i in $(seq 1 $TO); do
  a=$(curl -s --noproxy '*' -o /dev/null -w "%{http_code}" "$FU" 2>/dev/null)
  b=$(curl -s --noproxy '*' "$BU/ping" 2>/dev/null)
  if [ "$a" = "200" ] && [ "$b" = '"pong"' ]; then echo "ready after ${i}s"; exit 0; fi
  sleep 1
done
echo "NOT READY after ${TO}s (frontend=$a backend=$b)"; exit 1
