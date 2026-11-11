#!/usr/bin/env bash
# raw websocket upgrade to /_event with a given Host/Origin/X-Forwarded-Proto: ws_origin.sh <port> <host> <origin> [xfp]
P=$1 H=$2 O=$3 X=${4:-}
args=(-H "Host: $H" -H "Origin: $O" -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==")
[ -n "$X" ] && args+=(-H "X-Forwarded-Proto: $X")
code=$(curl --noproxy '*' -s -o /dev/null -m 3 -w '%{http_code}' "${args[@]}" "http://localhost:$P/_event/?EIO=4&transport=websocket")
echo "Host=$H Origin=$O XFP=${X:--} -> $code"
