#!/usr/bin/env bash
# raw websocket upgrade to /_event: hs.sh <port> <Host> <Origin> [Header: value ...]
P=$1 H=$2 O=$3; shift 3
args=(-H "Host: $H" -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==")
[ "$O" != "-" ] && args+=(-H "Origin: $O")
for h in "$@"; do args+=(-H "$h"); done
code=$(curl --noproxy '*' -s -o /dev/null -m 3 -w '%{http_code}' "${args[@]}" "http://127.0.0.1:$P/_event/?EIO=4&transport=websocket")
echo "$code  Host=$H Origin=$O $*"
