#!/usr/bin/env bash
# One server at a time: waits for the json follow-up, then runs each sequence; per-sequence logs in logs/seq-<name>.txt.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_upgrade
until grep -q '^### followup done' $W/logs/jsondrain-followup.txt 2>/dev/null; do sleep 3; done
for s in ${*:-guide smoke fd gh ck tw twr}; do
  echo "=== seq_$s start $(date +%T)"
  $W/bin/seq_$s.sh > $W/logs/seq-$s.txt 2>&1; echo "=== seq_$s exit=$? $(date +%T)"
  $W/bin/ports.sh
  $W/bin/sync_dest.sh > /dev/null 2>&1
done
echo "=== all done $(date +%T)"
