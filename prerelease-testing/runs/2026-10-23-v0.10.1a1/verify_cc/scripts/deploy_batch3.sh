#!/usr/bin/env bash
# Batch 3 (after batch 2): clean positive control on prev — `--loglevel debug` with no stub scenario (0.2.0 cannot retry a 409).
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
R=$SB/apps/verify_cc
BASE="deploy --no-interactive --app-id 00000000-0000-0000-0000-000000000a01 --token good-token"
while ! grep -q BATCH2-DONE $R/logs/deploy_batch2.log 2>/dev/null; do sleep 5; done
CP_PORT=8741 SCENARIO='{}' $R/scripts/run_cli.sh prev cc1-debug-plain -- $BASE --loglevel debug
echo BATCH3-DONE
