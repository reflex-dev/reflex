#!/usr/bin/env bash
# Re-run the guide app (with the same-state-var handler added) on 0.9.12 and a3 dev.
set -u; . $(dirname $0)/common.sh
A=$W/guide/app; FP=3214; BP=8214; S=$W/shots/guide
for v in stable a3; do
  rm -rf $A/.web $A/.states
  echo "### guide2 $v dev $(date +%T)"; $W/bin/run_app.sh $A $SB/envs/$v $FP $BP $W/logs/guide2-$v-dev.server.log || continue
  $DRV $W/scripts/drive_guide.py http://localhost:$FP $S guide2-$v-dev --defaults-tabs 1 | grep -E '^\[(FAIL|ANOM)|^== '
  $W/bin/stop_app.sh $A $FP $BP
done
