#!/usr/bin/env bash
# third queue: HYD-15 (entr dev) rerun new + prev with the fixed driver, flow reload A/B (N-026) new vs prev
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work ENT_NEW=new-ent ENT_PREV=prev-ent PREV=prev DRV_VENV=driver ENT_DRV=enterprise-drv
F=$SB/apps/enterprise/src; O=$SB/apps/enterprise/own; cd "$SB"
step() { echo; echo "##### $* $(date +%T)"; }
step xff rerun2 new-h0; "$O/xff_run.sh" new-ent 0 new-h0 2>&1 | tail -n 10
step xff rerun2 new-h1; "$O/xff_run.sh" new-ent 1 new-h1 2>&1 | tail -n 10
step xff rerun2 prev-h0; "$O/xff_run.sh" prev-ent 0 prev-h0 0.10.0 2>&1 | tail -n 10
step hyd15 rerun new; "$O/own_run.sh" new-ent hyd15 dev new2
step hyd15 prev; "$O/own_run.sh" prev-ent hyd15 dev prev
step flow prod prev; "$F/grid/bin/demo.sh" prev-ent flow prod prev 2>&1 | tail -n 6 | cut -c1-300
step flow reload AB; ORDER="new-ent prev-ent" "$F/grid/bin/flow_reload_ab.sh" 3 2>&1 | tail -n 12 | cut -c1-300
echo; echo "##### QUEUE3 DONE $(date +%T)"
