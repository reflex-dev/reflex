#!/usr/bin/env bash
# Runs the #7553 / #7435 scenarios against schema_app: static v1 frontend on :3227, prod backend-only on :8227.
# Usage: schema_scenarios.sh   (after `schema_run.sh export v1 SCHEMA_EXTRA=0`)
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
W=$SB/apps/frontend_store
L=$W/logs
PW="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
R=$W/schema_run.sh
cd $W
summarize() { $SB/envs/driver/bin/python -c "
import json,sys; r=json.load(open('$1'))
fails=[c['name'] for c in r['checks'] if not c['ok']]
tl=[c for c in r['checks'] if c['name']=='timeline after restart']
print(f'  fails={len(fails)} {fails} mismatch={r[\"mismatch_warnings\"]} unknown={r[\"unknown_substate_warnings\"]} pageerrors={len(r[\"pageerrors\"])}')
if tl: print('  timeline:', [ {k:v for k,v in s.items() if k in ('t','loads','nav','banner','hydrated','free_input','mismatch','unknown')} for s in tl[0]['got']][-4:])
"; }

$R static v1
echo "### S1 identical build, backend in another process"
$R backend be_v1 SCHEMA_EXTRA=0
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S1.json --reloads 3 > $L/schema_S1.out 2>&1; summarize $L/schema_S1.json
grep -c "does not match" $L/be_v1.log | sed 's/^/  backend mismatch log lines: /'

echo "### S2 prod restart of the same backend with the page open"
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S2.json --reloads 1 --hold 20 \
  --restart-cmd "$R stop be_v1; $R backend be_v1b SCHEMA_EXTRA=0" > $L/schema_S2.out 2>&1; summarize $L/schema_S2.json
grep -c "does not match" $L/be_v1b.log | sed 's/^/  backend mismatch log lines: /'
$R stop be_v1b

echo "### S3 Redis + 3 granian workers (fork), then spawn start method"
redis-server --port 8229 --save '' --appendonly no --daemonize no > $L/redis.log 2>&1 &
echo $! > $L/redis.pid; sleep 1
$R backend be_redis SCHEMA_EXTRA=0 REFLEX_REDIS_URL=redis://localhost:8229 GRANIAN_WORKERS=3
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S3a.json --reloads 6 > $L/schema_S3a.out 2>&1; summarize $L/schema_S3a.json
grep -c "does not match" $L/be_redis.log | sed 's/^/  backend mismatch log lines: /'
grep -c "Started worker" $L/be_redis.log | sed 's/^/  workers started: /'
$R stop be_redis
$R backend be_spawn SCHEMA_EXTRA=0 REFLEX_REDIS_URL=redis://localhost:8229 GRANIAN_WORKERS=3 REFLEX_BACKEND_START_METHOD=spawn
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S3b.json --reloads 6 > $L/schema_S3b.out 2>&1; summarize $L/schema_S3b.json
grep -c "does not match" $L/be_spawn.log | sed 's/^/  backend mismatch log lines: /'
$R stop be_spawn
kill $(cat $L/redis.pid) 2>/dev/null; rm -f $L/redis.pid

echo "### S4a default-only change on the backend (hash must be equal)"
$R backend be_default SCHEMA_DEFAULT=1
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S4a.json --reloads 1 > $L/schema_S4a.out 2>&1; summarize $L/schema_S4a.json
grep -c "does not match" $L/be_default.log | sed 's/^/  backend mismatch log lines: /'
$R stop be_default

echo "### S4b renamed handler on the backend (mismatch: reload once, then banner), cooldown 6s"
$R backend be_rename SCHEMA_RENAME=1 REFLEX_AUTO_RELOAD_COOLDOWN=6s
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S4b.json --reloads 1 --hold 1 > $L/schema_S4b.out 2>&1; summarize $L/schema_S4b.json
grep -c "does not match" $L/be_rename.log | sed 's/^/  backend mismatch log lines: /'
$R stop be_rename

echo "### S5 extra substate deployed while the page is open (old frontend): reload once, banner, unknown substate skipped+reported once"
$R backend be_v1c SCHEMA_EXTRA=0
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S5.json --reloads 1 --hold 25 \
  --restart-cmd "$R stop be_v1c; $R backend be_extra SCHEMA_EXTRA=1 REFLEX_AUTO_RELOAD_COOLDOWN=8s" > $L/schema_S5.out 2>&1; summarize $L/schema_S5.json
grep -c "does not match" $L/be_extra.log | sed 's/^/  backend mismatch log lines: /'
grep -c "Skipped state update for unknown substate" $L/be_extra.log | sed 's/^/  backend unknown-substate reports: /'
$R stop be_extra
$R stop static
echo "### done"
