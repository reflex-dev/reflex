# a3_events_tp — events suite + third-party sweep on reflex 0.10.0a3 (2026-10-07, a3 pass)

Status: IN PROGRESS (updated after every sub-test; another session can continue from "Remaining").

Versions: under test `$SB/envs/a3` (reflex/reflex-base 0.10.0a3); comparisons `$SB/envs/alpha2` (0.10.0a2 + greenlet),
`$SB/envs/stable` (0.9.12 + greenlet). Third-party venvs (own, from PyPI, identical except reflex/reflex-base, see
`tp/logs/{a3-all,a2,s912}-freeze.txt`): `a3_events_tp-all` (a3 + the 22 packages), `a3_events_tp-a2` (a2 + same),
`a3_events_tp-s912` (0.9.12 + same), `a3_events_tp-nodbextra` (`reflex==0.10.0a3` + local-auth + magic-link, no `[db]`).
Driver venv `$SB/envs/driver` (Playwright 1.63, Chromium /opt/pw-browsers/chromium).
`SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad`
Ports: evapp dev FE 3460 / BE 8460 / proxy 8462; evapp prod 8465 / proxy 8466; mini dev 3470/8470/proxy 8472;
mini prod 8475 / proxy 8476; n024doc dev 3474/8474/proxy 8473, prod 8477 / proxy 8478; third-party dev 3463/8463,
prod 8467 (single port), AppHarness 3464/8464; redis 8469. One server at a time.
Load: the machine was at load ~19 at start, ~4-5 during most runs; no check needed a load-induced rerun so far.

## 0. Positive control (a2, before any a3 run)
`bash events/bin/start.sh alpha2 dev a2ctl_dev evapp; bash events/bin/suite.sh a2ctl_dev http://localhost:3460 8460 sup,nested,bind t_deco,t_nested_cases,t_bind`
-> `deco.late_marker_after_is_background_read` FAIL, `nested.handler_returns_nested_list`/`handler_yields_nested_list`
FAIL, `bind` bg-parent `bump:self=StateProxy` + `bg_outside=ImmutableStateError`: exactly the a2-pass not-ok rows, so
the driver still detects them (`events/out/a2ctl_dev/`).

## 1. Events suite (copied from `../../2026-10-07/events/`; work dir `$SB/apps/a3_events_tp/events`)
Changes vs the a2 copy: paths (`apps/events2` -> `apps/a3_events_tp/events`), redis 8479 -> 8469, a venv guard in
`src/{evapp,mini,n024doc}/*/*.py` (asserts `/scratchpad/envs/$EV_EXPECT_VENV/` in `reflex.__file__`; `bin/start.sh`
exports it; server logs print `VENV_GUARD ok venv=...`), `bin/suite.sh` takes an optional 5th arg (test functions),
new `tools/diff_details.py` (record-by-record detail diff ignoring timing), `tools/log_sig.py` (normalized server-log
warning/error/traceback signature diff), new app `src/n024doc` + `driver/drive_n024.py` (N-024 docs claims).

### Rerun
```bash
W=$SB/apps/a3_events_tp/events   # = copy of DEST/events (src driver tools bin probes)
bash $W/bin/start.sh a3 dev a3_dev evapp && bash $W/bin/wait_up.sh http://localhost:3460/
bash $W/bin/suite.sh a3_dev http://localhost:3460 8460 && bash $W/bin/stop.sh a3_dev          # ~10 min
bash $W/bin/start.sh a3 prod a3_prod evapp && bash $W/bin/wait_up.sh http://localhost:8465/
bash $W/bin/suite.sh a3_prod http://localhost:8465 8465 && bash $W/bin/stop.sh a3_prod
A2=/home/user/reflex/prerelease_testing/2026-10-07/events
$SB/envs/driver/bin/python $W/tools/diff_details.py $A2/out/a2_dev/a2_dev_report.json $W/out/a3_dev/a3_dev_report.json
$SB/envs/driver/bin/python $W/tools/log_sig.py $A2/logs/a2_dev.log $W/logs/a3_dev.log
$SB/envs/driver/bin/python $W/tools/make_table2.py "a2 dev=..." "a3 dev=..." ... > $W/out/suite_table_a3.md
```

### Result: a3 == a2 in every row, dev and prod
`events/out/suite_table_a3.md` (a2 dev/prod and 0.9.12 dev/prod columns are the a2-pass reports, re-read, not re-run).
All 63 statuses identical a2 dev vs a3 dev and a2 prod vs a3 prod; `diff_details.py` finds only timing/path
differences (58/60 records byte-identical after removing timing keys; the 2 others differ only in screenshot path
and `delivered_s_after_up` 0.54 vs 0.44); `[console]` rows identical (proxy-drop reconnect errors; prod: favicon 404
and the known React #418 on `/vars`, E-4); server-log signatures identical (dev 33/33, prod 29/29 lines, same
distinct set). Info rows identical: `typelog.counts`, `api.undeclared_attribute_assignment` (prod silently sets,
dev raises), `bind.instance_access_and_inheritance` (`bg_outside=ImmutableStateError`, `bump:self=StateProxy`).

### N-024 docs claim (guide section "Calling inherited handlers from background tasks")
`src/n024doc` = the guide's own sample (Parent.count/bump, Child.work verbatim, Child.work_locked = sample 2) + probes;
`driver/drive_n024.py BASE OUT_JSON SERVER_LOG`. Run on a3 dev+prod, a2 dev, 0.9.12 dev+prod (`out/n024/`).
Every claim holds on a3 (dev = prod = a2): sample 1 raises ImmutableStateError (0.9.12: no error, unlocked write),
sample 2 works on both, read-only inherited handler runs outside the lock, inside the lock `type(self)` is
`StateProxy`, `self.__class__` is `Parent` (the declaring class, same as a foreground call and 0.9), isinstance True,
a same-state handler writing its own var raised on 0.9.12 too. NOT covered by the guide/changelog: a DIRECT write of
an inherited var (`self.count += 1` in a Child background task) or a same-state handler writing an inherited var,
outside the lock: 0.9.12 silently wrote, a2/a3 raise ImmutableStateError -> inbox `a3_events_tp-1.md` (low, docs).

## 2. Third-party sweep (copied from `../../2026-10-07/thirdparty_a2/`; work dir `$SB/apps/a3_events_tp/tp`)
Changes: paths, ports (3500/8500 -> 3463/8463, 3510 -> 8467, 3504/8504 -> 3464/8464, 8509 -> 8469), venv guard in
every `apps/*/rxconfig.py` (`TP_EXPECT_VENV` exported by `bin/start_app.sh`, or `TP_VENV` for AppHarness), new
`bin/cmp_checks.py` (check-by-check diff of two tpdrive reports), `pytest_downstream/test_pkg_states.py`.

| sub-test | a3 result | vs a2 pass |
|---|---|---|
| install | `reflex[db]==0.10.0a3` + 22 packages resolves; sqlalchemy 2.1.4 (a2 pass had 2.1.3); greenlet 3.5.6 via the `db` extra; no package caps reflex | same set |
| N-001 via packages | `reflex==0.10.0a3 reflex-local-auth reflex-magic-link-auth` WITHOUT `[db]`: greenlet comes in (both packages require `reflex[db]`); `import reflex_magic_link_auth`, `import reflex.model` OK (`tp/logs/nogl-import-a3.txt`) | fixed (a2: ImportError) |
| import sweep (`probes/import_sweep.py`) | 20/22 import; chakra (`_issubclass`), community ag-grid (`reflex.base`) fail | identical (also 0.9.12) |
| tp_components dev (35 checks) | 6 fail: audio CDN, webcam `muted`, monaco CDN, calendar on_change, dynoselect `VarTypeError ... Field`, clerk route | identical checks + console anomalies (`bin/compare_console.py`: 0 only-in-a2 / 0 only-in-a3) |
| tp_components prod (`TP_SKIP=clerk,monaco,webcam`, 34 checks) | 3 fail (audio, calendar, dynoselect) | identical |
| prod build with clerk / monaco / webcam alone | clerk `MISSING_EXPORT Event`; monaco prerender 500; webcam `muted is not defined` | identical (pre-existing) |
| reflex-chat `initial_messages` leak (F-009) | session B sees A's message | identical output |
| reflex-global-hotkey | keys + modifiers delivered | pass, same |
| reflex-dynoselect | page build fails `VarTypeError` | same |
| reflex-clerk `set_clerk_session` (`probes/clerk_jwt_probe.py`) | `TypeError: 'Field' object is not iterable` (class-level `jwt_public_keys` is a Field) | unchanged (0.9.12 validates the token) |
| tp_patterns dev / prod / prod+redis (11 + 4 checks) | 2 fail (F-001 class-level `Field` reads, expected); F-004 classassign 4/4 | identical |
| F-003 seed loop (`drive_storage_only.py`) | `tp_ls_cv` cleared: dev seeds 0,4,7; prod seeds 0,4; prod+redis | identical to a2 (fixed) |
| N-039 downstream (`pytest_downstream/test_pkg_states.py`, patches the PACKAGES' states: local-auth `auth_token` LocalStorage, magic-link `session_token` LocalStorage(sync), google-auth token, inherited var via `LoginState`, ComponentState `reflex_chat.Chat.messages`, decorator/stacked/manual) | **19/19 pass**, nothing leaks (default, storage wrapper/name/sync, compiled client storage, fresh instance) | a2: 12 failed + 6 errors (teardown `TypeError: A Field cannot overwrite another field`, leaks); 0.9.12: 11 pass / 8 fail (patches ignored by instances, no leak) |
| packages' own test suites | none of the 22 sdists (only reflex-pyplot has a component-only test) nor the GitHub repos of local-auth, magic-link, google-auth, chat, global-hotkey, clerk ship State tests | n/a |

### Rerun (third-party)
```bash
TW=$SB/apps/a3_events_tp/tp   # = copy of DEST/tp
cd $SB && uv --no-config venv --python 3.12 $SB/envs/a3_events_tp-all && uv --no-config pip install --python $SB/envs/a3_events_tp-all/bin/python --prerelease=allow \
  'reflex[db]==0.10.0a3' 'reflex-base==0.10.0a3' 'reflex-hosting-cli==0.2.0a1' 'pydantic<2.14' $(cat $TW/packages.txt) authlib pytest pytest-mock uvicorn psutil playwright==1.63.0 'google-api-python-client>=2.184.0'
#   a2: same with 'reflex[db]==0.10.0a2' 'reflex-base==0.10.0a2' greenlet -> a3_events_tp-a2; 0.9.12: 'reflex[db]==0.9.12' greenlet, no --prerelease -> a3_events_tp-s912
D="NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
cp -r $TW/apps/tp_components $TW/run/a3/ && $TW/bin/start_app.sh a3_events_tp-all $TW/run/a3/tp_components 3463 8463 $TW/logs/tp_components-a3-dev.log
(cd $TW/drivers && env $D drive_components.py http://localhost:3463 $TW/out/components a3-dev; env $D drive_chat_leak.py http://localhost:3463 a3)
$TW/bin/stop_app.sh $TW/pids/tp_components-a3_events_tp-all.pid
# prod: TP_SKIP=clerk,monaco,webcam REFLEX_API_URL=http://localhost:8467 bin/start_app.sh ... 8467 8467 <log> --env prod  (same TP_SKIP for the driver)
# prod build matrix: bin/prod_probe.sh a3_events_tp-all <rundir> <label> <skip-list>
# tp_patterns: bin/patterns_suite.sh a3_events_tp-all $TW/run/a3/tp_patterns a3 dev|prod ; prod+redis: redis-server --port 8469 --save '' --appendonly no &; REFLEX_REDIS_URL=redis://localhost:8469 bin/patterns_suite.sh ... a3redis prod
# F-003: bin/seed_loop.sh a3_events_tp-all $TW/run/a3/tp_patterns a3 dev 4 7 ; ... prod 0 4
# compare: $SB/envs/driver/bin/python $TW/bin/cmp_checks.py <a2 report> <a3 report>; bin/compare_console.py <a2 report> <a3 report>
# Python-only: (cd <copy of probes> && <venv>/bin/python import_sweep.py <venv>; clerk_jwt_probe.py <venv>; clerk_probe.py <venv>)
# N-039 downstream: cd $TW/pytest_downstream && EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q test_pkg_states.py
```

## Remaining (in order)
local-auth demo dev / prod / prod+redis (`drive_local_auth.py`) + AppHarness; magic-link dev + prod; google-auth dev +
prod; fresh-profile storage check (#7493 risk: F-002) for the three auth demos; mini app (E-1..E-4 and on_load
boot-delta cases) on a3 dev.
