#!/bin/bash
# verify_upgrade A3-07 follow-up: supervisord stopsignal=INT (stopasgroup/killasgroup default false) + `reflex run --json`:
# stop -> wait 30 s -> survivors? -> start again -> does the new instance come up on its ports?
# Usage: vu_supervisord_restart.sh <venv> <appdir> <outdir>
set -u
. "$(dirname "$0")/../../bin/env.sh"; L=$(cd "$(dirname "$0")/.." && pwd); FP=${FP:-3510}; BP=${BP:-8510}; SUPP=${SUPP:-8519}
V=$1; APP=$2; OUT=$3; mkdir -p $OUT
"$SB/envs/$V/bin/python" -I -c "import reflex,sys; assert '/envs/$V/' in reflex.__file__, reflex.__file__"
CONF=$OUT/supervisord.conf
cat > $CONF <<C
[supervisord]
nodaemon=true
user=root
logfile=$OUT/supervisord.log
pidfile=$OUT/supervisord.pid
childlogdir=$OUT
[inet_http_server]
port=127.0.0.1:$SUPP
[supervisorctl]
serverurl=http://127.0.0.1:$SUPP
[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface
[program:rx]
command=$SB/envs/$V/bin/reflex run --json --frontend-port $FP --backend-port $BP
directory=$APP
environment=REFLEX_TELEMETRY_ENABLED="false"
autostart=false
autorestart=false
startsecs=1
stopsignal=INT
stopwaitsecs=10
stdout_logfile=$OUT/rx.out.log
stderr_logfile=$OUT/rx.err.log
C
app_pids(){ for d in /proc/[0-9]*; do c=$(readlink $d/cwd 2>/dev/null) || continue; case "$c" in "$APP"|"$APP"/*) echo ${d#/proc/};; esac; done; }
env NO_PROXY= no_proxy= $SB/envs/${SUP_VENV:-$VENV_PREFIX-sup}/bin/supervisord -c $CONF & SUPPID=$!
sleep 2
CTL="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/${SUP_VENV:-$VENV_PREFIX-sup}/bin/supervisorctl -c $CONF"
$CTL start rx
for i in $(seq 1 120); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://127.0.0.1:$BP/ping | grep -q 200 && break; sleep 0.5; done
echo "first instance up; pids $(app_pids | tr '\n' ' ')"
$CTL stop rx
for t in 5 30; do sleep $([ $t = 5 ] && echo 5 || echo 25)
  echo "t=+${t}s after stop: ping=$(curl -s --noproxy '*' -m 2 http://127.0.0.1:$BP/ping || echo DOWN) frontend=$(curl -s --noproxy '*' -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:$FP/) survivors=$(app_pids | tr '\n' ' ')"
done
echo "restart:"; $CTL start rx; sleep 15; $CTL status rx
echo "rx.out.log tail after restart:"; tail -n 8 $OUT/rx.out.log | sed "s#$SB#\$SB#g" | cut -c1-260
echo "rx.err.log tail:"; tail -n 5 $OUT/rx.err.log | sed "s#$SB#\$SB#g" | cut -c1-260
$CTL stop rx >/dev/null 2>&1
for p in $(app_pids); do kill -9 $p 2>/dev/null; done
$CTL shutdown >/dev/null; wait $SUPPID
echo "final survivors: $(app_pids | tr '\n' ' ') listening: $(lsof -nP -iTCP:$FP -iTCP:$BP -iTCP:$SUPP -sTCP:LISTEN -t 2>/dev/null | tr '\n' ' ')"
