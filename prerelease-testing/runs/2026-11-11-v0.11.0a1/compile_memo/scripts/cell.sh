#!/usr/bin/env bash
# Usage: cell.sh <label> <venv> <appdir> <AM true|false> <RC true|false> [modes: "compile export prod dev"] [pages]
# Runs one matrix cell; results in results/<label>_*.json, logs/<label>_*.log
set -u
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
B=$SB/apps/compile_memo; S=$B/scripts; L=$B/logs; R=$B/results
label=$1; venv=$2; app=$3; am=$4; rc=$5; modes=${6:-"compile export prod dev"}; pages=${7:-}
export REFLEX_TELEMETRY_ENABLED=false REFLEX_AUTO_MEMOIZE=$am REFLEX_REACT_COMPILER=$rc
cd $app
for m in $modes; do
  case $m in
  compile)
    s=$(date +%s.%N); $SB/envs/$venv/bin/reflex compile > $L/${label}_compile.log 2>&1; rcd=$?
    e=$(date +%s.%N); echo "$label compile rc=$rcd wall=$(echo "$e - $s" | bc)s $(grep -o 'compiled successfully in [0-9.]* seconds' $L/${label}_compile.log)"
    grep -i -E "warning|experimental|auto_memoize" $L/${label}_compile.log | head -5 ;;
  export)
    rm -rf .web/build
    s=$(date +%s.%N); $SB/envs/$venv/bin/reflex export --frontend-only --no-zip > $L/${label}_export.log 2>&1; rce=$?
    e=$(date +%s.%N)
    js=$(find .web/build/client -name '*.js' | wc -l); jsb=$(find .web/build/client -name '*.js' -printf '%s\n' | awk '{s+=$1} END {print s}')
    tot=$(du -sb .web/build/client | cut -f1)
    echo "$label export rc=$rce wall=$(echo "$e - $s" | bc)s js_files=$js js_bytes=$jsb client_bytes=$tot"
    rm -rf $B/builds/$label; mkdir -p $B/builds/$label; cp -r .web/build/client $B/builds/$label/ 2>/dev/null ;;
  prod|dev)
    $S/srv.sh start ${label}_$m $venv $m $app 3300 $([ $m = prod ] && echo 3300 || echo 8300) || { echo "start failed"; continue; }
    ( cd $S && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 900 $SB/envs/driver/bin/python drive_cm.py http://localhost:3300 $R/${label}_$m.json $pages > /dev/null 2>&1 )
    $S/srv.sh stop ${label}_$m
    echo "== $label $m"; $SB/envs/driver/bin/python $S/summ.py $R/${label}_$m.json ;;
  esac
done
