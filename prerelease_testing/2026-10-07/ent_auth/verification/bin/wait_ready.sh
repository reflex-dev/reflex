#!/usr/bin/env bash
# Usage: wait_ready.sh <frontend_url> <backend_url> [timeout_s]
FE=$1; BE=$2; T=${3:-360}; start=$(date +%s)
while true; do
  a=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "$FE"); b=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "$BE/ping")
  if [ "$a" = 200 ] && [ "$b" = 200 ]; then echo "ready after $(( $(date +%s)-start ))s"; exit 0; fi
  if [ $(( $(date +%s)-start )) -gt $T ]; then echo "TIMEOUT fe=$a be=$b"; exit 1; fi
  sleep 5
done
