#!/usr/bin/env bash
# after the restart: XFF REST reruns (fixed route), gridshare DOM debug, hyd15 prev, MCP oauth on prev, N-032 control a2, flow prev + A/B
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work ENT_NEW=new-ent ENT_PREV=prev-ent PREV=prev DRV_VENV=driver ENT_DRV=enterprise-drv
F=$SB/apps/enterprise/src; O=$SB/apps/enterprise/own; cd "$SB"; . "$F/lib.sh"
step() { echo; echo "##### $* $(date +%T)"; }
step xff3 new-h0; "$O/xff_run.sh" new-ent 0 new-h0 2>&1 | tail -n 10
step xff3 new-h1; "$O/xff_run.sh" new-ent 1 new-h1 2>&1 | tail -n 10
step xff3 prev-h0; "$O/xff_run.sh" prev-ent 0 prev-h0 0.10.0 2>&1 | tail -n 10
step gridshare dom debug new; GW=$WORK/grid; RUN=$GW/runs/gridshare_newent; (cd "$O/gridshare" && tar --exclude=.web --exclude=__pycache__ -cf - .) | (cd "$RUN" && tar -xf -)
  "$F/grid/bin/start.sh" new-ent "$RUN" "$GW/logs/gridshare-dev-dbg.log" dev 3611 8611 QA_EXPECT_VENV=new-ent && (cd "$O/probes" && $NP "$DRVPY" gridshare_dom.py http://localhost:3611 2>&1 | cut -c1-1500); "$F/grid/bin/stop.sh"
step hyd15 prev; "$O/own_run.sh" prev-ent hyd15 dev prev
step mcp anon+oauth prev; "$O/mcp_run.sh" prev-ent prev 2>&1 | tail -n 12 | cut -c1-300
step control N-032 reflex0.10.0a2 vauth dev; "$F/auth/bin/seq_ent_auth.sh" enterprise-ctrl-a2 ctrla2 1 2>&1 | grep -E "SUMMARY|race|tracebacks|###" | cut -c1-300
step flow prod prev; "$F/grid/bin/demo.sh" prev-ent flow prod prev 2>&1 | tail -n 6 | cut -c1-300
step flow reload AB; ORDER="new-ent prev-ent" "$F/grid/bin/flow_reload_ab.sh" 3 2>&1 | tail -n 12 | cut -c1-300
echo; echo "##### QUEUE4 DONE $(date +%T)"
