#!/bin/bash
# verify_upgrade A3-07: stop `reflex run [--json]` through a real supervisord 4.3.0 with several stop configs.
# Usage: vu_supervisord.sh <venv: a3|alpha2|stable> <appdir> <outdir>
# supervisorctl talks to 127.0.0.1:8659 (verify_upgrade range); the app uses 3640/8640.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
V=$1; APP=$2; OUT=$3; mkdir -p $OUT
"$SB/envs/$V/bin/python" -I -c "import reflex,sys; assert '/scratchpad/envs/$V/' in reflex.__file__, reflex.__file__; print('reflex from', reflex.__file__)"
CONF=$OUT/supervisord.conf
prog(){ # name stopsignal stopasgroup killasgroup json
cat <<P
[program:$1]
command=$SB/envs/$V/bin/reflex run $5 --frontend-port 3640 --backend-port 8640
directory=$APP
environment=REFLEX_TELEMETRY_ENABLED="false"
autostart=false
autorestart=false
startsecs=1
stopsignal=$2
stopasgroup=$3
killasgroup=$4
stopwaitsecs=10
stdout_logfile=$OUT/$1.out.log
stderr_logfile=$OUT/$1.err.log
P
}
{
cat <<C
[supervisord]
nodaemon=true
user=root
logfile=$OUT/supervisord.log
pidfile=$OUT/supervisord.pid
childlogdir=$OUT
[inet_http_server]
port=127.0.0.1:8659
[supervisorctl]
serverurl=http://127.0.0.1:8659
[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface
C
prog json_INT_pidonly INT false false --json
prog json_INT_group INT true true --json
prog json_TERM_default TERM false false --json
prog plain_INT_pidonly INT false false ""
} > $CONF
# processes whose cwd is the app dir (reflex, backend worker, bun, node) -- never matches this shell
app_pids(){ for d in /proc/[0-9]*; do c=$(readlink $d/cwd 2>/dev/null) || continue; case "$c" in "$APP"|"$APP"/*) echo ${d#/proc/};; esac; done; }
env NO_PROXY= no_proxy= $SB/envs/verify_upgrade-sup/bin/supervisord -c $CONF & SUPPID=$!
sleep 2
CTL="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/verify_upgrade-sup/bin/supervisorctl -c $CONF"
for P in json_INT_pidonly json_INT_group json_TERM_default plain_INT_pidonly; do
  echo "== $P"
  $CTL start $P
  for i in $(seq 1 120); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://127.0.0.1:8640/ping 2>/dev/null | grep -q 200 && break; sleep 0.5; done
  echo "  ready after ~$((i/2)) s; app pids: $(app_pids | tr '\n' ' ')"
  T0=$(date +%s.%N)
  $CTL stop $P
  T1=$(date +%s.%N)
  echo "  supervisorctl stop took $(echo "$T1 - $T0" | bc) s"
  sleep 3
  echo "  ping after stop+3s: $(curl -s --noproxy '*' -m 2 http://127.0.0.1:8640/ping || echo DOWN)"
  echo "  frontend after stop+3s: $(curl -s --noproxy '*' -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:3640/ || echo DOWN)"
  for p in $(app_pids); do echo "  LEFTOVER $p ppid=$(awk '{print $4}' /proc/$p/stat) $(tr '\0' ' ' < /proc/$p/cmdline | sed "s#$SB#\$SB#g" | cut -c1-110)"; done
  echo "  listening: $(lsof -nP -iTCP:3640 -iTCP:8640 -sTCP:LISTEN -t 2>/dev/null | tr '\n' ' ')"
  grep -E "$P" $OUT/supervisord.log | tail -4 | sed 's/^/  sup.log: /'
  for p in $(app_pids); do kill -9 $p 2>/dev/null; done
  sleep 2
done
$CTL shutdown >/dev/null
wait $SUPPID
