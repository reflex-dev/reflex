#!/usr/bin/env bash
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work ENT_NEW=new-ent ENT_PREV=prev-ent PREV=prev DRV_VENV=driver ENT_DRV=enterprise-drv
F=$SB/apps/enterprise/src; O=$SB/apps/enterprise/own; cd "$SB"
step() { echo; echo "##### $* $(date +%T)"; }
step consent new redis; REDIS=1 "$O/mcp_consent_run.sh" new-ent new-redis
step consent rxe97 redis; REDIS=1 "$O/mcp_consent_run.sh" enterprise-ctrl-rxe97 rxe97-redis
step consent new memory; REDIS=0 "$O/mcp_consent_run.sh" new-ent new-mem
echo; echo "##### QUEUE8 DONE $(date +%T)"
