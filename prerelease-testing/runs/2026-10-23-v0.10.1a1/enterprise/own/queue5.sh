#!/usr/bin/env bash
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work ENT_NEW=new-ent ENT_PREV=prev-ent PREV=prev DRV_VENV=driver ENT_DRV=enterprise-drv
F=$SB/apps/enterprise/src; O=$SB/apps/enterprise/own; cd "$SB"
step() { echo; echo "##### $* $(date +%T)"; }
step gridshare new; "$O/own_run.sh" new-ent gridshare dev new
step gridshare prev; "$O/own_run.sh" prev-ent gridshare dev prev
step mcp oauth memory new; "$O/mcp_oauth_mem.sh" new-ent new 2>&1 | tail -n 8 | cut -c1-300
echo; echo "##### QUEUE5 DONE $(date +%T)"
