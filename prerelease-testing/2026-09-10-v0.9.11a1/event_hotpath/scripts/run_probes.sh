#!/bin/bash
# Runs the offline name/fast-path probes under each venv (low priority), sequentially.
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/event_hotpath
cd $A/scripts
for v in smoke hp313 base0910; do
  echo "=== probe_names2 $v $(date +%T)"
  REFLEX_TELEMETRY_ENABLED=false nice -n 15 $SB/envs/$v/bin/python probe_names2.py --out $A/logs2/probe2_$v.jsonl > $A/logs2/probe2_$v.out 2> $A/logs2/probe2_$v.err
done
for v in smoke hp313 base0910; do
  echo "=== probe_names $v $(date +%T)"
  REFLEX_TELEMETRY_ENABLED=false nice -n 15 $SB/envs/$v/bin/python probe_names.py > $A/logs2/probe_names_$v.jsonl 2> $A/logs2/probe_names_$v.err
done
echo "ALL PROBES DONE $(date +%T)"
