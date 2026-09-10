#!/bin/bash
# wait_up.sh <url> [timeout_s]  -- poll until HTTP 200 (proxy bypassed)
url=$1; t=${2:-360}; end=$((SECONDS+t))
while [ $SECONDS -lt $end ]; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --noproxy '*' "$url" 2>/dev/null)
  if [ "$code" = "200" ]; then echo "UP $url after $SECONDS s"; exit 0; fi
  sleep 2
done
echo "TIMEOUT waiting for $url (last code $code)"; exit 1
