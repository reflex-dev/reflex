#!/usr/bin/env bash
# N-025 quick re-check (entv fixture prod + aggrid_min probe) and dnd/flow/mantine/map demo smoke on <venv> (default $ENT_NEW).
# Usage: seq_grid.sh [venv] [label] [parts=12]   (part 2 needs bin/fetch_demos.sh first)
set -u
. "$(dirname "$0")/../../lib.sh"; fx_sync grid; GW=$WORK/grid; B=$FX/grid/bin; cd "$GW"
V=${1:-$ENT_NEW}; L=${2:-new}; PARTS=${3:-12}; VV=${V//-/}
if [[ $PARTS == *1* ]]; then
  echo "### entv prod $V $(date +%T)"; "$B/run.sh" $V entv prod 3600 entv_${VV}_prod
  tail -n 25 out/entv_${VV}_prod.txt | cut -c1-250
  echo "### aggrid_min prod $V $(date +%T)"; "$B/run.sh" $V aggrid_min prod 3601 aggrid_min_${VV}_prod
  tail -n 8 out/aggrid_min_${VV}_prod.txt | cut -c1-250
  echo "server tracebacks: entv=$(grep -c Traceback logs/entv_${VV}_prod.log) aggrid_min=$(grep -c Traceback logs/aggrid_min_${VV}_prod.log)"
fi
if [[ $PARTS == *2* ]]; then
  for a in dnd flow mantine map; do echo "### demo $a prod $V $(date +%T)"; "$B/demo.sh" $V $a prod $L; done
fi
echo "### grid done $(date +%T)"
