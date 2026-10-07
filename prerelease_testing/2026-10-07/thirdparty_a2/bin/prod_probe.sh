#!/bin/bash
# Usage: prod_probe.sh <venv> <rundir> <label> <skip-list> [--keep]
# Starts tp_components in prod with TP_SKIP=<skip-list>; prints whether it came up, or which page failed the build/prerender.
SB=${SB:-/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad}
W=$SB/apps/thirdparty_a2
V=$1; APP=$2; LABEL=$3; SKIP=$4; KEEP=${5:-}
LOG=$W/logs/tp_components-$LABEL-prod.log
TP_SKIP=$SKIP REFLEX_API_URL=http://localhost:3510 $W/bin/start_app.sh $V $APP 3510 3510 $LOG --env prod >/dev/null
PIDF=$W/pids/$(basename $APP)-$V.pid
$W/bin/wait_up.sh http://localhost:3510/ 300 $PIDF | tail -1
grep -E "Prerender: Request failed|MISSING_EXPORT|Build failed|Creating Production Build failed|SyntaxError|ReferenceError" $LOG | cut -c1-200 | head -5
if [ "$KEEP" != "--keep" ]; then $W/bin/stop_app.sh $PIDF >/dev/null; fi
