#!/usr/bin/env bash
# usage: demo_hooks_run.sh <venv> <label> <prod|dev> [demos="dnd mantine"]  -- demo drivers + hook_order scan + deprecation count
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work; F=$SB/apps/enterprise/src; . "$F/lib.sh"; GW=$WORK/grid; B=$F/grid/bin; O=$SB/apps/enterprise/own
V=$1; L=$2; M=$3; DEMOS=${4:-dnd mantine}
for a in $DEMOS; do
  echo "### demo $a $M $V ($L) $(date +%T)"
  "$B/demo.sh" "$V" "$a" "$M" "$L" 2>&1 | tail -n 8 | cut -c1-300
  LOGF=$GW/logs/$a-$M-$L.log
  echo "deprecation lines in server log: position=$(grep -c 'VarData(position' "$LOGF") HookPosition=$(grep -c 'HookPosition' "$LOGF") total-deprecated=$(grep -ci 'deprecated' "$LOGF") vite-public-warn=$(grep -c 'Files in the public directory' "$LOGF")"
  grep -i "deprecat" "$LOGF" | sed 's/^ *//' | cut -c1-200 | sort | uniq -c | sort -rn | head -5
  (cd "$O/probes" && "$DRVPY" -I hook_order.py "$GW/runs/${a}_demo_${V//-/}/.web" "$a-$M-$L" 2>&1 | tail -n 12 | cut -c1-300)
done
