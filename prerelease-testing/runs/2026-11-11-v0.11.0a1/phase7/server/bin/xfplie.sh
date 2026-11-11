#!/bin/bash
# xfplie.sh <venv> <hops>: page over PLAIN http through a proxy on 3341 (keeps Host); profile xfp-https claims XFP https (lie),
# nginx-host sends no XFP. With hops>=1 the trusted XFP https must reject the http:// origin; without XFP it must connect.
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/net/bin/lib.sh
v=$1 h=$2 P=3340 T=3341; chkport $P && chkport $T || exit 3
label=${v}_xfplie_h$h; app=$(mkapp fapp $v $label)
start $label $v $app $W/logs/$label.log REFLEX_API_URL=http://app.test:$T REFLEX_TRUSTED_PROXY_HOPS=$h -- --env prod --frontend-port $P --backend-port $P >/dev/null
wait_up http://localhost:$P/ping 400 >/dev/null
for prof in nginx-host xfp-https; do
  $PW $W/bin/hproxy.py $T $P $prof > $W/logs/${label}_$prof.px.log 2>&1 & pp=$!; sleep 1.2
  echo "hops=$h plain-http proxy profile=$prof (proxy pid $pp: $(head -1 $W/logs/${label}_$prof.px.log))"; browse ${label}_$prof http://app.test:$T/ | grep -v 'status of 404' | head -2
  kill $pp; wait $pp 2>/dev/null
done
stop $label >/dev/null; grep -A3 'Rejected' $W/logs/$label.log | tr '\n' ' ' | cut -c1-300; echo
