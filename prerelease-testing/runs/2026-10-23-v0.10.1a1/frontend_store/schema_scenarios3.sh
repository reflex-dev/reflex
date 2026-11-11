#!/usr/bin/env bash
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
W=$SB/apps/frontend_store; L=$W/logs; R=$W/schema_run.sh
PW="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
cd $W
summarize() { $SB/envs/driver/bin/python -c "
import json; r=json.load(open('$1'))
for c in r['checks']:
    if c['name']=='timeline after restart':
        for s in c['got']: print('    ', {k:v for k,v in s.items() if k in ('t','loads','nav','banner','hydrated','free_input','mismatch','unknown','err')})
    else: print('  ', 'ok ' if c['ok'] else 'FAIL', c['name'], '| got', repr(c['got'])[:60], '| want', repr(c['want'])[:40])
print(f'  => fails={sum(1 for c in r[\"checks\"] if not c[\"ok\"])} mismatch={r[\"mismatch_warnings\"]} unknown={r[\"unknown_substate_warnings\"]} pageerrors={r[\"pageerrors\"]}')
"; }
$R static v1
echo "### S4b renamed handler deployed under the open page (cooldown 6s)"
$R backend be_v1e SCHEMA_EXTRA=0
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S4b.json --reloads 1 --hold 12 \
  --restart-cmd "$R stop be_v1e; $R backend be_rename SCHEMA_RENAME=1 REFLEX_AUTO_RELOAD_COOLDOWN=6s" > $L/schema_S4b.out 2>&1; summarize $L/schema_S4b.json
grep -c "does not match" $L/be_rename.log | sed 's/^/  backend mismatch log lines: /'
$R stop be_rename
echo "### S5 extra substate deployed under the open page (cooldown 8s)"
$R backend be_v1c SCHEMA_EXTRA=0
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S5.json --reloads 1 --hold 12 \
  --restart-cmd "$R stop be_v1c; $R backend be_extra SCHEMA_EXTRA=1 REFLEX_AUTO_RELOAD_COOLDOWN=8s" > $L/schema_S5.out 2>&1; summarize $L/schema_S5.json
grep -c "does not match" $L/be_extra.log | sed 's/^/  backend mismatch log lines: /'
grep -c "Skipped state update for unknown substate" $L/be_extra.log | sed 's/^/  backend unknown-substate reports: /'
grep -n "Skipped state update\|does not match" $L/be_extra.log | head -4 | cut -c1-200
echo "### S5b fresh load of the old frontend against the extra-substate backend"
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S5b.json --reloads 2 > $L/schema_S5b.out 2>&1; summarize $L/schema_S5b.json
$R stop be_extra
$R stop static
echo "### done"
