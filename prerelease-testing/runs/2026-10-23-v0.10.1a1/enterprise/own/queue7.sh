#!/usr/bin/env bash
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work ENT_NEW=new-ent ENT_PREV=prev-ent PREV=prev DRV_VENV=driver ENT_DRV=enterprise-drv
F=$SB/apps/enterprise/src; O=$SB/apps/enterprise/own; cd "$SB"
step() { echo; echo "##### $* $(date +%T)"; }
step gridshare new r2; "$O/own_run.sh" new-ent gridshare dev new-r2
step gridshare new r3; "$O/own_run.sh" new-ent gridshare dev new-r3
step gridshare prev r2; "$O/own_run.sh" prev-ent gridshare dev prev-r2
echo; echo "##### QUEUE7 DONE $(date +%T)"
