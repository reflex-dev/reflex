#!/usr/bin/env bash
R=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad/apps/hmr_runtime
until grep -q "CHAIN-DONE" $R/logs/chain.log 2>/dev/null; do sleep 5; done
$R/scripts/run_pre7048_safari.sh > $R/logs/run_pre7048_pipeline.log 2>&1
echo CHAIN2-DONE
