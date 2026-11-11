#!/bin/bash
# split.sh <venv> <label> <FP> <BP> [backend ENV=VAL...]: docs/hosting/self-hosting.md @ v0.11.0a2 split recipe, literally:
#   REFLEX_DEPLOY_URL=http://localhost:FP reflex run --env prod --backend-only --backend-port BP   (pass REFLEX_DEPLOY_URL=... as arg)
#   REFLEX_API_URL=http://localhost:BP reflex run --env prod --frontend-only --frontend-port FP
# then Chromium on the frontend, a cross-site page, and raw handshakes to the backend.
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/net/bin/lib.sh
v=$1 label=$2 FP=$3 BP=$4; shift 4; E=$((FP+1))
chkport $FP && chkport $BP && chkport $E || exit 3
app=$(mkapp fapp $v $label)
start ${label}_be $v $app $W/logs/${label}_be.log "$@" -- --env prod --backend-only --backend-port $BP >/dev/null
wait_up http://localhost:$BP/ping 300 >/dev/null || { echo BE NOT UP; tail $W/logs/${label}_be.log; stop ${label}_be; exit 1; }
start ${label}_fe $v $app $W/logs/${label}_fe.log REFLEX_API_URL=http://localhost:$BP -- --env prod --frontend-only --frontend-port $FP >/dev/null
wait_up http://localhost:$FP/ 400 >/dev/null || { echo FE NOT UP; tail $W/logs/${label}_fe.log; }
echo "##### $label venv=$v backend env: $*"
browse $label http://localhost:$FP/
setsid $PW -m http.server -d $W/xsite $E -b 127.0.0.1 > /dev/null 2>&1 & hp=$!; sleep 1
(cd $W && NO_PROXY=localhost,127.0.0.1,.test no_proxy=localhost,127.0.0.1,.test timeout 60 $PW $W/bin/xsite.py http://evil.test:$E/ $W/res/${label}_xsite.json ws://localhost:$BP/_event/?EIO=4\&transport=websocket | sed 's/^/  [xsite] /')
kill $hp 2>/dev/null
{ hs $BP localhost:$BP http://localhost:$FP; hs $BP localhost:$BP http://localhost:$BP; hs $BP localhost:$BP http://127.0.0.1:$FP; hs $BP localhost:$BP https://evil.example; } | sed 's/^/  hs /'
stop ${label}_fe >/dev/null; stop ${label}_be >/dev/null
awk '/Rejected an event websocket|not an accepted origin/{p=1} p{print "  backend log: "$0} /once per worker|further occurrences/{p=0}' $W/logs/${label}_be.log | cut -c1-300
