#!/usr/bin/env bash
# reflex-google-auth demo dev on <venv> (bogus-token clearing, /protected not unlocked); 3463/8463.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; TW=$SB/apps/a5_upgrade_ent/tp
V=${1:-a4_upgrade_ent-tp}; L=${2:-a4}; R=$TW/run/$L/ga_dev
D="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 600 $SB/envs/driver/bin/python"
rm -rf $R; mkdir -p $TW/run/$L $TW/out/google_auth; cp -r $TW/apps/google_auth_demo $R
GOOGLE_CLIENT_ID=123456789012-dummyclientid.apps.googleusercontent.com $TW/bin/start_app.sh $V $R 3463 8463 $TW/logs/ga-$L-dev.log --loglevel debug
$TW/bin/wait_up.sh http://localhost:3463/ 420 $TW/pids/ga_dev-$V.pid
for i in $(seq 1 120); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:8463/ping | grep -q 200 && break; sleep 1; done
(cd $TW/drivers && $D drive_google_auth.py http://localhost:3463 $TW/out/google_auth $L-dev > $TW/out/google_auth/$L-dev-stdout.txt 2>&1); tail -n 3 $TW/out/google_auth/$L-dev-stdout.txt | cut -c1-220
$TW/bin/stop_app.sh $TW/pids/ga_dev-$V.pid
A3=/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_events_tp/tp/out/google_auth
$SB/envs/driver/bin/python -I $TW/bin/cmp_checks.py $A3/a3-dev-report.json $TW/out/google_auth/$L-dev-report.json
$SB/envs/driver/bin/python -I $TW/bin/compare_console.py $A3/a3-dev-report.json $TW/out/google_auth/$L-dev-report.json | head -8
echo "ga-$L-dev.log: tracebacks=$(grep -c Traceback $TW/logs/ga-$L-dev.log) TypeError=$(grep -c TypeError $TW/logs/ga-$L-dev.log)"
