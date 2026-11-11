#!/usr/bin/env bash
# Batch 2 (runs after batch 1, same app dirs):
#  cc1-narr-*   : status narration (intermediate statuses from GET deployments/<id>/status) at default vs debug level
#  cc1-bounds500: WARNING + ERROR visibility after export at the default level (instance_bounds -> 500)
#  cc2-deploy   : CC-2 through the real `reflex deploy` (dir symlink leaving the app root), both venvs
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
R=$SB/apps/verify_cc
RUN=$R/scripts/run_cli.sh
BASE="deploy --no-interactive --app-id 00000000-0000-0000-0000-000000000a01 --token good-token"
NARR='{"responses":{"GET deployments/[^/]+/status":[{"status":200,"json":"Deployment is being built."},{"status":200,"json":"Deployment is being built."},{"status":200,"json":"Deployment is being provisioned."},{"status":200,"json":"deployment completed successfully"}]}}'
B500='{"responses":{"POST apps/00000000-0000-0000-0000-000000000a01/instance_bounds":[{"status":500,"json":{"detail":"internal"}}]}}'
while ! grep -q BATCH1-DONE $R/logs/deploy_batch1.log 2>/dev/null; do sleep 5; done
export CP_PORT=8740
SCENARIO=$NARR $RUN new cc1-narr-default -- $BASE
SCENARIO=$NARR $RUN new cc1-narr-debug   -- $BASE --loglevel debug
SCENARIO=$B500 $RUN new cc1-bounds500    -- $BASE --min-instances 1 --max-instances 2
export CP_PORT=8741
SCENARIO=$NARR $RUN prev cc1-narr-default -- $BASE
# CC-2 via deploy: add the symlink, run, remove it again.
ln -s $R/sym/outside_target $R/app-new/data;  CP_PORT=8740 SCENARIO='{}' $RUN new  cc2-deploy -- $BASE; rm -f $R/app-new/data
ln -s $R/sym/outside_target $R/app-prev/data; CP_PORT=8741 SCENARIO='{}' $RUN prev cc2-deploy -- $BASE; rm -f $R/app-prev/data
ls /tmp | grep -c '^tmp' > $R/logs/cc2-deploy.tmpdirs-after.txt
echo BATCH2-DONE
