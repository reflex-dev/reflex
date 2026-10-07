#!/bin/bash
# Usage: wait_up.sh <url> [timeout_s] [pidfile]
URL=$1; T=${2:-400}; PIDF=${3:-}
for i in $(seq 1 $T); do
  code=$(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' "$URL")
  if [ "$code" = "200" ]; then echo "UP after ${i}s ($URL)"; exit 0; fi
  if [ -n "$PIDF" ] && ! kill -0 "$(cat $PIDF)" 2>/dev/null; then echo "SERVER DIED after ${i}s ($URL)"; exit 2; fi
  sleep 1
done
echo "NOT UP after ${T}s ($URL) last=$code"; exit 1
