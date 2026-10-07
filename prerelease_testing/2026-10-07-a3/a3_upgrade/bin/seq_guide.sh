#!/usr/bin/env bash
# Upgrade-guide e2e app: a3 dev, a3 prod + Redis (multi-worker), 0.9.12 dev, a2 dev (shared read-only venvs).
set -u; . $(dirname $0)/common.sh
A=$W/guide/app; FP=3214; BP=8214; S=$W/shots/guide; mkdir -p $S
for v in a3 stable alpha2; do
  rm -rf $A/.web $A/.states
  echo "### guide $v dev $(date +%T)"; $W/bin/run_app.sh $A $SB/envs/$v $FP $BP $W/logs/guide-$v-dev.server.log || continue
  $DRV $W/scripts/drive_guide.py http://localhost:$FP $S guide-$v-dev --defaults-tabs 2 | grep -v '^\[PASS'
  $W/bin/stop_app.sh $A $FP $BP
done
echo "### guide a3 prod+redis $(date +%T)"
redis-server --port 8209 --save '' --appendonly no > $W/logs/guide-redis.log 2>&1 & RPID=$!; sleep 1
REFLEX_REDIS_URL=redis://localhost:8209 REFLEX_API_URL=http://localhost:$FP $W/bin/run_app.sh $A $SB/envs/a3 $FP $FP $W/logs/guide-a3-prod.server.log --env prod && {
  pstree -p $(cat $W/run/app.pid) > $W/logs/guide-a3-prod-pstree.txt 2>/dev/null
  echo "granian workers (python children of the server process): $(grep -o 'python[^(]*([0-9]*)' $W/logs/guide-a3-prod-pstree.txt | wc -l) total python procs in tree"
  $DRV $W/scripts/drive_guide.py http://localhost:$FP $S guide-a3-prod --defaults-tabs 8 | grep -v '^\[PASS'
  $W/bin/stop_app.sh $A $FP; }
kill $RPID
for v in a3-dev stable-dev alpha2-dev a3-prod; do echo "--- guide-$v server-log warnings:"; logscan $W/logs/guide-$v.server.log; done
echo "### guide done $(date +%T)"
