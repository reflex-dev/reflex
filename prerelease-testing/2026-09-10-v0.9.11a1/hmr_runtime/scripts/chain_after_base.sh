#!/usr/bin/env bash
R=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad/apps/hmr_runtime
until grep -q "PIPELINE-DONE\|START-FAILED" $R/logs/run_base_pipeline.log 2>/dev/null; do sleep 5; done
echo "base pipeline finished; starting knobs"
$R/scripts/run_knobs.sh > $R/logs/run_knobs_pipeline.log 2>&1
echo "knobs finished; starting base safari headmeta"
$R/scripts/run_base_safari_headmeta.sh > $R/logs/run_base_safari_pipeline.log 2>&1
echo CHAIN-DONE
