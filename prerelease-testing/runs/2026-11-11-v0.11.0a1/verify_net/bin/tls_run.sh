#!/usr/bin/env bash
# Same-origin single-port prod behind a TLS terminator (no X-Forwarded-*): tls_run.sh <venv> <label> <P_app> <P_tls> [backend ENV=VAL...]
set -u
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad; W=$SB/apps/verify_net
venv=$1 label=$2 P=$3 T=$4; shift 4
$W/bin/single.sh start $venv $label $P REFLEX_API_URL=https://vnet.test:$T "$@"
setsid $SB/envs/driver/bin/python $W/bin/tls_term.py $T $P $W/tls/cert.pem $W/tls/key.pem > $W/logs/${label}_tls.log 2>&1 & echo $! > $W/logs/${label}_tls.pid; sleep 2
(cd $SB && NO_PROXY=localhost,127.0.0.1,vnet.test no_proxy=localhost,127.0.0.1,vnet.test timeout 120 $SB/envs/driver/bin/python $W/bin/drv.py https://vnet.test:$T/ $W/res/$label.json $W/res/$label.png)
kill -- -$(cat $W/logs/${label}_tls.pid) 2>/dev/null; $W/bin/single.sh stop $label
grep -h -i "accepted origin" $W/logs/$label.log | head -2 | sed 's/^/  server log: /'
