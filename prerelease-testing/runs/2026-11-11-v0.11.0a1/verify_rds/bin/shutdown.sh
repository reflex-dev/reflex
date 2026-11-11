#!/bin/bash
# Shutdown with events in flight. Usage: shutdown.sh <out.txt> "<venvs>" "<INT-group TERM-pid ...>" [prod|dev]
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_rds/bin/lib.sh
OUT=$1; VENVS=$2; SIGS=$3; MODE=${4:-prod}; RP=8237; D=$SB/envs/vrds-drv/bin/python
redis-cli -p $RP ping >/dev/null 2>&1 || redis_up $RP
for v in $VENVS; do app=$W/run/lock-$v; [ -d $app ] || cp -r $W/src/lockapp $app
 for s in $SIGS; do sig=${s%-*}; how=${s#*-}; tag=sd-$v-$MODE-$s-$(date +%H%M%S); log=$W/logs/$tag.log
  if [ $MODE = prod ]; then P=3221; B=3221; args="--env prod"; else P=3222; B=8222; args=""; fi
  REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$B GRANIAN_WORKERS=2 start_app sd $v $app $P $B $log $args >/dev/null
  wait_up http://localhost:$P/ 400 >/dev/null; [ $MODE = dev ] && wait_up http://localhost:$B/ping 100 >/dev/null; sleep 3
  ( $D $W/bin/load.py http://localhost:$B --clients 4 --events 300 --mode pipe --event incr_async --bg 2000 --api 100 --api-conc 4 --timeout 20 --label $tag > $W/logs/$tag.load 2>&1 & )
  ( for i in 1 2 3; do $D $W/bin/faults.py http://localhost:$B $RP lost_none > /dev/null 2>&1 & done )
  sleep 1.5
  pid=$(cat $W/pids/sd.pid); t0=$(date +%s.%N)
  if [ $how = group ]; then kill -$sig -- -$pid; else kill -$sig $pid; fi
  res="HUNG"; for i in $(seq 1 120); do kill -0 -- -$pid 2>/dev/null || { res="exited"; break; }; sleep 0.25; done
  dt=$(echo "$(date +%s.%N) - $t0" | bc)
  [ $res = HUNG ] && { left=$(ps -o pid,args -g $pid | tail -n +2 | cut -c1-80 | tr '\n' ';'); kill -9 -- -$pid; }
  py=$($SB/envs/$v/bin/python -c 'import sys,redis;print(sys.version.split()[0],"redis",redis.__version__)')
  echo "$tag [$py]: $res in ${dt}s ${left:-} | tail: $(grep -v -E '^\s*$' $log | tail -3 | cut -c1-120 | tr '\n' '|') | errs: $(grep -c -i -E 'traceback|error' $log)" >> $OUT
  rm -f $W/pids/sd.pid; sleep 2
 done
done
