#!/bin/bash
# warn.sh <venv> <label> <P> <T> <profile> [ENV=VAL...]: single-port prod on P, one hproxy <profile> (TLS) on T, Chromium first,
# then print the server's rejection lines (the first rejection of the worker is this profile's).
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/net/bin/lib.sh
v=$1 label=$2 P=$3 T=$4 prof=$5; shift 5
chkport $P && chkport $T || exit 3
app=$(mkapp fapp $v $label); log=$W/logs/$label.log
start $label $v $app $log REFLEX_API_URL=https://app.test:$T "$@" -- --env prod --frontend-port $P --backend-port $P >/dev/null
wait_up http://localhost:$P/ping 400 >/dev/null || { echo "NOT UP"; tail -20 $log; stop $label; exit 1; }
echo "##### $label venv=$v profile=$prof env: $*"
setsid $PW $W/bin/hproxy.py $T $P $prof $W/tls/cert.pem $W/tls/key.pem > $W/logs/${label}_px.log 2>&1 & pp=$!; sleep 1.2
browse ${label}_$prof https://app.test:$T/
kill $pp 2>/dev/null; stop $label >/dev/null
awk '/Rejected an event websocket|not an accepted origin/{p=1} p{print "    "$0} /once per worker|further occurrences/{p=0}' $log | cut -c1-300
