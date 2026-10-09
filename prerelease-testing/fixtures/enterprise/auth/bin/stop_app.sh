#!/usr/bin/env bash
# Stop the server process group recorded by start_app.sh (or scripts/start_app.sh), then free the auth ports
# (3620-3639, 8620-8628, 8630-8637; never Redis 8629 / mock IdP 8638).
. "$(dirname "$0")/../../lib.sh"; W=$WORK/auth
F="$W/run/app.pgid"
if [ -s "$F" ]; then
  G=$(cat "$F")
  kill -INT -- "-$G" 2>/dev/null
  for i in $(seq 1 20); do ps -eo pgid= | grep -qw "$G" || break; sleep 0.5; done
  kill -TERM -- "-$G" 2>/dev/null; sleep 1
  kill -KILL -- "-$G" 2>/dev/null
  rm -f "$F"
fi
L=$( (lsof -t -iTCP:3620-3639 -sTCP:LISTEN; lsof -t -iTCP:8620-8628 -sTCP:LISTEN; lsof -t -iTCP:8630-8637 -sTCP:LISTEN) 2>/dev/null | sort -u)
for p in $L; do echo "leftover listener $p: $(ps -o cmd= -p $p | cut -c1-150)"; kill "$p"; done
acct_stub_stop
echo stopped
