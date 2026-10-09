#!/bin/bash
# Usage: proxy.sh start LISTEN TARGET DELAY_MS LOGNAME | proxy.sh stop LISTEN
# drivers/upgrade_delay_proxy.py: delays the websocket UPGRADE by DELAY_MS (F-010 redirect-hijack window, f6_natural.py).
. "$(dirname "$0")/env.sh"
PIDF=$W/run/proxy-$2.pidfile
case $1 in
  start)
    nohup "$DRV" "$F/drivers/upgrade_delay_proxy.py" "$2" "$3" "$4" "$PIDF" > "$W/logs/$5.log" 2>&1 < /dev/null &
    for _ in $(seq 1 20); do [ -s "$PIDF" ] && break; sleep 0.1; done; sleep 0.3
    echo "proxy $2->$3 delay $4 pid=$(cat "$PIDF")";;
  stop)
    [ -s "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null; rm -f "$PIDF"; sleep 0.3; echo "proxy $2 stopped";;
esac
