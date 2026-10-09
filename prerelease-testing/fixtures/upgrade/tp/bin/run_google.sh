#!/usr/bin/env bash
# reflex-google-auth demo dev on <venv> (bogus-token clearing, /protected not unlocked); 3463/8463. Expected 12/13
# (the driver's "key discoverable" check), 0 differing vs tp/expected/google_auth-dev.json (a5 pass).
# Usage: run_google.sh [venv] [label]   (default $VENV_PREFIX-tp new)
set -u; . "$(dirname "$0")/../../bin/env.sh"; TW=$(cd "$(dirname "$0")/.." && pwd)
V=${1:-$VENV_PREFIX-tp}; L=${2:-new}; R=$TW/run/$L/ga_dev
D="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 600 $DPY"
rm -rf $R; mkdir -p $TW/run/$L $TW/out/google_auth $TW/logs; cp -r $TW/apps/google_auth_demo $R
GOOGLE_CLIENT_ID=123456789012-dummyclientid.apps.googleusercontent.com $TW/bin/start_app.sh $V $R 3463 8463 $TW/logs/ga-$L-dev.log --loglevel debug
$TW/bin/wait_up.sh http://localhost:3463/ 420 $TW/pids/ga_dev-$V.pid
for i in $(seq 1 120); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:8463/ping | grep -q 200 && break; sleep 1; done
(cd $TW/drivers && $D drive_google_auth.py http://localhost:3463 $TW/out/google_auth $L-dev > $TW/out/google_auth/$L-dev-stdout.txt 2>&1); tail -n 3 $TW/out/google_auth/$L-dev-stdout.txt | cut -c1-220
$TW/bin/stop_app.sh $TW/pids/ga_dev-$V.pid
CMP=${CMP_DIR:-$TW/expected}
$DPY -I $TW/bin/cmp_checks.py $CMP/google_auth-dev.json $TW/out/google_auth/$L-dev-report.json
$DPY -I $TW/bin/compare_console.py $CMP/google_auth-dev.json $TW/out/google_auth/$L-dev-report.json | head -8
echo "ga-$L-dev.log: tracebacks=$(grep -c Traceback $TW/logs/ga-$L-dev.log) TypeError=$(grep -c TypeError $TW/logs/ga-$L-dev.log)"
