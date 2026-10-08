#!/usr/bin/env bash
# reflex-azure-auth flows on <venv> (a5_upgrade_ent-az | -az4) <label>, dev 3463/8463 (+ optional prod 8467), mock IdP 8638 via ent/auth/bin/infra.sh.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; T=$SB/apps/a5_upgrade_ent/tp/az; E=$SB/apps/a5_upgrade_ent/ent/auth
V=$1; L=$2; MODES=${3:-dev}
R=$T/run/$L; mkdir -p $T/run; [ -d $R ] || cp -r $T/src/azapp $R
$E/bin/infra.sh start > /dev/null
for m in ${MODES//,/ }; do
  cd $R
  if [ $m = dev ]; then FP=3463; BP=8463; ARGS=(); else FP=8467; BP=8467; ARGS=(--env prod); fi
  CI=true REFLEX_TELEMETRY_ENABLED=false QA_EXPECT_VENV=$V AZURE_ISSUER_URI=http://localhost:8638 AZURE_CLIENT_ID=az-client AZURE_CLIENT_SECRET=az-secret \
    REFLEX_API_URL=$([ $m = dev ] && echo http://localhost:$BP || echo http://localhost:$FP) AUTHLIB_INSECURE_TRANSPORT=1 \
    setsid $SB/envs/$V/bin/reflex run --frontend-port $FP --backend-port $BP --loglevel debug "${ARGS[@]}" > $T/logs/az-$L-$m.server.log 2>&1 < /dev/null &
  PID=$!; start=$(date +%s)
  until [ "$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$FP/)" = 200 ] && [ "$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$BP/ping)" = 200 ]; do
    kill -0 $PID 2>/dev/null || { echo "server died"; tail -20 $T/logs/az-$L-$m.server.log; break; }; [ $(( $(date +%s) - start )) -gt 420 ] && { echo TIMEOUT; break; }; sleep 3; done
  (cd $T/drivers && env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 300 $SB/envs/driver/bin/python drive_az.py http://localhost:$FP $L-$m 2>&1 | tail -3 | cut -c1-500)
  kill -INT -- -$PID 2>/dev/null; for i in $(seq 1 20); do kill -0 $PID 2>/dev/null || break; sleep 0.5; done; kill -KILL -- -$PID 2>/dev/null
  for p in $FP $BP; do for lp in $(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null); do kill -KILL $lp; done; done
  echo "az-$L-$m server: tracebacks=$(grep -c Traceback $T/logs/az-$L-$m.server.log) verification_failed=$(grep -c 'verification failed' $T/logs/az-$L-$m.server.log)"
done
$E/bin/infra.sh stop > /dev/null
