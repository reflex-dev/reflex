#!/bin/bash
# usage: run.sh <venv> <dev|prod> <label> [chart]
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa; W=$SB/apps/verify_ent910; V=$1; M=$2; L=$3; C=${4:-0}
rm -rf $W/run-$L; cp -r $W/gridfix $W/run-$L; cd $W/run-$L
if [ "$M" = prod ]; then FP=3611; BP=3611; EXTRA="--env prod"; export REFLEX_API_URL=http://localhost:3611; else FP=3611; BP=8611; EXTRA=""; fi
CI=true REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=$V GF_CHART=$C setsid $SB/envs/$V/bin/reflex run $EXTRA --frontend-port $FP --backend-port $BP > $W/server-$L.log 2>&1 &
SP=$!
for i in $(seq 1 150); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:3611/ | grep -q 200 && break; sleep 3; done
cd $W; NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive.py http://localhost:3611/ $W/out-$L.json
kill -- -$SP 2>/dev/null; sleep 4; kill -9 -- -$SP 2>/dev/null; rm -rf $W/run-$L
echo "server tracebacks=$(grep -c Traceback $W/server-$L.log)"
