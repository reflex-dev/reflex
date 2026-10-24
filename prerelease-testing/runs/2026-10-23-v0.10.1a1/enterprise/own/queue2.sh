#!/usr/bin/env bash
# second server queue: positive controls, deeplink (#7360 / ENT-16 G), a4 matrix + MCP (part 3), AG Grid demo venv, pending-login prod
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work ENT_NEW=new-ent ENT_PREV=prev-ent PREV=prev DRV_VENV=driver ENT_DRV=enterprise-drv
F=$SB/apps/enterprise/src; O=$SB/apps/enterprise/own; cd "$SB"
step() { echo; echo "##### $* $(date +%T)"; }
step xff rerun new-h0; "$O/xff_run.sh" new-ent 0 new-h0 2>&1 | tail -n 12
step xff rerun new-h1; "$O/xff_run.sh" new-ent 1 new-h1 2>&1 | tail -n 12
step xff rerun prev-h0; "$O/xff_run.sh" prev-ent 0 prev-h0 0.10.0 2>&1 | tail -n 12
step pending_login D rerun new dev; "$F/auth/bin/infra.sh" start; "$O/pl_run.sh" new-ent new 1 dev; "$F/auth/bin/infra.sh" stop
step gridshare rerun new; "$O/own_run.sh" new-ent gridshare dev new
step gridshare rerun prev; "$O/own_run.sh" prev-ent gridshare dev prev
step control N-025 rxe0.9.6 aggrid_min prod; "$F/grid/bin/run.sh" enterprise-ctrl-rxe96 aggrid_min prod 3601 aggrid_min_ctrlrxe96_prod 2>&1 | tail -n 4; tail -n 8 "$WORK/grid/out/aggrid_min_ctrlrxe96_prod.txt" | cut -c1-250
step control N-032 reflex0.10.0a3 vauth dev; "$F/auth/bin/seq_ent_auth.sh" enterprise-ctrl-a3 ctrla3 1 2>&1 | grep -E "SUMMARY|race|tracebacks|###" | cut -c1-300
step deeplink new dev; "$F/auth/bin/seq_deeplink.sh" new-ent new dev 2>&1 | tail -n 14 | cut -c1-300
step mcp anon+oauth new; "$O/mcp_run.sh" new-ent new 2>&1 | tail -n 20 | cut -c1-300
step a4 matrix + MCP new; "$F/auth/bin/seq_ent_auth.sh" new-ent new 3 2>&1 | tail -n 25 | cut -c1-300
step n033 default workers new; "$F/auth/bin/seq_n033.sh" new-ent new 2>&1 | tail -n 14 | cut -c1-300
step ag_demo new prod; "$F/grid/bin/ag_demo.sh" enterprise-demo-new prod new 2>&1 | tail -n 20 | cut -c1-300
step pending_login new prod; "$F/auth/bin/infra.sh" start; "$O/pl_run.sh" new-ent newp 1 prod; "$F/auth/bin/infra.sh" stop
echo; echo "##### QUEUE2 DONE $(date +%T)"
