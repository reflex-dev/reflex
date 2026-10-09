#!/bin/bash
# Usage: run_noinit.sh <venv> [FP=3142] [BP=8142]
#   Pre-existing (0.9.12 .. 0.10.0a5): an app package WITHOUT __init__.py compiles and serves, but every state update fails
#   in the browser: console "Cannot process state update: no dispatch function for substate(s) ..." (state names lose the
#   module segment, rtr___rs instead of rtr___rtr___rs); is_hydrated stays false. Builds src/rtr minus __init__.py in the
#   work dir, prints the console errors of / (dbg_console.py). Expected while unfixed: the dispatch-function errors.
. "$(dirname "$0")/env.sh"
V=$1; FP=${2:-3142}; BP=${3:-8142}
S=$W/src_noinit/rtr; rm -rf "$S" "$W/run/rtr-noinit/rtr"; mkdir -p "$S/rtr"
cp "$F/src/rtr/rxconfig.py" "$S/"; cp "$F/src/rtr/rtr/rtr.py" "$S/rtr/"
"$F/scripts/srv.sh" start rtr-noinit "$V" dev "$S" "$FP" "$BP" > /dev/null || exit 1
$NP "$DRV" "$F/drivers/waitsrv.py" 400 "http://localhost:$FP/" "http://localhost:$BP/ping" > /dev/null; sleep 3
echo "== $V no __init__.py"; $NP "$DRV" "$F/drivers/dbg_console.py" "http://localhost:$FP/" 5 2>&1 | grep -iE "error|PAGEERROR|dispatch" | cut -c1-220
"$F/scripts/srv.sh" stop rtr-noinit > /dev/null
