#!/bin/bash
# wait for batch1, then run batch2
W=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/a5_hydration_router
until grep -q BATCH1_DONE $W/results/p2/batch1.out; do sleep 5; done
$W/scripts/p2_batch2.sh > $W/results/p2/batch2.out 2>&1
