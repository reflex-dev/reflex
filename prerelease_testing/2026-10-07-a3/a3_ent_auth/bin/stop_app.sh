#!/usr/bin/env bash
# Stop the server process group recorded by start_app.sh, then verify the app ports are closed.
W=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/a3_ent_auth
F="$W/run/app.pgid"
if [ -s "$F" ]; then
  G=$(cat "$F")
  kill -INT -- "-$G" 2>/dev/null
  for i in $(seq 1 20); do ps -eo pgid= | grep -qw "$G" || break; sleep 0.5; done
  kill -TERM -- "-$G" 2>/dev/null; sleep 1
  kill -KILL -- "-$G" 2>/dev/null
  rm -f "$F"
fi
L=$( (lsof -t -iTCP:3340-3359 -sTCP:LISTEN; lsof -t -iTCP:8340-8348 -sTCP:LISTEN; lsof -t -iTCP:8350-8357 -sTCP:LISTEN) 2>/dev/null | sort -u)
for p in $L; do echo "leftover listener $p: $(ps -o cmd= -p $p | cut -c1-150)"; kill "$p"; done
echo stopped
