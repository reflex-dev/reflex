#!/bin/bash
# usage: run.sh <venv> <label>
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa; W=$SB/apps/verify_en1; V=$1; L=$2
rm -rf $W/run-$V; cp -r $W/gridmin $W/run-$V; cd $W/run-$V
CI=true REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=$V setsid $SB/envs/$V/bin/reflex run --frontend-port 3611 --backend-port 8611 > $W/server-$L.log 2>&1 &
SP=$!
for i in $(seq 1 120); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:3611/ | grep -q 200 && break; sleep 3; done
cd $W; NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_min.py http://localhost:3611/ $L $W/out-$L.json
kill -- -$SP 2>/dev/null; sleep 3; kill -9 -- -$SP 2>/dev/null
echo "tracebacks=$(grep -c Traceback $W/server-$L.log)"
