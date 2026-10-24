#!/usr/bin/env bash
# first server queue after the auth suite: pending-login, XFF, N-032 prod, grid part 1+2, dnd/mantine dev, prev-ent demos, own apps
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work ENT_NEW=new-ent ENT_PREV=prev-ent PREV=prev DRV_VENV=driver ENT_DRV=enterprise-drv
F=$SB/apps/enterprise/src; O=$SB/apps/enterprise/own; cd "$SB"
step() { echo; echo "##### $* $(date +%T)"; }
step pending_login new dev; "$F/auth/bin/infra.sh" start; "$O/pl_run.sh" new-ent new 2 dev; "$F/auth/bin/infra.sh" stop
step xff new-h0; "$O/xff_run.sh" new-ent 0 new-h0 2>&1 | tail -n 12
step xff new-h1; "$O/xff_run.sh" new-ent 1 new-h1 2>&1 | tail -n 12
step xff prev-h0; "$O/xff_run.sh" prev-ent 0 prev-h0 0.10.0 2>&1 | tail -n 12
step n032 prod new; "$F/auth/bin/seq_n032_prod.sh" new-ent new 2>&1 | tail -n 12 | cut -c1-300
step grid new 12; "$F/grid/bin/seq_grid.sh" new-ent new 12 2>&1 | cut -c1-300
step demos dev new; "$O/demo_hooks_run.sh" new-ent new dev
step hook_order prod new; (cd "$O/probes" && for a in dnd mantine; do "$SB/envs/driver/bin/python" -I hook_order.py "$WORK/grid/runs/${a}_demo_newent/.web" "$a-prod-new" | tail -n 6; done)
step demos prod prev; "$O/demo_hooks_run.sh" prev-ent prev prod
step demos dev prev; "$O/demo_hooks_run.sh" prev-ent prev dev
step gridshare new; "$O/own_run.sh" new-ent gridshare dev new
step gridshare prev; "$O/own_run.sh" prev-ent gridshare dev prev
step hyd15 new; "$O/own_run.sh" new-ent hyd15 dev new
echo; echo "##### QUEUE1 DONE $(date +%T)"
