#!/usr/bin/env bash
# CC-1 end-to-end: real `reflex deploy` against the fake control plane, scaling-conflict scenario (2x409 app_scaling, then 200).
# new -> stub :8740, prev -> stub :8741. Labels: cc1-<variant>.
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
R=$SB/apps/verify_cc
RUN=$R/scripts/run_cli.sh
BASE="deploy --no-interactive --app-id 00000000-0000-0000-0000-000000000a01 --token good-token"
SCALING='{"responses":{"POST deployments":[{"status":409,"headers":{"x-reflex-error-code":"app_scaling"},"json":{"detail":"The scale is finishing."}},{"status":409,"headers":{"x-reflex-error-code":"app_scaling"},"json":{"detail":"The scale is finishing."}},{"status":200,"json":"00000000-0000-0000-0000-00000000d001"}]}}'
export CP_PORT=8740
SCENARIO=$SCALING $RUN new cc1-debug   -- $BASE --loglevel debug
SCENARIO=$SCALING $RUN new cc1-default -- $BASE
SCENARIO=$SCALING $RUN new cc1-info    -- $BASE --loglevel info
SCENARIO=$SCALING $RUN new cc1-envinfo REFLEX_LOGLEVEL=info -- $BASE
SCENARIO=$SCALING $RUN new cc1-json    -- $BASE --json
export CP_PORT=8741
SCENARIO=$SCALING $RUN prev cc1-debug   -- $BASE --loglevel debug
SCENARIO='{}'     $RUN prev cc1-default -- $BASE
SCENARIO='{}'     $RUN prev cc1-envinfo REFLEX_LOGLEVEL=info -- $BASE
echo BATCH1-DONE
