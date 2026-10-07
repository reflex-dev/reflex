#!/usr/bin/env bash
# Stop the app process group started by start.sh and check the app ports are closed.
W=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/verify_ent_auth
F=$W/run/app.pgid
if [ -s $F ]; then
  G=$(cat $F); kill -INT -- -$G 2>/dev/null
  for i in $(seq 1 20); do ps -eo pgid= | grep -qw "$G" || break; sleep 0.5; done
  kill -TERM -- -$G 2>/dev/null; sleep 1; kill -KILL -- -$G 2>/dev/null; rm -f $F
fi
for p in $( (lsof -t -iTCP:3620-3628 -sTCP:LISTEN; lsof -t -iTCP:8620-8628 -sTCP:LISTEN) 2>/dev/null | sort -u); do echo "leftover $p: $(ps -o cmd= -p $p | cut -c1-120)"; kill $p; done
echo stopped
