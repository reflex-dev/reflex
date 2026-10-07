#!/usr/bin/env bash
# Usage: wait.sh <frontend_url> <backend_url> [timeout_s]
FE=$1; BE=$2; T=${3:-400}; s=$(date +%s)
while true; do
  a=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "$FE"); b=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "$BE/ping")
  [ "$a" = 200 ] && [ "$b" = 200 ] && { echo "ready after $(( $(date +%s)-s ))s"; exit 0; }
  [ $(( $(date +%s)-s )) -gt $T ] && { echo "TIMEOUT fe=$a be=$b"; exit 1; }
  sleep 3
done
