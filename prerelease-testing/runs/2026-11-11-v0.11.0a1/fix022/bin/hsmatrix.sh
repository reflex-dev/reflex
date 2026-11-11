#!/usr/bin/env bash
# hsmatrix.sh <app_port> <public_host[:port]> : raw handshakes with the headers each front door delivers upstream
P=$1 PUB=$2; H=$SB/bin/hs.sh; SB=/tmp/claude-0/-home-user/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/fix022; H=$SB/bin/hs.sh
row(){ n=$1; shift; printf '%-22s ' "$n"; $H $P "$@"; }
row local-localhost localhost:$P http://localhost:$P
row local-127 127.0.0.1:$P http://127.0.0.1:$P
row local-cross-127 localhost:$P http://127.0.0.1:$P
row passthrough $PUB https://$PUB
row nginx-default 127.0.0.1:$P https://$PUB
row nginx-host-xfp $PUB https://$PUB "X-Forwarded-Proto: https"
row xfp-xfh $PUB https://$PUB "X-Forwarded-Proto: https" "X-Forwarded-Host: $PUB"
row render-wss $PUB https://$PUB "X-Forwarded-Proto: wss"
row caddy-behind-edge $PUB https://$PUB "X-Forwarded-Proto: http" "X-Forwarded-Host: $PUB"
row appgw-override backend.azurewebsites.test https://$PUB "X-Forwarded-Proto: https" "X-Original-Host: $PUB"
row afd origin.azurewebsites.test https://$PUB "X-Forwarded-Proto: https" "X-Forwarded-Host: $PUB"
row split-or-cdn api.test https://$PUB "X-Forwarded-Proto: https"
row same-host-other-port ${PUB%%:*}:8000 https://$PUB
row http-plain-proxy $PUB http://$PUB
row atk-cross-site $PUB https://evil.example "X-Forwarded-Proto: https"
row atk-http-downgrade $PUB http://$PUB "X-Forwarded-Proto: https"
row atk-null $PUB null
row no-origin $PUB -
row atk-xfh-nonbrowser $PUB https://evil.example "X-Forwarded-Proto: https" "X-Forwarded-Host: evil.example"
