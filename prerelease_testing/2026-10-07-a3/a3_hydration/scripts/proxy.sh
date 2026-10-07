#!/bin/bash
# Usage: proxy.sh start LISTEN TARGET DELAY_MS LOGNAME | proxy.sh stop LISTEN
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
V=$SB/apps/a3_hydration
PIDF=$V/run/proxy-$2.pidfile
case $1 in
  start)
    nohup $SB/envs/driver/bin/python $V/drivers/upgrade_delay_proxy.py $2 $3 $4 $PIDF > $V/logs/$5.log 2>&1 < /dev/null &
    for i in $(seq 1 20); do [ -s $PIDF ] && break; sleep 0.1; done; sleep 0.3
    echo "proxy $2->$3 delay $4 pid=$(cat $PIDF)";;
  stop)
    [ -s $PIDF ] && kill $(cat $PIDF) 2>/dev/null; rm -f $PIDF; sleep 0.3; echo "proxy $2 stopped";;
esac
