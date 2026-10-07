#!/usr/bin/env bash
# #7428 matrix: json_drain.py runs, one server at a time. Usage: json_matrix.sh <label> <venv-name> "<sig>:<rate> ..."
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_upgrade
lbl=$1; venv=$2; shift 2
for spec in $*; do
  sig=${spec%%:*}; rate=${spec##*:}
  echo "### $lbl $sig rate=$rate $(date +%T)"
  $SB/envs/driver/bin/python $W/scripts/json_drain.py $SB/envs/$venv $W/jsondrain 3210 8210 $sig $rate $W/shots/jsondrain/$lbl-$sig-r$rate.json 2>&1 | tail -2
  $W/bin/ports.sh 3210 8210
done
