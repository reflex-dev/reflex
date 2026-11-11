#!/usr/bin/env bash
# CLI-16 probe: dev backend while the app is broken by a hot reload, after the fix, and after SIGTERM.
#   cli16.sh <venv>   (3357/8357)
set -u
SB=${SB:?}; W=${W:-$SB/apps/server_net}
venv=$1 label=c16_$1
APPF=$W/run/$venv/netapp/netapp/netapp.py
$W/bin/srv.sh start $label $venv netapp --frontend-port 3357 --backend-port 8357 >/dev/null
LABEL=$label $W/bin/srv.sh wait http://localhost:3357/ 300 >/dev/null; $W/bin/srv.sh wait http://localhost:8357/ping 60 >/dev/null; sleep 3
probe() { # probe <tag> <seconds>
  local out=""
  for i in $(seq 1 $2); do
    r=$(curl --noproxy '*' -s -o /dev/null -m 3 -w '%{http_code}/%{time_total}' localhost:8357/ping 2>/dev/null); [ -z "$r" ] && r="ERR"
    out="$out ${r%%.*}${r#*.}"; out="$out"
    sleep 1
  done
  echo "  $1:$(echo $out | tr ' ' '\n' | awk -F/ '{printf " %s/%.2fs", $1, $2}')"
}
probe healthy 3
cp $APPF $APPF.bak
echo "def broken(:" >> $APPF
echo "  [broke app at $(date +%T)]"
probe broken 15
cp $APPF.bak $APPF; rm $APPF.bak
echo "  [fixed app at $(date +%T)]"
probe fixed 15
pid=$(cat $W/logs/$label.pid); t0=$(date +%s.%N); kill -TERM $pid
for i in $(seq 1 80); do curl --noproxy '*' -s -m 1 -o /dev/null localhost:8357/ping || break; sleep 0.1; done
echo "  after SIGTERM: /ping refused after $(echo "$(date +%s.%N) - $t0" | bc)s"
$W/bin/srv.sh stop $label >/dev/null
grep -c -i "SyntaxError" $W/logs/$label.log | sed 's/^/  SyntaxError lines in log: /'
