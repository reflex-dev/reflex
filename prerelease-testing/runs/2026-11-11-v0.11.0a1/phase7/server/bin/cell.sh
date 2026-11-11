#!/bin/bash
# cell.sh <venv> <label> <P> <T> [ENV=VAL...]: single-port prod on P (api_url https://app.test:T) and, on T, TLS front doors:
# browser via passthrough (tls_term, keeps Host, no XFF) / afd (Host rewritten + XFH) / xfp-xfh / caddy-behind-edge;
# cross-site attacker page in Chromium; raw handshake matrix. Logs: logs/<label>.log; results res/<label>_*.
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/net/bin/lib.sh
v=$1 label=$2 P=$3 T=$4; shift 4; E=$((T+1))
chkport $P && chkport $T && chkport $E || exit 3
app=$(mkapp fapp $v $label); log=$W/logs/$label.log
start $label $v $app $log REFLEX_API_URL=https://app.test:$T "$@" -- --env prod --frontend-port $P --backend-port $P >/dev/null
wait_up http://localhost:$P/ping 400 >/dev/null || { echo "NOT UP"; tail -20 $log; stop $label; exit 1; }
wait_up http://localhost:$P/ 60 >/dev/null
echo "##### $label venv=$v env: $*"
px() { setsid "$@" > $W/logs/${label}_px.log 2>&1 & echo $! > $W/pids/${label}_px.pid; sleep 1.2; }
pxstop() { kill -- -$(cat $W/pids/${label}_px.pid) 2>/dev/null; kill $(cat $W/pids/${label}_px.pid) 2>/dev/null; sleep 0.5; }
for prof in passthrough afd xfp-xfh caddy-behind-edge; do
  if [ $prof = passthrough ]; then px $PW $W/bin/tls_term.py $T $P $W/tls/cert.pem $W/tls/key.pem
  else px $PW $W/bin/hproxy.py $T $P $prof $W/tls/cert.pem $W/tls/key.pem; fi
  browse ${label}_$prof https://app.test:$T/
  [ $prof = passthrough ] && { echo "  [xsite]"; setsid $PW -m http.server -d $W/xsite $E -b 127.0.0.1 > /dev/null 2>&1 & hp=$!; sleep 1
    (cd $W && NO_PROXY=localhost,127.0.0.1,.test no_proxy=localhost,127.0.0.1,.test timeout 60 $PW $W/bin/xsite.py http://evil.test:$E/ $W/res/${label}_xsite.json wss://app.test:$T/_event/?EIO=4\&transport=websocket ws://localhost:$P/_event/?EIO=4\&transport=websocket | sed 's/^/    /')
    kill $hp 2>/dev/null; }
  pxstop
done
PUB=app.test:$T
{ row(){ n=$1; shift; printf '%-24s ' "$n"; hs $P "$@"; }
row local-localhost localhost:$P http://localhost:$P
row local-127 127.0.0.1:$P http://127.0.0.1:$P
row passthrough $PUB https://$PUB
row nginx-default 127.0.0.1:$P https://$PUB
row nginx-host-xfp $PUB https://$PUB "X-Forwarded-Proto: https"
row xfp-xfh $PUB https://$PUB "X-Forwarded-Proto: https" "X-Forwarded-Host: $PUB"
row render-wss $PUB https://$PUB "X-Forwarded-Proto: wss"
row caddy-behind-edge $PUB https://$PUB "X-Forwarded-Proto: http" "X-Forwarded-Host: $PUB"
row afd origin.azurewebsites.test https://$PUB "X-Forwarded-Proto: https" "X-Forwarded-Host: $PUB"
row afd-noxfp origin.azurewebsites.test https://$PUB "X-Forwarded-Host: $PUB"
row afd-xfh-chain2 origin.azurewebsites.test https://$PUB "X-Forwarded-Proto: https" "X-Forwarded-Host: edge.test, $PUB"
row split-or-cdn api.test https://$PUB "X-Forwarded-Proto: https"
row http-plain-proxy $PUB http://$PUB
row atk-cross-site $PUB https://evil.example "X-Forwarded-Proto: https"
row atk-cross-site-noxf $PUB https://evil.example
row atk-http-downgrade $PUB http://$PUB "X-Forwarded-Proto: https"
row atk-http-downgrade-wss $PUB http://$PUB "X-Forwarded-Proto: wss"
row atk-http-dg-chain2 $PUB http://$PUB "X-Forwarded-Proto: https, http"
row atk-null $PUB null
row no-origin $PUB -
row atk-xfh-forged $PUB https://evil.example "X-Forwarded-Proto: https" "X-Forwarded-Host: evil.example"
row atk-xfh-chain-evil origin.azurewebsites.test https://evil.example "X-Forwarded-Proto: https" "X-Forwarded-Host: evil.example, $PUB"
row atk-userinfo $PUB https://x@$PUB
row atk-suffix $PUB https://$PUB.evil.example
} > $W/res/${label}_hs.txt
cat $W/res/${label}_hs.txt | sed 's/^/  hs /'
stop $label >/dev/null
echo "  log: rejections:"; grep -n -i 'Rejected an event websocket\|not an accepted origin' $log | cut -c1-900 | sed 's/^/    /'
echo "  log: warning/error count: $(grep -c -i 'warn\|error\|traceback' $log)"
