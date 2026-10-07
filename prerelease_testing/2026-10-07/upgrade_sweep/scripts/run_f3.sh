#!/usr/bin/env bash
# F-003 re-verification: run the cvstore app (hydration rewrites of client storage) under one reflex version and drive it.
# Usage: run_f3.sh <label> <venv-dir-name under $SB/envs> <app copy under $W/f3> <PYTHONHASHSEED> [variants...]
# Aborts (exit 2) if the server did not start, so a busy port can never make the driver hit the wrong version.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/upgrade_sweep
label=$1; venv=$2; app=$3; seed=$4; shift 4
variants=${*:-a b c d e_cookie e_session f g}
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
mkdir -p $W/shots/f3
PYTHONHASHSEED=$seed VERIFY_VENV=$venv $W/bin/run_app.sh $W/f3/$app $SB/envs/$venv 3158 8158 $W/logs/$label.server.log > $W/logs/$label.start.log 2>&1 || { echo "START FAILED for $label"; cat $W/logs/$label.start.log; exit 2; }
ver=$(curl -s --noproxy '*' http://localhost:3158/ | grep -o 'reflex [0-9][0-9a-z.]*' | head -1)
echo "$label serving: $ver (expected venv $venv)" | tee -a $W/logs/f3-versions.txt
$SB/envs/driver/bin/python $W/scripts/drive_cvstore.py http://localhost:3158 $W/shots/f3 $label $variants > $W/logs/$label.driver.log 2>&1
$W/bin/stop_app.sh $W/f3/$app 3158 8158 > $W/logs/$label.stop.log 2>&1
cat $W/logs/$label.stop.log | head -3
lsof -nP -iTCP:3158 -sTCP:LISTEN -iTCP:8158 -sTCP:LISTEN 2>/dev/null | head -3
echo "$label DONE" 
