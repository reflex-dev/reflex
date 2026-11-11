#!/usr/bin/env bash
# split_prod.sh <key> <appdir> <venv> : prod frontend-only on 3420 + backend-only on 8420 (REFLEX_API_URL=http://localhost:8420,
# deploy_url unset) = split-origin prod (#7641). Drives the upload app, probes CORS on /_event polling + /_upload preflight.
set -u; . "$(dirname "$0")/../env_eu.sh"; . "$W/up/bin/common.sh"
k=$1; A=$2; V=$3; L=$W/logs/upload; export QA_UPLOAD_EXTRAS=1
cd "$A" || exit 2
for p in 3420 8420; do port_busy $p && { echo "PORT $p BUSY"; exit 2; }; done
QA_EXPECT_VENV=$(basename "$V") REFLEX_API_URL=http://localhost:8420 setsid "$V/bin/reflex" run --env prod --backend-only --backend-port 8420 --loglevel debug > "$L/split-$k-be.server.log" 2>&1 < /dev/null & BE=$!
QA_EXPECT_VENV=$(basename "$V") REFLEX_API_URL=http://localhost:8420 setsid "$V/bin/reflex" run --env prod --frontend-only --frontend-port 3420 --loglevel debug > "$L/split-$k-fe.server.log" 2>&1 < /dev/null & FE=$!
for i in $(seq 1 120); do [ "$(http_code http://localhost:3420/)" = 200 ] && [ "$(http_code http://localhost:8420/ping)" = 200 ] && break; sleep 3; done
echo "fe=$(http_code http://localhost:3420/) be=$(http_code http://localhost:8420/ping) after ${i}x3s"
echo "-- GET /_event polling with Origin http://localhost:3420:"; curl -s --noproxy '*' -o /dev/null -D - -H 'Origin: http://localhost:3420' "http://localhost:8420/_event/?EIO=4&transport=polling" | grep -iE '^HTTP|access-control' | tr -d '\r'
echo "-- OPTIONS /_upload preflight:"; curl -s --noproxy '*' -o /dev/null -D - -X OPTIONS -H 'Origin: http://localhost:3420' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: reflex-client-token,reflex-event-handler' "http://localhost:8420/_upload" | grep -iE '^HTTP|access-control' | tr -d '\r'
$DRV "$W/up/scripts/drive_upload.py" http://localhost:3420/ "$W/shots/upload" "upload-split-$k" "$A/uploaded_files" "$W/run/upload-fixtures" > "$L/split-$k.drive.txt" 2>&1
grep -E '^\[(FAIL|ANOMALY)|^== |UNEXPECTED|PAGE ERR|BAD REQ' "$L/split-$k.drive.txt" | cut -c1-400 | head -14
for pid in $FE $BE; do kill -TERM -- -$pid 2>/dev/null; done; sleep 4; for pid in $FE $BE; do kill -KILL -- -$pid 2>/dev/null; done
sleep 1; for p in 3420 8420; do port_busy $p && { echo "STILL LISTENING $p"; lsof -nP -iTCP:$p -sTCP:LISTEN -t | xargs -r kill -9; }; done; echo stopped
