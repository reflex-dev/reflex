#!/usr/bin/env bash
# S4a / S4b / S5 of the schema-hash scenarios (page open on a v1 backend, then the backend is swapped).
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
W=$SB/apps/frontend_store; L=$W/logs; R=$W/schema_run.sh
PW="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
cd $W
summarize() { $SB/envs/driver/bin/python -c "
import json; r=json.load(open('$1'))
fails=[c['name'] for c in r['checks'] if not c['ok']]
tl=[c for c in r['checks'] if c['name']=='timeline after restart']
print(f'  fails={len(fails)} {fails} mismatch={r[\"mismatch_warnings\"]} unknown={r[\"unknown_substate_warnings\"]} pageerrors={len(r[\"pageerrors\"])}')
if tl:
    for s in tl[0]['got']: print('   ', {k:v for k,v in s.items() if k in ('t','loads','nav','banner','hydrated','free_input','mismatch','unknown','err')})
"; }
$R static v1
echo "### S4a default-only change deployed under the open page (hash equal: no reload, no mismatch)"
$R backend be_v1d SCHEMA_EXTRA=0
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S4a.json --reloads 1 --hold 15 \
  --restart-cmd "$R stop be_v1d; $R backend be_default SCHEMA_DEFAULT=1" > $L/schema_S4a.out 2>&1; summarize $L/schema_S4a.json
grep -c "does not match" $L/be_default.log | sed 's/^/  backend mismatch log lines: /'
$R stop be_default
echo "### S4b renamed handler deployed under the open page (mismatch: reload once, then banner; cooldown 6s)"
$R backend be_v1e SCHEMA_EXTRA=0
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S4b.json --reloads 1 --hold 22 \
  --restart-cmd "$R stop be_v1e; $R backend be_rename SCHEMA_RENAME=1 REFLEX_AUTO_RELOAD_COOLDOWN=6s" > $L/schema_S4b.out 2>&1; summarize $L/schema_S4b.json
grep -c "does not match" $L/be_rename.log | sed 's/^/  backend mismatch log lines: /'
$R stop be_rename
echo "### S5 extra substate deployed under the open page: reload once, banner, unknown substate skipped+reported once"
$R backend be_v1c SCHEMA_EXTRA=0
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S5.json --reloads 1 --hold 25 \
  --restart-cmd "$R stop be_v1c; $R backend be_extra SCHEMA_EXTRA=1 REFLEX_AUTO_RELOAD_COOLDOWN=8s" > $L/schema_S5.out 2>&1; summarize $L/schema_S5.json
grep -c "does not match" $L/be_extra.log | sed 's/^/  backend mismatch log lines: /'
grep -c "Skipped state update for unknown substate" $L/be_extra.log | sed 's/^/  backend unknown-substate reports: /'
echo "### S5b fresh load of the old frontend against the extra-substate backend (first load mismatches)"
$PW drive_schema.py --url http://localhost:3227/ --out $L/schema_S5b.json --reloads 1 > $L/schema_S5b.out 2>&1; summarize $L/schema_S5b.json
grep -E "^\[|Timeout" $L/schema_S5b.out | head -12 | cut -c1-160
$R stop be_extra
$R stop static
echo "### done"
