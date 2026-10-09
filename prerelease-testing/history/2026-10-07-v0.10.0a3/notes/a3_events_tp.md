# a3_events_tp — events suite + third-party sweep on reflex 0.10.0a3 (2026-10-07, a3 pass)

Status: DONE (2026-10-07 ~22:15 UTC). Final report: `../board/results/a3_events_tp.md`; inbox files `a3_events_tp-1.md` (N-024 docs), `a3_events_tp-2.md` (#7493 duplicate boot delta).

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

### Auth demos (a3 vs a2 pass, `bin/cmp_checks.py` + `bin/compare_console.py`)
| run | a3 | vs a2 |
|---|---|---|
| reflex-local-auth demo dev / prod / prod+redis (38 checks, `drive_local_auth.py`) | 36/38 each (the known `_validate_fields` subclass-override pair) | identical checks, 0 new console anomalies, 0 tracebacks; redis had 24 keys |
| AppHarness `harness/test_local_auth_harness.py` (3464/8464) | 2 passed, 28 warnings (framework `PydanticDeprecatedSince20 __fields__`) | identical |
| dev hot reload while logged in (`drive_hmr_auth.py`) | 7/7 after warming the routes | identical to a2 pass. ANOMALY (pre-existing): on a COLD dev server the driver's first registration posts an empty username ("Username cannot be empty" while the field shows the value): a3 2/2 and a2 (`a3_events_tp-a2`) 1/1 cold runs; screenshot `tp/out/local_auth/a3-dev-hmr-report-fail.jpg`; not investigated further |
| reflex-magic-link-auth dev (11 checks) | 10/11 (known `/check-your-email` bounce) | identical |
| magic-link prod with `ML_FORCE_DEV=1`, real prod (captcha) | 10/11, 3/3 | identical when each run gets a FRESH db. NOTE: a first prod run on the dev run's db failed 3 checks with "Invalid email, or too many attempts" = the package's per-IP OTP rate limit (5 per 30 min, `reflex_magic_link_auth/state.py:_generate_otp`) tripped by the preceding dev run: test-order artifact, not a regression |
| reflex-google-auth dev / prod (13 checks) | 12/13 (driver's "key discoverable" check, same on a2); bogus token cleared by the tokeninfo computed var; does not unlock /protected | identical |
| fresh profile storage (`drive_fresh_storage.py`; F-002 risk from #7493) | local-auth, magic-link, google-auth: only `theme`/`last_compiled_theme` + per-tab session `token`; no package storage key written | identical (F-002 stays fixed) |

### #7493 hunt: boot deltas
- `events/src/bootdup` + `driver/drive_bootdup.py` (core only, ports 3474/8477): per reload with a stored value, a3 sends
  4 deltas (storage var + every dependent computed var twice, each dependent var evaluated twice), a2 3 deltas / once,
  0.9.12 4 / twice (same as a3); fresh profile: nothing written to localStorage on any version -> inbox `a3_events_tp-2.md` (low).
- `tp/drivers/drive_boot_frames.py <base> <out> local|magic <server_log>` (logged-in reload x3 + 5 tabs, prod):
  local-auth a3 second boot delta re-sends `auth_token`/`is_authenticated`/`authenticated_user` (a2: only `is_hydrated`);
  magic-link: token re-sent, 0 frames in tab 0 while 5 tabs open, 0 idle frames, all tabs logged in, same as a2.
- mini app (E-1..E-4, on_load partial delta, bg raise, supersedes, emoji prerender, ComponentState private attrs):
  a3 dev and prod identical to a2 (`out/mini_a3_{dev,prod}`, `tools/mini_summary.py`).

### N-039 / pytest (Python only)
`pytest_downstream/test_pkg_states.py`: a3 19/19; a2 12 failed + 6 errors; 0.9.12 11 pass / 8 fail (patches ignored).
a2-pass probes on my venvs (`tp/logs/pytest-probes-a2pass.txt`): test_min a3 2 passed (a2 1F/1E); backend_var a3 5/6
(the 1 failure = `Mock()` rejected/called as a factory for `_client: Client | None`, documented N-040; a2 5 failed);
other_attrs a3 10/10 (a2 3 failed + 1 error from the leak).

### More rerun commands
```bash
# bootdup (#7493): bash $W/bin/start.sh <a3|alpha2|stable> <dev|prod> <label> bootdup ; base 3474 (dev) / 8477 (prod)
(cd $W/driver && env $D drive_bootdup.py http://localhost:3474 $W/out/bootdup/<label>.json $W/logs/<label>.log)
# N-024: same with app n024doc and drive_n024.py BASE OUT_JSON SERVER_LOG
# mini: bash $W/bin/start.sh a3 dev mini_a3_dev mini ; (cd $W/driver && env $D drive_mini.py http://localhost:3470 $W/out/mini_a3_dev mini_a3_dev)
# auth demos (copy apps/<demo> to run/<x>/, then `TP_EXPECT_VENV=<venv> <venv>/bin/reflex db migrate` in it):
#   local: bin/start_app.sh a3_events_tp-all <dir> 3463 8463 <log>; drivers: drive_local_auth.py <base> $TW/out/local_auth a3-dev <dir>/reflex.db
#   prod:  REFLEX_API_URL=http://localhost:8467 bin/start_app.sh ... 8467 8467 <log> --env prod  (+ REFLEX_REDIS_URL=redis://localhost:8469 for redis)
#   magic: drive_magic_link.py <base> $TW/out/magic_link a3-dev <server log>   (prod: ML_FORCE_DEV=1; real prod: drive_magic_prod_real.py <base> <json>) - FRESH db per run
#   google: GOOGLE_CLIENT_ID=123456789012-dummyclientid.apps.googleusercontent.com, drive_google_auth.py <base> $TW/out/google_auth a3-dev
#   fresh storage: drive_fresh_storage.py <base> <label> <json> / [/login]
#   boot frames: drive_boot_frames.py <base> <json> local x | magic <server log>
#   HMR: drive_hmr_auth.py http://localhost:3463 <dir>/local_auth_demo/local_auth_demo.py <log> <json>   (warm the routes first, see above)
# AppHarness: cd $TW/harness && TP_VENV=a3_events_tp-all TP_FP=3464 TP_BP=8464 REFLEX_TELEMETRY_ENABLED=false NO_PROXY=localhost,127.0.0.1 $SB/envs/a3_events_tp-all/bin/python -m pytest -x -s -p no:cacheprovider test_local_auth_harness.py
```

## Not covered
Real OAuth/Clerk logins and CDN-hosted assets (sandbox), reflex-chakra/community ag-grid (do not import anywhere),
0.9.12 evapp columns re-run today (the a2-pass 0.9.12 reports were re-used; the a2 positive control was re-run),
Redis for the evapp suite and the mini app (the E-2 Redis cases are unchanged code paths; local-auth and tp_patterns
did run prod+redis), Python versions other than 3.12, root cause of the cold-dev registration race (identical on a2).
All servers, proxies and redis were stopped (`lsof` on 3460-3479/8460-8479 clear at the end).
