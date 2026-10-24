#!/bin/bash
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa; W=$SB/apps/verify_ct; V=$1
rm -rf $W/run-$V; cp -r $W/ctform $W/run-$V; cd $W/run-$V
REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=$V setsid $SB/envs/$V/bin/reflex run --frontend-port 3720 --backend-port 8720 > $W/server-$V.log 2>&1 &
SP=$!
for i in $(seq 1 120); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:3720/ | grep -q 200 && break; sleep 3; done
cd $W; NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive.py http://localhost:3720/ $W/out-$V.json
kill -- -$SP 2>/dev/null; sleep 3; kill -9 -- -$SP 2>/dev/null; rm -rf $W/run-$V
grep -iE 'Traceback|deprecat' $W/server-$V.log | head -5
