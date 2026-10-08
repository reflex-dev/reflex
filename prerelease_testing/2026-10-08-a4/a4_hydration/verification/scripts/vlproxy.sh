#!/bin/bash
# vlproxy.sh start LISTEN TARGET ONE_WAY_DELAY_MS | stop LISTEN   (explorer's latency_proxy.py: fixed delay each direction)
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; V=$SB/apps/a4_hydration/v
case $1 in
  start) nohup $SB/envs/driver/bin/python $V/drivers/latency_proxy.py $2 $3 $4 > $V/logs/lproxy-$2.out 2>&1 < /dev/null & echo $! > $V/run/lproxy-$2.pidfile; sleep 0.5; echo "lproxy $2->$3 ${4}ms pid=$(cat $V/run/lproxy-$2.pidfile)";;
  stop) kill $(cat $V/run/lproxy-$2.pidfile) 2>/dev/null; rm -f $V/run/lproxy-$2.pidfile; echo "lproxy $2 stopped";;
esac
