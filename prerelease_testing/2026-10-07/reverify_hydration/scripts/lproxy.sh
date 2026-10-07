#!/bin/bash
# lproxy.sh start LISTEN TARGET ONE_WAY_DELAY_MS | stop LISTEN  (latency_proxy.py: fixed delay each direction)
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/reverify_hydration
case $1 in
  start) nohup $SB/envs/driver/bin/python $W/drivers/latency_proxy.py $2 $3 $4 > $W/logs/lproxy-$2.out 2>&1 < /dev/null & echo $! > $W/run/lproxy-$2.pidfile; sleep 0.5; echo "lproxy $2->$3 ${4}ms pid=$(cat $W/run/lproxy-$2.pidfile)";;
  stop) kill $(cat $W/run/lproxy-$2.pidfile) 2>/dev/null; rm -f $W/run/lproxy-$2.pidfile; echo "lproxy $2 stopped";;
esac
