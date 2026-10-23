set -u
cd /tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa/apps/cloud_cli
V=$1; export CP_PORT=$2
R=./run_cli.sh; BASE="deploy --no-interactive --app-id 00000000-0000-0000-0000-000000000a01 --token good-token"
SCENARIO='{"responses":{"POST deployments":[{"status":409,"headers":{"x-reflex-error-code":"app_scaling"},"json":{"detail":"The scale is finishing."}},{"status":409,"headers":{"x-reflex-error-code":"app_scaling"},"json":{"detail":"The scale is finishing."}},{"status":200,"json":"00000000-0000-0000-0000-00000000d001"}]}}' $R $V r01-scaling-retry2 -- $BASE
SCENARIO='{"responses":{"POST apps/00000000-0000-0000-0000-000000000a01/instance_bounds":[{"status":409,"headers":{"x-reflex-error-code":"instance_bounds_scale_conflict"},"json":{"detail":"The scale is finishing."}},{"status":409,"headers":{"x-reflex-error-code":"instance_bounds_scale_conflict"},"json":{"detail":"The scale is finishing."}},{"status":200,"json":{"status":"ok","applied_now":false}}]}}' $R $V r07-bounds-retry2 -- $BASE --min-instances 1 --max-instances 2
SCENARIO='{"responses":{"POST apps/00000000-0000-0000-0000-000000000a01/instance_bounds":[{"status":500,"json":{"detail":"internal"}}]}}' $R $V r08-bounds-500 -- $BASE --min-instances 1 --max-instances 2
SCENARIO='{"responses":{"POST apps/00000000-0000-0000-0000-000000000a01/instance_bounds":[{"status":200,"json":"ok"}]}}' $R $V r09-bounds-undecodable -- $BASE --min-instances 1 --max-instances 2
SCENARIO='{"responses":{"POST apps/00000000-0000-0000-0000-000000000a01/instance_bounds":[{"drop":true}]}}' $R $V r11-bounds-drop -- $BASE --min-instances 1 --max-instances 2
SCENARIO='{"responses":{"POST deployments":[{"status":409,"headers":{"x-reflex-error-code":"app_busy"},"json":{"detail":"a deployment is already in progress for this app"}}]}}' $R $V r12-bounds-ok-submit-busy -- $BASE --min-instances 1 --max-instances 2
CP_PREFIX=/proxy/v2 SCENARIO='{"responses":{"POST deployments":[{"status":409,"headers":{"x-reflex-error-code":"app_scaling"},"json":{"detail":"The scale is finishing."}},{"status":200,"json":"00000000-0000-0000-0000-00000000d001"}]}}' $R $V r13-prefix-scaling-retry -- $BASE
echo DONE
