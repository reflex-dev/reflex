# a4_upgrade_ent — upgrade, third-party and enterprise spot check on reflex 0.10.0a4 (2026-10-08)

Agent `a4_upgrade_ent`. Spot check that the three a4 changes (#7505 state.js storage echo, #7516 metaclass refuses class-level
assignment over a state var, #7513 docs) do not break real apps. Everything installed from PyPI (uv `--no-config`, cwd `$SB`) or,
for enterprise, from the offline a5 wheel by file path. Nothing was installed from or run inside `/home/user/reflex` or
`/home/user/reflex-enterprise`. Every app config / driver carries a venv guard (`QA_EXPECT_VENV` / `TP_EXPECT_VENV` in rxconfig,
`VENV_GUARD` banner in enterprise start scripts, `/scratchpad/envs/driver/` assertion in every Playwright driver).
Host: 4-CPU container shared with `a4_hydration`; one app server set at a time.

## Verdict (2026-10-08 15:45-16:45 UTC)

**No regression from a3 (or 0.9.12) found; no new issue.** Every flow re-run here gives the same per-check result as the a3 pass:
- In-place upgrades 0.9.12 -> a4 of form-designer (reflex-local-auth, db), github-stats (LocalStorage-heavy) and twitter (prod + Redis), and
  a3 -> a4 of twitter (prod + Redis): identical pass/fail/anomaly counts to the a3 pass in dev, prod and cold; 0.9.12- and a3-pickled Redis
  sessions load on a4; a3 -> a4 moves only reflex + reflex-base and leaves `.web/package.json` byte-identical. No reflex-examples app writes a
  state var through its class, so #7516 hits none of them (0 TypeError in every log).
- Third party: 22-package import sweep identical to a3; reflex-local-auth (dev/prod/prod+Redis), reflex-magic-link-auth (dev/prod; its
  `sync=True` session token drives cross-tab login AND logout) and reflex-google-auth identical to a3 check by check, 0 console diffs.
- Enterprise 0.9.7a5 on a4: nothing in the wheel writes a state var through its class; **N-032 stays fixed** (dev Redis and prod 1 worker,
  stale/away/xtab 3/3 each); auth flows ALL_PASSED, a4 auth matrix 36/36 + MCP; **N-025 stays fixed** (entv 13/13 scenarios as a3, aggrid_min 4/4);
  dnd/flow/mantine/map identical to a3 (flow's N-026 reload race and N-028 page error appear on both versions).
- #7505 is visible only as the intended improvement: the enterprise token hash (`LocalStorage(sync=True)`) is no longer rewritten on every boot
  (0 vs 1 write per boot; per run 1 vs 8, relogin 4 vs 13) with identical events and outcomes; `sync=False` vars (local-auth, github-stats,
  google-auth) are written exactly as on a3.

```bash
export SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
export W=$SB/apps/a4_upgrade_ent          # this DEST dir mirrors $W (minus .web, dbs, run dirs, pngs; JSON/logs > 30 KB gzipped: zcat); tools/sync_dest.sh copies
```
Ports: upgrades 3600/8600 (form-designer), 3604/8604 + GraphQL stub 8608 (github-stats), 3612 prod (twitter 0.9.12->a4),
3614 prod (twitter a3->a4), redis 8609; third-party 3463/8463 dev, 8467 prod, redis 8469; enterprise auth 3620-3627/8620-8627,
redis 8629, mock IdP 8638 (the a3_ent_auth ports + 280); AG Grid / demos 3470-3479/8470-8479.

Layout: `up/` (upgrades: `bin/`, `scripts/` = a3_upgrade drivers unchanged, app sources with a venv guard added to rxconfig,
`logs/`, `freeze/`, `pkg/`, `shots/`), `tp/` (third-party: `bin/`, `drivers/`, `apps/`, `probes/`, `logs/`, `out/`),
`ent/auth/` (a3_ent_auth copy, ports remapped: `bin/ drivers/ scripts/ src/ a4auth/ logs/ shots/`), `ent/grid/` (a3_ent_grid copy,
ports remapped: `bin/ drivers/ scripts/ src/ out/ logs/`), `tools/`.

## 1. In-place upgrades (reflex-examples apps; a3_upgrade drivers and QA patches, unchanged)

Venvs (`up/bin/build_base_venvs.sh`, freezes `up/freeze/<k>-base.txt`): `$SB/envs/a4_upgrade_ent-{fd,gh,twr}` = Python 3.12,
`-r requirements.txt 'reflex==0.9.12'` (+ `'sqlalchemy<2.1'` for the db apps, exactly as the a3 pass); `a4_upgrade_ent-twa3` = what an
a3 tester had: `--prerelease=allow 'reflex[db]==0.10.0a3' 'pydantic<2.14'`.
Upgrade in place (same venv, app dir, `.web/`, `reflex.lock/`, `reflex.db`, persistent Chromium profile; `up/bin/common.sh upgrade()`):
`uv --no-config pip install --python <venv> --prerelease=allow -U 'reflex[db]==0.10.0a4'` (0.9.12 paths, NO pydantic pin: a user's
graph; pydantic 2.14.0 is now a stable release and the 0.9.12 venvs already resolved it) and `... -U 'reflex[db]==0.10.0a4' 'pydantic<2.14'`
for a3 -> a4 (keeps the a3 tester's graph so only the train packages can move). Note: the a3 pass pinned `pydantic<2.14` on every
upgrade, so these a4 runs differ from the a3 runs by pydantic 2.14.0 vs 2.13.5 on the 0.9.12 paths.

Rerun (one server at a time; each script prints a summary, details in `up/logs/`, `up/shots/<k>/*.json`):
```bash
$W/up/bin/build_base_venvs.sh
$W/up/bin/seq_fd.sh  > $W/up/logs/seq-fd.txt    # form-designer (reflex[db] + reflex-local-auth): 3600/8600; prod 3600
$W/up/bin/seq_gh.sh  > $W/up/logs/seq-gh.txt    # github-stats (+ GraphQL stub up/scripts/github_stub.py on 8608): 3604/8604
$W/up/bin/seq_twr.sh > $W/up/logs/seq-twr.txt   # twitter prod + Redis 8609, 0.9.12 -> a4 (+ rollback to 0.9.12): 3612
$W/up/bin/seq_twa3.sh > $W/up/logs/seq-twa3.txt # twitter prod + Redis 8609, a3 -> a4: 3614
# (up/bin/chain_rest.sh ran gh, twr, twa3 back to back after fd)
```
#7516 static check first: `up/logs/grep_examples_class_writes.txt` — no `<State>.<var> =`, `cls.<var> =`, `type(self).<var> =` or
`setattr(<StateClass>, ...)` anywhere in the 27 reflex-examples apps (commit ebe19ff), so no example app can hit the new TypeError at import.

Freeze diff 0.9.12 -> a4 (every app, `up/freeze/<k>-base-to-up.diff`): reflex/reflex-base 0.10.0a4, reflex-build-sdk 0.1.0a1 (new), components
code/core/gridjs/markdown/moment/plotly/radix/recharts 0.10.0a2, dataeditor/react-player/sonner 0.10.0a1, lucide 1.1.0a1, hosting-cli 0.2.0a1,
sqlalchemy 2.0.54 -> 2.1.4, wrapt 2.5.0 (github-stats had no `[db]` before: + alembic, greenlet 3.5.6, sqlmodel, ...) = the a3 diff with reflex/reflex-base at a4.
`uv pip check` clean. `.web/package.json` diff after the first a4 run (`up/pkg/<k>-base-to-up.package.diff`) is byte-identical to the a3 pass's
for form-designer and github-stats (react 19.2.8->19.3.0, react-error-boundary 6.1.6, socket.io-client 4.8.4, autoprefixer 10.6.1, postcss 8.5.29,
vite 8.3.2, + moment 2.31.0 in form-designer). Cold rebuild (`rm -rf .web`) = identical package.json and file list.

| app / run | a4 result (pass/fail/anomaly) | a3 pass (same flow) | notes |
|---|---|---|---|
| form-designer 0.9.12 `full` / `entry` | 18/0/2 / (entry run on a4 only) | 18/0/2 | anomalies = app's login auto-redirect (pre-existing) |
| form-designer a4 in place `up` / `entry` | **12/0/1 / 14/0/1** | 12/0/1 / 14/0/1 | protected editor rendered from the 0.9.12-written `_auth_token` (local-auth LocalStorage) without login |
| form-designer a4 prod `up` / `entry` | **12/0/1 / 15/0/0** | 12/0/1 / 15/0/0 | prod routes `/edit/form/1` `/form/1` `/responses/1` 200, `/nope` 404, `/login` 307 (same) |
| form-designer a4 cold `up` | **12/0/1** | 12/0/1 | |
| github-stats 0.9.12 `fresh` | 14/0/2 | 14/0/2 | anomalies pre-existing (widget dark appearance, React value-without-onChange) |
| github-stats a4 in place `persist` | **12/0/2** | 12/0/2 | users + stats restored from 0.9.12-written LocalStorage |
| github-stats a4 prod `persist` / cold `fresh` | **13/0/1 / 14/0/2** | 13/0/1 / 14/0/2 | |
| twitter prod+Redis 0.9.12 `base` | 19/0/2 | 19/0/2 | anomalies = app's `bg.svg` 404s (pre-existing) |
| twitter stale tab across stop -> upgrade -> a4 | **8/0/3** | 8/0/3 | old tab keeps working against a4, session kept; F-019 log-only version warning |
| twitter a4 prod `up` with the 0.9.12 tokens | **12/0/2** | 12/0/2 | **0.9.12-pickled Redis sessions load on a4** (alice, bob logged in without re-login, rows intact) |
| twitter a4 prod `base` (new users) | **19/0/2** | 19/0/2 | |
| twitter rollback to 0.9.12 on the same Redis | 11/1/2 | 11/1/2 | same as a3: a4-modified session discarded silently, the FAIL is the driver's "every session resets" expectation |

Storage on the first a4 load of the 0.9.12-written profiles (`storage_probe.py --forbid-writes`): 0 changing app writes in both apps;
form-designer: 1 idempotent `setItem _auth_token` (same value); github-stats: idempotent rewrites of `selected_users_json` x1, widget
`user_stats_json` x1, `last_fetch` x1 and `user_stats_json` x292 in 8 s (app's refetch loop for the unknown user `ghost1`; a3 pass 208, a2 147)
— identical in kind to a3 (O-3). Expected: #7505 only suppresses echo writes for `sync=True` LocalStorage vars and every LocalStorage var in
these apps (local-auth `auth_token`, github-stats' four) is `sync=False`, which a4 writes exactly as a3 did.
Server logs: same signatures as the a3 pass (form-designer pydantic serializer UserWarning from the app's model + vite console relays; github-stats
`Attempting to send delta to disconnected client` 579 in the in-place dev run vs a3 359 — scales with the refetch-loop count above —,
`RouterData.page` deprecation; twitter: granian's 9-workers-on-4-CPUs warning (O-4), F-019 `Frontend version 0.9.12 ... does not match`).
0 tracebacks, 0 TypeError in any a4 log (no #7516 hit). Shutdown: a4 exits 2-3 s after SIGTERM, ports free; 0.9.12 dev leaves the node
process on the frontend port (known, fixed since a1).

### a3 -> a4 in place (twitter prod + Redis; `up/bin/twa3_rerun.sh` = rebuild the a3 venv + `seq_twa3.sh`)
`uv pip install -U --prerelease=allow 'reflex[db]==0.10.0a4' 'pydantic<2.14'` from the a3 tester's venv moves ONLY reflex and reflex-base
0.10.0a3 -> 0.10.0a4 (`up/freeze/twa3-base-to-up.diff`); `.web/package.json` after the first a4 run is IDENTICAL to the a3 one
(`up/pkg/twa3-base-to-up.package.diff` empty) and `reflex.lock/package.json == .web/package.json`.
| run | a4 result | a3 pass (a2 -> a3, same flow) |
|---|---|---|
| a3 prod `base` | 19/0/2 | 19/0/2 |
| stale tab across stop -> upgrade -> a4 | **8/0/3** | 8/0/3 |
| a4 prod `up` with the a3 tokens | **12/0/2** — **a3-pickled Redis sessions load on a4** without re-login | 12/0/2 |
| a4 prod `base` | **19/0/2** | 19/0/2 |
Server log: only granian's worker-count warning and `Warning: Frontend version 0.10.0a3 for session ... does not match the backend version 0.10.0a4` (F-019 style).
Attempt 1 (`up/logs/twa3-attempt1/`) had 2 FAILs in the stale-tab driver because MY script told the stale user `davet` to follow `alicet`
while the users had been created with suffix `s` (a sed slip when adapting `seq_twr2.sh`); fixed (`QA_USER_SUFFIX=t`) and rerun clean.

## 2. Third-party sweep on a4 (imports + local-auth / magic-link / google-auth flows)

Venv `$SB/envs/a4_upgrade_ent-tp` (`tp/bin/build_venv.sh`, freeze `tp/logs/a4-tp-freeze.txt`) = the a3 sweep's spec with a4:
`--prerelease=allow 'reflex[db]==0.10.0a4' 'reflex-base==0.10.0a4' 'reflex-hosting-cli==0.2.0a1' 'pydantic<2.14' $(cat tp/packages.txt) authlib
'google-api-python-client>=2.184.0'` -> resolves (reflex-local-auth 0.5.0, magic-link 0.2.2, google-auth 0.2.0, sqlalchemy 2.1.4, greenlet 3.5.6,
pydantic 2.13.5), `uv pip check` clean, no package caps reflex.

Import sweep (`tp/probes/import_sweep.py`, run from a copy in `tp/run/probes`: `$SB/envs/a4_upgrade_ent-tp/bin/python -I import_sweep.py a4_upgrade_ent-tp`,
output `tp/logs/import_sweep.a4.txt`; comparison `tp/bin/cmp_sweep.py <a3 json> <a4 txt>` -> `tp/logs/import_sweep.cmp_a3_a4.txt`):
**22/22 identical to the a3 sweep** — 20 import, reflex-chakra (`_issubclass` ImportError) and community reflex-ag-grid (`reflex.base`)
fail as on a3 and 0.9.12 (known); reflex-clerk imports with the same 1 warning. No import raises the #7516 TypeError (the sibling
a4_class_state got the same with its own venv: `../a4_class_state/logs/downstream/import_sweep.*`).

Flows (`tp/bin/seq_tp.sh [venv] [label]`, fresh app copy + fresh db per run; drivers from the a3 sweep unchanged; compare a3 vs a4
check-by-check with `tp/bin/cmp_checks.py` and console with `tp/bin/compare_console.py`; `tp/bin/run_google.sh` for google-auth):
```bash
$W/tp/bin/build_venv.sh
$W/tp/bin/seq_tp.sh a4_upgrade_ent-tp a4 > $W/tp/logs/seq-tp-a4.txt   # la dev 3463/8463, la prod 8467, la prod+redis 8467 + redis 8469, ml dev, ml prod (ML_FORCE_DEV=1)
$W/tp/bin/run_google.sh a4_upgrade_ent-tp a4 > $W/tp/logs/run-google-a4.txt
```

| flow (a4, `a4_upgrade_ent-tp`) | a4 | a3 sweep (same driver) | vs a3 |
|---|---|---|---|
| reflex-local-auth demo dev / prod / prod+Redis (38 checks: register, login, redirect_to, protected on_load, reload, **second tab shares login, second tab logged out after reload**, fresh context anonymous, whoami substates, user switch, short session expiry, new tab after expiry) | **36/38 each** (the known `_validate_fields` subclass-override pair) | 36/38 each | `cmp_checks.py`: 0 differing checks; `compare_console.py`: 0 only-in-a3 / 0 only-in-a4; 0 tracebacks; Redis 24 keys (a3: 24) |
| reflex-magic-link-auth dev / prod (`ML_FORCE_DEV=1`) (11 checks: link login in tab2, **tab1 follows via `session_token` LocalStorage(sync=True)**, OTP reuse, **logout in tab1 -> tab2 logged out via LocalStorage sync**, rate limit) | **10/11 each** (known `/check-your-email` bounce) | 10/11 each | 0 differing checks, 0 console diffs, 0 tracebacks |
| reflex-google-auth dev (13 checks: bogus token cleared by the tokeninfo computed var, does not unlock /protected) | **12/13** (driver's "key discoverable" check) | 12/13 | 0 differing checks; the same 11 anomaly signatures (Google endpoints blocked by the sandbox) |
#7505 relevance: magic-link's `session_token` is the only `sync=True` LocalStorage var among the three packages (local-auth `auth_token` and
google-auth's two are `sync=False`, written as on a3); its cross-tab login and logout both still propagate through the storage event on a4.

## 3. reflex-enterprise 0.9.7a5 (offline wheel) on a4 (`$SB/envs/a4-ent`, `CI=true`)

### 3a. #7516 grep of the a5 wheel (`ent/logs/grep_ent_a5_class_writes.txt`, complements the sibling's `../a4_class_state/logs/downstream/grep_class_writes.txt`)
Every `setattr(`, `__fields__` / `get_fields()` / `add_var` / `add_field`, `type(x).attr =`, `<X>State.<attr> =` / `state_cls.<attr> =` in
`$SB/downloads/enterprise_wheel_a5/x/reflex_enterprise`. Results: `enforcement.py:1089/1098` `setattr(substate, name, ...)` and
`oidc/state.py:688` `setattr(self, ...)` write INSTANCES (`_reset_protected(substate: BaseState, ...)`, `state_cls = type(substate)`);
`enforcement.py:1588/1628` `state_cls.get_delta = ...` / `state_cls.dict = ...` replace METHODS (not state vars, the #7516 guard only fires for
a name resolving to a var's Field); `comp.State._grid_component`, `cls._model_class`, `cls._primary_key`, `cls._has_registered_endpoints`,
`cls._has_registered_handlers` target `ClassVar`s (sibling's finding); the rest are on non-state objects (ORM rows, app, config, functions,
modules). `__fields__` reads are on SQLModel/pydantic models; `get_fields()` reads only. => nothing in enterprise a5 that #7516 can hit;
confirmed at runtime: 0 `TypeError` in every enterprise server log below.

### 3b. Auth (`ent/auth/`, a3_ent_auth fixtures; `ent/auth/bin/seq_ent_auth.sh [venv] [label] [parts]`)
```bash
$W/ent/auth/bin/seq_ent_auth.sh a4-ent a4e 123 > $W/ent/auth/logs/seq-ent-auth-a4e.txt
#  starts redis 8629 + oidc-provider-mock 8638 (scripts/mock_oidc.py, run by the read-only alpha2-ent python as in a3), then
#  part 1: vauth_a4e dev+Redis (3620/8620): drivers/vdrv.py stale|away|xtab x3, drivers/race.py, drivers/hunt.py loads|relogin x2
#  part 2: entauth_a4e dev+Redis: scripts/drive_auth_redis.py cycle,pubnav,twotab,xtab; xtab_probe.py x5; stale_hash_probe.py x3; hydration_token_probe.py
#  part 3: scripts/a4_matrix.sh a4-ent a4e (dev, memory; 3622/8622, 3623/8623, backend-only 8626) + bin/a4_tally.sh a4e
# a3 / 0.9.12 references: the a3 pass JSONs (gunzipped into ent/auth/logs/a3ref/, not copied to DEST); hunt comparison:
#  mkdir -p run/huntcmp/{drivers,logs}; cp drivers/hunt_cmp.py run/huntcmp/drivers/; cp <a3e/a4e/s912e5 hunt jsons> run/huntcmp/logs/
#  (cd run/huntcmp/drivers && $SB/envs/driver/bin/python -I hunt_cmp.py a3e-dev-redis a4e-dev-redis s912e5-dev-redis) -> logs/hunt_cmp_a3e_a4e_s912e5.txt
```
**N-032 (part 1, vauth, dev Redis) — still FIXED:**
| probe | a4 + a5 | a3 + a5 (a3 pass) | 0.9.12 + a5 |
|---|---|---|---|
| stale P1 anon boot bogus hash -> "" | **3/3** | 3/3 | 3/3 |
| stale P2 signed-in boot re-asserts the real hash | **3/3** | 3/3 | 3/3 |
| stale P3 cookies cleared + hash "" -> signed out | **3/3** | 3/3 | 3/3 |
| stale P4 control (live storage event) | 3/3 | 3/3 | 3/3 |
| away (logout in tab2, Back in tab1) -> signed out | **3/3** (tab1 ends on /login after its protected click 3/3) | 3/3 | 3/3 |
| xtab two-tab race, tab1 logged out | **3/3**, 0 accepted-after-logout (race 3/3, all healed by tab2's reconcile) | 6/6 | 6/6 |
Boot events as on a3: `hydrate_and_load`, then on a hash mismatch `/_reflex/cookies/sync` (200) + `reconcile_tokens_after_sync`.
A3-09 (reset tab left on the protected page until its next protected event) unchanged in kind: P3 tab on /vault 2/3, /login 1/3 (a3: /vault 3/3;
it is the race the a3 verifier described), every protected click -> /login.

**#7505 visible effect (intended):** `hunt loads` (alice signed in; reload x3, new tab /vault, new tab /, client nav, 10 s idle with 3 tabs):
a4 sends exactly the same events as a3 (1 `hydrate_and_load` per boot, `update_vars_internal` + `on_load_internal` on client nav, 0 idle events,
1 cookie sync) but writes the `latest_access_token_hash_ls` (`LocalStorage(sync=True)`) **0 times per boot** instead of once (a3 and 0.9.12
re-wrote the same value on every boot / client nav): total hash writes per run 1 (the login) vs 8 on a3 and 0.9.12. `hunt relogin` (alice ->
add -> reload -> logout -> bob on the same tab -> reload -> add -> new tab): ok 2/2 (a3 2/2), hash writes 4 vs 13 — the real changes (login,
logout "", bob's hash) are still written. No storage event storms, no lost logouts.

**Auth flows (part 2, explorer app `entauth`, dev Redis):** `drive_auth_redis.py` cycle (login/logout/re-login), pubnav, twotab, xtab
(cross-tab logout) **ALL_PASSED** (a3 ALL_PASSED); `xtab_probe.py` **TAB1_LOGGED_OUT 5/5** (a3 5/5); `stale_hash_probe.py` **CORRECTED
anon_boot 3/3, loggedin_boot 3/3, live_update 3/3** (a3 identical); `hydration_token_probe.py` SUMMARY `{reload_writes: True, newtab_writes: True,
garbage_protected: False, garbage_public: False, garbage_id_refresh: False, garbage_all_after_login: True}` = the a3 line verbatim (the garbage_*
flags are the 0.9.12 ones, see a3 notes). Failed requests only the known-benign mock-IdP pico.css tunnel error and cookie-sync keepalive
`ERR_ABORTED` on navigation; 0 page errors; server log 0 tracebacks, 0 TypeError.

**10-05 a4 auth matrix (part 3, dev, memory manager; servers on a4-ent, drivers on the read-only `ent_auth2-drv` venv as in the a3 pass):**
full upstream auth app **22/22**, public nav + 2 reloads **3/3**, auth_min default **4/4**, extra scopes **4/4**, iframe pending replay **3/3**
= **36/36** (a3 36/36, 0.9.12 36/36); MCP OAuth (discovery, registration, consent, PKCE, protected event, code replay, refresh rotation) and
anonymous MCP (token rejection, events, computed reads, redaction, session isolation) pass. 0 tracebacks, 0 TypeError; failed requests = the
known cookie-sync keepalive aborts. Logs `ent/auth/a4auth/logs/a4e/`.

### 3c. N-025 AG Grid quick re-check + demo route smoke (`ent/grid/`, a3_ent_grid fixtures; ports 3470-3479/8470-8479)
```bash
$W/ent/grid/bin/seq_grid.sh a4-ent a4 12 > $W/ent/grid/logs/seq-grid-a4.txt
#  part 1: bin/run.sh a4-ent entv prod 3470 entv_a4ent_prod ; bin/run.sh a4-ent aggrid_min prod 3471 aggrid_min_a4ent_prod
#  part 2: bin/demo.sh a4-ent {dnd,flow,mantine,map} prod a4   (prod on 3478)
cd $W/ent/grid && $SB/envs/driver/bin/python -I drivers/summarize.py out entv_a4ent_prod > out/SUMMARY_a4.md; $SB/envs/driver/bin/python -I drivers/anomalies.py out/entv_a4ent_prod
```
**N-025 — still FIXED on a4 + a5 (prod):** entv s1-s13 all identical to the a3-ent prod column of the a3 pass: s1 full load state / literal grid
2h6c / 2h6c, s2 reload, s3 after unrelated-substate event, s4/s5, s6 client nav, s7, **s8 `/memo` memo-prop / State-in-memo 2h6c / 2h6c**, s9 on_load
page, s10 second context, **s11 `/detail` detail-grid headers `Count, Value` for both the State and literal params**, s12 lambda `rx.badge`
renderer 3 badges, s13 dynamic route (`ent/grid/out/SUMMARY_a4.md`). Boot = one `hydrate_and_load` in the socket.io connect auth, deltas carry the
root state only (as a3); grid headers ~95 ms after the `window.__reflex` assignment (e.g. s1 213 ms / 308 ms). Explorer probe `aggrid_min`
4/4 PASS (State grid `Make, Price` on load and reload). 0 page errors; console only the AG Grid trial banner + `/favicon.ico` 404 (benign);
0 server tracebacks.

**Demo route smoke (prod, a4 + a5; `bin/demo.sh a4-ent <demo> prod a4`, outputs `ent/grid/out/<demo>_prod_a4*`):**
| demo | a4 + a5 prod | a3 + a5 prod (a3 pass) | verdict |
|---|---|---|---|
| dnd (react-dnd kanban) | **27/27**, 0 console/page errors | 27/27 | same |
| flow (React Flow) | run 1 **20/22** + 1 page error; reruns 21/22, 21/22 | 20/22 (today's a3-ent rerun 20/22) | same failures in kind: `index lists 6 flow demos` (driver expectation) and N-026 (reload reverts controlled edits) — a race on both versions, see below; the page error is N-028 |
| mantine | **23/23** + 1 page error | 23/23 + the same page error | same (pre-existing N-028 `Cannot read properties of null (reading 'name')`) |
| map (leaflet) 4 routes | **4/4** | 4/4 | same (54 OSM tile requests blocked by the sandbox proxy) |
0 server tracebacks in every run.
- flow run 1 page error: `Cannot read properties of null (reading 'name')` on `/overview` at t=9.7 s = N-028 (reflex's `window.onerror` dereferences
  the `null` error of a benign "ResizeObserver loop" event; known, pre-existing since 0.9.12, `window.onerror` is untouched by the a3->a4 diff);
  it did not recur in 2 a4 reruns or in the a3 run (timing of the ResizeObserver loop).
- N-026 A/B (`ent/grid/bin/flow_reload_ab.sh N`, `ORDER`/`TAG` env; `scripts/probe_flow_reload.py` x N per server, prod 3478,
  outputs `ent/grid/out/flow_reload_<venv>-<tag>r<i>.txt`): moved node survives reload — order a4 then a3: **a4 2/4, a3 0/4**; reversed
  order: **a3 3/3, a4 2/3**. Whenever it fails, the boot sends the mount-time `set_nodes` with the compiled-default positions (the N-026
  mechanism); when it passes, only `hydrate_and_load` is sent. => a timing race on both versions (a2 pass: 5/5 and 0.9.12 3/3 failing on
  a busier machine); no a4-attributable change.

**Extra #7505 checks (`ent/auth/bin/seq_ent_extra.sh a4-ent a4e`, dev Redis):**
- `hunt.py fresh` x2 (fresh anonymous browser, /, reload, client nav to protected, /pid): writes only `theme`/`last_compiled_theme`/`debug`
  + the per-tab session token, no token hash, no cookie, no client-storage default; identical to a3 (`ent/auth/logs/hunt_cmp_a3e_a4e_with_fresh.txt`)
  -> F-002 not back from the enterprise angle.
- `storx.py` (vauthx: protected `vx_draft = LocalStorage(sync=True)` + `vx_ck = Cookie`) x2: reload /vault, new tab /vault, new tab / keep
  alice's values (a3 same); client nav /vault -> /vault2 -> /vault -> / blanks them (= A3-10, known/filed, unchanged); anonymous boot with leftover
  values blanks them (a3 same). Write counts per boot: a3 wrote `vx_draft` twice and the cookie twice; a4 writes `vx_draft` ONCE (one of the two
  boot deltas carrying the same value is recognised as the echo of the `hydrate_and_load` value and skipped; the second identical delta is no
  longer matched because `takeEcho` consumes the entry, so it is written — same value, no storage event) and the cookie twice (cookies are still
  rewritten by design, renewing max_age). Observation only.

**N-032 in prod (`ent/auth/bin/seq_n032_prod.sh a4-ent a4e`: vauth, `--env prod` single port 8621, Redis, `GRANIAN_WORKERS=1`):**
stale P1/P2/P3/P4 **3/3 each**, away **3/3**, xtab **3/3** (0 accepted-after-logout; race 0/3) — a3 prod 1 worker: 3/3, 3/3, 3/3, 3/3, 3/3, 6/6.
0 tracebacks / 0 TypeError.

## Observations (not issues)
- O-1 pydantic 2.14.0 (released since the a3 pass) is what a plain 0.9.12 install resolves today and what stays after the in-place upgrade
  without a pin; reflex 0.10.0a4 ran form-designer, github-stats and twitter with it with results identical to the a3 pass (which ran 2.13.5).
  The shared `a4`/`a4-ent` venvs and my tp / a3-path venvs use `pydantic<2.14` (2.13.5).
- O-2 (#7505 design, enterprise vauthx) two identical boot deltas for a protected `LocalStorage(sync=True)` var: the first is skipped as the
  echo, the second is written (same value, no storage event); a3 wrote both. Harmless; noted because a second same-value write can in principle
  land over another tab's newer value written between the two deltas (millisecond window; the a4_hydration item owns storm/convergence tests).
- O-3 the in-place github-stats dev run still logs `Attempting to send delta to disconnected client` hundreds of times (app's refetch loop),
  proportional to a3's.
- Known, not re-reported: A3-09 (stale tab left blanked until its next protected event; P3 /vault 2/3), A3-10 (protected client storage blanked
  on client nav with Redis), N-026 (flow reload race), N-028 (window.onerror null error), F-019 (log-only frontend/backend version warning),
  granian 9-workers warning, the app-level 404s (`bg.svg`), favicon 404s, AG Grid trial banners, mock-IdP pico.css tunnel error, cookie-sync
  keepalive `ERR_ABORTED`.

## Harness slips (mine, fixed)
- `seq_twa3.sh` attempt 1: stale-tab user told to follow `alicet` while users had suffix `s` -> 2 FAILs; fixed + rerun clean (`up/logs/twa3-attempt1/`).
- `flow_reload_ab.sh` first call: relative log path after `cd` -> no server started; fixed to an absolute path.

## Cleanup
Every server, redis (8609, 8629, 8469), mock IdP (8638), GraphQL stub (8608) and Chromium started here was stopped (stop scripts after every
run); final check: no listener on 3600-3639, 8600-8639, 3460-3479, 8460-8479 and no process under `$SB/apps/a4_upgrade_ent`.
Venvs left (scratch, not in the repo): `$SB/envs/a4_upgrade_ent-{fd,gh,twr,twa3,tp}` (fd/gh/twr/twa3 are now at a4; twr was rolled back to 0.9.12).

## Not covered
- AG Grid demo app (ag_grid + QA pages: smoke/features/model) on a4 — needs its own faker/pandas venv; N-025 was re-checked on the entv
  fixture + explorer probe instead (the demo's numbers are known: model 24/29).
- Enterprise prod with the default 9 workers (N-033 territory, unchanged since a3); MCP prod suite; expiry matrix; entauth prod suite.
- reflex-examples apps other than form-designer / github-stats / twitter (clock was not re-run: no client storage beyond an `rx.Cookie`,
  cookies are untouched by #7505's echo logic); the a3 pass's `guide` app.
- The verifier's `vea` xsync scenario (A3-10's second trigger) on a4.
