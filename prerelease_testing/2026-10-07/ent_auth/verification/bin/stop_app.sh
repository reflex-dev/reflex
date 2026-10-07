#!/usr/bin/env bash
# Kill the app process group, then any leftover listener on 3720/8720/8721.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_ent_auth_0
if [ -f $W/logs/app.pid ]; then
  P=$(cat $W/logs/app.pid); kill -INT -- -$P 2>/dev/null; sleep 4; kill -KILL -- -$P 2>/dev/null; rm -f $W/logs/app.pid
fi
for port in 3720 8720 8721; do
  for pid in $(lsof -t -nP -iTCP:$port -sTCP:LISTEN 2>/dev/null); do kill -KILL $pid 2>/dev/null; done
done
sleep 1
lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | awk '$9 ~ /:(37[2-3][0-9]|87[2-3][0-9])$/ {print "still:",$1,$2,$9}'
