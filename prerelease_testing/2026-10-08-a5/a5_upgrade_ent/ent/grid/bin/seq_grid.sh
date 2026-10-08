#!/usr/bin/env bash
# N-025 quick re-check (entv fixture, prod; + explorer aggrid_min probe) and dnd/flow/mantine/map demo smoke on <venv> (default a4-ent).
# Usage: seq_grid.sh [venv] [label] [parts=12]
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; GW=$SB/apps/a5_upgrade_ent/ent/grid; cd $GW
V=${1:-a4-ent}; L=${2:-a4}; PARTS=${3:-12}; VV=${V//-/}
if [[ $PARTS == *1* ]]; then
  echo "### entv prod $V $(date +%T)"; bin/run.sh $V entv prod 3470 entv_${VV}_prod
  tail -n 25 out/entv_${VV}_prod.txt | cut -c1-250
  echo "### aggrid_min prod $V $(date +%T)"; bin/run.sh $V aggrid_min prod 3471 aggrid_min_${VV}_prod
  tail -n 8 out/aggrid_min_${VV}_prod.txt | cut -c1-250
  echo "server tracebacks: entv=$(grep -c Traceback logs/entv_${VV}_prod.log) aggrid_min=$(grep -c Traceback logs/aggrid_min_${VV}_prod.log)"
fi
if [[ $PARTS == *2* ]]; then
  for a in dnd flow mantine map; do echo "### demo $a prod $V $(date +%T)"; bin/demo.sh $V $a prod $L; done
fi
echo "### grid done $(date +%T)"
