#!/usr/bin/env bash
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work ENT_NEW=new-ent ENT_PREV=prev-ent PREV=prev DRV_VENV=driver ENT_DRV=enterprise-drv
F=$SB/apps/enterprise/src; O=$SB/apps/enterprise/own; cd "$SB"
step() { echo; echo "##### $* $(date +%T)"; }
step gridshare new; "$O/own_run.sh" new-ent gridshare dev new
step gridshare prev; "$O/own_run.sh" prev-ent gridshare dev prev
step mcp oauth redis rxe0.9.7; "$O/mcp_run.sh" enterprise-ctrl-rxe97 rxe97 2>&1 | tail -n 10 | cut -c1-300
echo; echo "##### QUEUE6 DONE $(date +%T)"
