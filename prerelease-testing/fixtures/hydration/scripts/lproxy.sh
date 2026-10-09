#!/bin/bash
# lproxy.sh start LISTEN TARGET ONE_WAY_DELAY_MS | stop LISTEN   (drivers/latency_proxy.py: fixed delay each direction;
# 50 = 100 ms RTT). Used by vmatrix.sh, the race.py RTT runs and ab_timing.py.
. "$(dirname "$0")/env.sh"
case $1 in
  start) nohup "$DRV" "$F/drivers/latency_proxy.py" "$2" "$3" "$4" > "$W/logs/lproxy-$2.out" 2>&1 < /dev/null &
         echo $! > "$W/run/lproxy-$2.pidfile"; sleep 0.5; echo "lproxy $2->$3 ${4}ms pid=$(cat "$W/run/lproxy-$2.pidfile")";;
  stop) kill "$(cat "$W/run/lproxy-$2.pidfile")" 2>/dev/null; rm -f "$W/run/lproxy-$2.pidfile"; echo "lproxy $2 stopped";;
esac
