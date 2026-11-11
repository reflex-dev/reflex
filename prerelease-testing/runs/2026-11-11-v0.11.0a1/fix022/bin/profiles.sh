#!/usr/bin/env bash
# profiles.sh <tag> <app_port> <tls_port> <profile...>: TLS front door per profile on tls_port, Chromium to https://app.test:<tls_port>/
SB=/tmp/claude-0/-home-user/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/fix022
D=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/envs/driver/bin/python
tag=$1 P=$2 T=$3; shift 3
for prof in "$@"; do
  setsid $D $SB/bin/hproxy.py $T $P $prof $SB/tls/cert.pem $SB/tls/key.pem > $SB/logs/px_${tag}_$prof.log 2>&1 & pid=$!; sleep 1.5
  $SB/bin/browse.sh ${tag}_$prof https://app.test:$T/
  kill -- -$pid 2>/dev/null; kill $pid 2>/dev/null; sleep 0.5
done
