# a5_upgrade_ent — enterprise, install/upgrade and third-party re-verification on reflex 0.10.0a5 (2026-10-08)

Agent `a5_upgrade_ent`. Everything installs from PyPI (uv `--no-config`, cwd `$SB`), or for enterprise from the offline
0.9.7a5 wheel (shared venvs `a5-ent` / `a4-ent` / `s912-ent-a5`, used read-only). Nothing was installed from or run inside
`/home/user/reflex` or `/home/user/reflex-enterprise`. Every app config / driver carries a venv guard (`QA_EXPECT_VENV` /
`TP_EXPECT_VENV` in rxconfig, `VENV_GUARD` banner in the enterprise start scripts, a `/scratchpad/envs/driver/` assertion in
every Playwright driver). Host: 4-CPU container shared with `a5_hydration_router`; one app server set at a time (
sequential chains, each waiting for the previous: `ent/bin_chain1.sh` (killed after N-032 prod a5 to fix a driver) -> `ent/bin_chain1b.sh` -> `chain2.sh` -> `chain3b.sh` -> `chain6.sh`).

```bash
export SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
export W=$SB/apps/a5_upgrade_ent   # this DEST dir mirrors $W (minus .web, dbs, run dirs, a4ref/); tools/sync_dest.sh copies
# set-up from the repo: copy this DEST dir to $W (the scripts carry absolute $W paths), mkdir -p the logs/out/run dirs.
```
$W was created from the a4 pass's work dir (`2026-10-08-a4/a4_upgrade_ent/`, paths rewritten a4_upgrade_ent -> a5_upgrade_ent);
the a4 pass's own logs/outputs sit in `$W/a4ref/` (not copied to DEST: they are in `../../2026-10-08-a4/a4_upgrade_ent/`).
Ports (all mine): enterprise auth 3620/8620 dev, 8621 prod, 3622-3623/8622-8623 + backend-only 8626 (matrix), Redis 8629,
mock IdP 8638; grid/demos 3470-3479/8470-8479; upgrades 3600/8600 (fd), 3604/8604 + stub 8608 (gh), 3612 (twr), 3614 (twa4),
Redis 8609; N-001 prod CRUD 3602; third party 3463/8463, 8467, Redis 8469.

## Verdict (2026-10-08 20:03-21:45 UTC)

**No regression from a4 (or 0.9.12) found; no new issue.** #7360 is invisible to reflex-enterprise auth except as the intended fix:
- Enterprise 0.9.7a5 on a5 vs a4 back to back: **N-032 stays fixed** (dev Redis + prod 1 worker: stale/away/xtab 3/3 each, 0 accepted after
  logout), auth flows ALL_PASSED, xtab_probe 5/5, stale-hash 3/3 x3, hydration-token SUMMARY verbatim, **auth matrix 36/36 + MCP OAuth +
  anonymous MCP**, hunt event/storage counts identical per step; **N-025 stays fixed** (entv s1-s13 table byte-identical to the a4 pass,
  aggrid_min 4/4); dnd 27/27, flow 20/22 (known), mantine 23/23 (+ known N-028), map 4/4; expiry / proactive refresh / revoke as before.
- New #7360 probe (deep link with query string, dynamic route, anonymous and signed-in client-side nav, reload, logout from a protected page,
  audit routes of every page-guard decision): identical on a5, a4 and 0.9.12 functionally (dev + prod); the page guard always sees the right
  page; and **on a4 / 0.9.12 the HttpOnly `_oidc_*_id_token` / `refresh_token` cookie values reach the browser inside `rx_router_headers`
  after a reload — on a5 they never do** (the fix, verified from the enterprise angle; server-side cookie reads keep working).
- reflex-azure-auth (on_load handlers that read `router.url` / query params, pointed at the mock IdP) passes on a5 and a4, dev + prod.
- Install paths: **N-001, F-005, F-006, F-014 still fixed** (py3.11 + 3.14, uv + pip, nothing added by hand; prod CRUD on a fresh db).
- In-place upgrades: form-designer and github-stats 0.9.12 -> a5, twitter prod + Redis 0.9.12 -> a5 and a4 -> a5: per-check results identical
  to the a4 pass; 0.9.12- and a4-pickled Redis sessions load on a5; a4 -> a5 moves only reflex + reflex-base, `.web/package.json` identical.
- Third party: no downstream package uses `State.router.headers.cookie` / `["cookie"]` / `raw_headers` in a component (grep of 38 wheels +
  sources); 22-package import sweep = a4; local-auth 36/38, magic-link 10/11, google-auth 12/13 = a4 check by check.

## Part 2a — install paths (N-001, F-005, F-006, F-014) — `inst/`
```bash
$W/inst/bin/n001.sh > $W/inst/logs/n001.txt          # pip venvs (py3.11 / 3.14 'reflex[db]==0.10.0a5', py3.12 plain 'reflex==0.10.0a5'), no --pre
SPECS="uv311:uv:3.11:db uv314:uv:3.14:db" $W/inst/bin/n001.sh > $W/inst/logs/n001-uv.txt   # uv venvs, --prerelease=allow
$W/inst/bin/dbcli.sh > $W/inst/logs/dbcli.txt        # greenlet_probe + reflex db init / makemigrations / migrate / makemigrations noop, per venv
$W/inst/bin/prod_crud.sh > $W/inst/logs/prod_crud.txt   # dbcli app --env prod on 3602: add x2, reload (drive_app.py)
cd $W/inst/cli_neutral && for a in component "component init" ...; do $SB/envs/a5/bin/reflex $a; done   # F-014 -> logs/f014_component_a5.txt
```
Venvs `$SB/envs/a5_upgrade_ent-n001-{uv311,uv314,pip311,pip314,f006pip312}`; nothing added by hand (no greenlet, no pydantic pin).
| check | result | evidence |
|---|---|---|
| N-001 pip py3.11 / py3.14 `pip install 'reflex[db]==0.10.0a5'` (NO `--pre`) | rc 0; sqlalchemy 2.1.4 + **greenlet 3.5.6** (via the extra) + sqlmodel 0.0.48 + alembic 1.20.0, pydantic 2.14.0; `import reflex.model` OK; `pip check` clean | `logs/n001.txt`, `logs/freeze-pip3*.txt` |
| N-001 uv py3.11 / py3.14 `uv pip install --prerelease=allow 'reflex[db]==0.10.0a5'` | rc 0; same graph (greenlet 3.5.6, pydantic 2.14.0); `uv pip check` clean | `logs/n001-uv.txt` |
| uv WITHOUT `--prerelease=allow` | refuses: "reflex-base was requested with a pre-release marker ... try --prerelease=allow" — pre-existing uv semantics, identical on every alpha (10-06 pymatrix_install, 10-07 reverify_db_install) | `logs/install-uv311-noflag.log` |
| N-001 original repro + F-005 fresh DB, all 4 db venvs: `greenlet_probe.py`, `reflex db init`, `makemigrations --message init`, `migrate`, `makemigrations --message noop` | every command rc 0, 0 error lines; `rx.Model` subclass created; 1 version file (the noop generated nothing); tables `alembic_version`, `note`; sqlmodel 0.0.48 (>= 0.0.45) | `logs/dbcli.txt`, `logs/db-<venv>-*.log` |
| F-006 `pip install reflex==0.10.0a5` (py3.12, no extra, no `--pre`) | rc 0; the full train: reflex/reflex-base 0.10.0a5, reflex-build-sdk 0.1.0a1, components code/core/gridjs/markdown/moment/plotly/radix/recharts 0.10.0a2, dataeditor/react-player/sonner 0.10.0a1, lucide 1.1.0a1, hosting-cli 0.2.0a1 (= the a4 set with reflex/reflex-base at a5) | `logs/n001.txt`, `logs/freeze-f006pip312.txt` |
| N-001 / F-005 end to end: the migrated dbcli app `--env prod` (3602) on the pip-3.14 and uv-3.11 venvs: add x2, reload | pass both: `note 1`, `note 2` rendered after reload, 2 rows in `reflex.db`; 0 tracebacks; only console error the favicon 404 of an app without assets (benign, = a3 preflight) | `logs/prod_crud.txt`, `logs/dbcli-prod-*.json` |
| F-014 `reflex component`, `component init/build/share`, `--help` forms | every form prints "`reflex component` was removed in Reflex 0.10. Wrap React components directly in your app (https://reflex.dev/docs/wrapping-react/overview/) and start reusable component packages from the component template: https://github.com/reflex-dev/component-template", rc 1 (`--help` forms rc 0); hidden from `reflex --help` (= a3/a4) | `logs/f014_component_a5.txt` |
| benign | `reflex.Model has been deprecated in version 0.9.2 ...` printed by `greenlet_probe.py` on a5, a4, a3 and 0.9.12 alike (pre-existing, documented deprecation) | `inst/run/probe_neutral` re-run |

## Part 3a — third-party grep for #7360 patterns + import sweep — `tp/`
Sources: the 37 wheels the a4 pass collected (`$SB/downloads/wheels/`, the a4_class_state downstream set incl. reflex-enterprise
0.9.7a4), the PyPI reflex-enterprise 0.9.7a5 wheel, `downloads/{reflex-local-auth,reflex-google-auth,reflex-magic-link-auth}` and
reflex-examples (ebe19ff). Unpacked under `$W/tp/grep7360/unz/` (scratch only).
- `tp/logs/grep_7360.txt` (pattern `router.headers|headers.cookie|headers["cookie"]|raw_headers|router_data|.router.session|router.url|router.page`):
  **every hit is server side** (`self.router...` / `instance.router...` / `state.router...` in handlers, on_load handlers, plugins).
- `tp/logs/grep_7360_frontend.txt` (any `State.router...` Var / `router.headers.cookie|raw_headers|[...]` outside `self.router`):
  **no frontend (component) use of `State.router.headers.cookie`, `headers["cookie"]` or `raw_headers` in any downstream package**; the only
  `.headers.cookie` read is enterprise `auth/cookie.py:225 instance.router.headers.cookie` (server side, by design unchanged by #7360).
- On_load handlers among the hits that read the router (the part #7360 changed — on_load events no longer carry router_data) and where
  each is exercised: enterprise page guards (`page_guard.py:163/216 login_url_for(str(state.router.url))`), OIDC callback
  (`oidc/state.py:2065` query params, `:1329/1342` `_redirect_uri`/`_index_uri`, `:1571` `redirect_to`), MCP consent (`consent_state.py:224`
  `txn`), `auth/replay.py:84`, audit `route` -> Part 1 suites + `vauthd`/`deeplink.py`; reflex-local-auth `login.py:59` (require_login
  redirect_to) and form-designer `form_entry.py:21` (client_token) -> local-auth flows + form-designer upgrade; reflex-magic-link-auth
  `page.py:16` (link query params) -> magic-link flows; github-stats `widget.py:18` (`page.params` appearance) -> seq_gh;
  **reflex-azure-auth 0.1.2** (`state.py:240` `auth_callback` on_load reads code/state from `router.url.query_parameters`, `:181`
  `redirect_to_login` stores `self.router.url`) -> `tp/az/` (pointed at the mock IdP); reflex-examples `azure_auth` (MSAL, `router.page.params`
  on its callback) needs real Azure — not run; recaptcha (`router.headers` x_forwarded_for in a click handler) — server side, not exercised.
- Import sweep (`tp/run/probes/import_sweep.py` on my `$SB/envs/a5_upgrade_ent-tp`, built by `tp/bin/build_venv.sh` = the a4 spec with
  `==0.10.0a5`): **22/22 identical to the a4 pass** (`tp/logs/import_sweep.cmp_a4_a5.txt`; the one "DIFF" is reflex-chakra's identical
  `_issubclass` ImportError differing only in the venv path in the message); reflex-chakra and community reflex-ag-grid fail as known,
  reflex-clerk imports with its 1 known warning. Matches the sibling a5_class_state (22 = a4, 112 enterprise modules import).

## Part 1 — reflex-enterprise 0.9.7a5 on reflex a5 (`$SB/envs/a5-ent`, `CI=true`), a4 back to back (`a4-ent`) — `ent/auth/`, `ent/grid/`
```bash
E=$W/ent/auth
$E/bin/seq_ent_auth.sh a5-ent a5e 123 > $E/logs/seq-ent-auth-a5e.txt   # parts: 1 vauth dev+Redis (vdrv stale/away/xtab x3, race, hunt loads/relogin x2)
                                                                        #        2 entauth dev+Redis (drive_auth_redis cycle,pubnav,twotab,xtab; xtab_probe x5; stale_hash_probe x3; hydration_token_probe)
                                                                        #        3 the 10-05 a4 auth matrix (dev, memory) + MCP OAuth + anonymous MCP
$E/bin/seq_n032_prod.sh a5-ent a5e > $E/logs/seq-n032-prod-a5e.txt      # vauth --env prod single port 8621, Redis, GRANIAN_WORKERS=1
$E/bin/seq_deeplink.sh a5-ent a5e > $E/logs/seq-deeplink-a5e.txt        # NEW #7360 probe: vauthd app + drivers/deeplink.py, dev+Redis x3, prod+Redis 1w x2
# the same three with a4-ent / a4e (back to back, same session); seq_deeplink.sh s912-ent-a5 s912e5 for 0.9.12
(mkdir -p $E/run/huntcmp/{drivers,logs}; cp $E/drivers/hunt_cmp.py $E/run/huntcmp/drivers/; cp $E/logs/a5e-dev-redis-hunt-*.json <a4 hunt jsons> $E/run/huntcmp/logs/;
 cd $E/run/huntcmp/drivers && $SB/envs/driver/bin/python -I hunt_cmp.py a4e-dev-redis a5e-dev-redis) > $E/logs/hunt_cmp_a4e_a5e.txt
```
Chains used: `ent/bin_chain1.sh` (a5 auth -> N-032 prod) then `ent/bin_chain1b.sh` (deeplink a5, deeplink a4, a4 auth, a4 N-032 prod, grid a5).

### 1a. The re-run suites: a5 == a4 (today, back to back) == the a4 pass
| suite (dev + Redis unless noted) | a5 + ent a5 | a4 + ent a5 (today) | a4 pass (16:04) |
|---|---|---|---|
| **N-032** `vdrv.py stale` P1 anon bogus hash -> "" / P2 signed-in re-asserts real hash / P3 cookies cleared + "" -> signed out / P4 control | **3/3, 3/3, 3/3, 3/3** | 3/3 x4 | 3/3 x4 |
| **N-032** `vdrv.py away` (logout in tab2, Back in tab1) | **3/3** | 3/3 | 3/3 |
| **N-032** `vdrv.py xtab` two-tab logout race | **3/3, 0 accepted-after-logout** (race 2/3, healed by tab2's reconcile) | 3/3, 0 (race 2/3) | 3/3, 0 (race 3/3) |
| **N-032 prod** (`--env prod` 8621, Redis, 1 worker): stale P1-P4 / away / xtab | **3/3 x4 / 3/3 / 3/3, 0 accepted** (race 1/3) | 3/3 x4 / 3/3 / 3/3, 0 (race 0/3) | same |
| `hunt.py loads` x2 / `relogin` x2 (event + storage-write counts per step) | identical per step to a4 (`logs/hunt_cmp_a4e_a5e.txt`: 1 `hydrate_and_load` per boot, `update_vars_internal` + `on_load_internal` on client nav, 0 idle events, 1 cookie sync, 1 hash write; relogin ok 2/2, 4 hash writes); prod 1w same | — | same |
| `drive_auth_redis.py` cycle, pubnav, twotab, xtab | **ALL_PASSED** | ALL_PASSED | ALL_PASSED |
| `xtab_probe.py` x5 | **TAB1_LOGGED_OUT 5/5** | 5/5 | 5/5 |
| `stale_hash_probe.py` x3 | **CORRECTED anon 3/3, loggedin 3/3, live 3/3** | same | same |
| `hydration_token_probe.py` SUMMARY | `{reload_writes: True, newtab_writes: True, garbage_protected: False, garbage_public: False, garbage_id_refresh: False, garbage_all_after_login: True}` | verbatim the same | verbatim the same |
| 10-05 auth matrix (dev, memory): full app / reload / auth_min default / iframe replay / extra scopes | **22/22, 3/3, 4/4, 3/3, 4/4 = 36/36** | 36/36 | 36/36 |
| MCP OAuth (discovery, registration, consent, PKCE, protected event, code replay, refresh rotation) + anonymous MCP (token endpoint = api_tokens `persist_router_data`, events, computed reads, redaction, isolation) | **pass / pass** | pass / pass | pass / pass |
| server logs | 0 Traceback, 0 TypeError; same warning signatures (Sitemap/Radix/`console.debug`/`ArrayVar.foreach` deprecations, granian shutdown lines) | same | same |
The full upstream matrix includes `test_full_login_flow_returns_to_requested_page`, `test_protected_page_redirects_anonymous_with_redirect_to`,
`test_blocked_event_replays_after_login`, `test_protected_vars_survive_client_side_navigation`, `test_logout_ends_session_and_reprotects`.

### 1c. N-025 AG Grid + demo route smoke (prod, `ent/grid/`, ports 3470-3479)
```bash
$W/ent/grid/bin/seq_grid.sh a5-ent a5 12 > $W/ent/grid/logs/seq-grid-a5.txt    # entv prod 3470, aggrid_min prod 3471, dnd/flow/mantine/map prod 3478
cd $W/ent/grid && $SB/envs/driver/bin/python -I drivers/summarize.py out entv_a5ent_prod > out/SUMMARY_a5.md; $SB/envs/driver/bin/python -I drivers/anomalies.py out/entv_a5ent_prod
```
- **N-025 still FIXED on a5:** entv s1-s13 table **byte-identical** to the a4 pass's (`diff` of SUMMARY_a4.md vs SUMMARY_a5.md rows s1-s13 empty):
  state / literal grids 2h/6c on full load, reload, after events, client nav, second context, dynamic route; `/memo` memo-prop and
  State-in-memo grids 2h/6c; `/detail` detail grids headers `Count, Value` for both; lambda renderer 3 badges. Boot = one `hydrate_and_load`
  in the socket.io connect auth; 0 page errors; console only the AG Grid trial banner + favicon 404. aggrid_min **4/4 PASS**.
- Demos (prod, a5): dnd **27/27** (0 console/page errors); flow **20/22** — the same two as the a4 pass (`index lists 6 flow demos`, a driver
  expectation; N-026 reload revert, known race); mantine **23/23** + 1 page error `Cannot read properties of null (reading 'name')` (= N-028,
  known, same as a4/a3); map **4/4** (54 OSM tile requests blocked by the sandbox, as before). 0 server tracebacks everywhere.
  Identical to the a4 pass's a4 column, so a4 was not re-run for the grid/demos.

## Part 2b — in-place upgrades (reflex-examples apps; the a3/a4 drivers and QA patches unchanged) — `up/`
```bash
$W/up/bin/build_base_venvs.sh                  # $SB/envs/a5_upgrade_ent-{fd,twr} = 'reflex==0.9.12' -r requirements.txt 'sqlalchemy<2.1'; -twa4 = --prerelease=allow 'reflex[db]==0.10.0a4' 'pydantic<2.14'
$W/up/bin/build_base_venvs.sh gh:github-stats:  # -gh = 'reflex==0.9.12' -r requirements.txt
$W/up/bin/seq_fd.sh   > $W/up/logs/seq-fd.txt    # form-designer (reflex[db] + reflex-local-auth) 0.9.12 -> a5: dev 3600/8600, prod 3600, cold
$W/up/bin/seq_twr.sh  > $W/up/logs/seq-twr.txt   # twitter prod + Redis 8609 (port 3612), 0.9.12 -> a5, + rollback to 0.9.12
$W/up/bin/seq_twa4.sh > $W/up/logs/seq-twa4.txt  # twitter prod + Redis 8609 (port 3614), a4 -> a5 (pydantic<2.14 kept, so only the train can move)
$W/up/bin/seq_gh.sh   > $W/up/logs/seq-gh.txt    # github-stats 0.9.12 -> a5 (+ GraphQL stub 8608): dev 3604/8604, prod, cold
```
Upgrade = `uv --no-config pip install --python <venv> --prerelease=allow -U 'reflex[db]==0.10.0a5'` in the same venv / app dir / `.web` /
`reflex.lock` / `reflex.db` / persistent Chromium profile (`up/bin/common.sh upgrade()`). (The `granian workers spawned (a4)` label in
seq-twr.txt is a leftover echo string; that run is a5.)
| app / run | a5 | a4 pass (same flow, a4) |
|---|---|---|
| form-designer 0.9.12 `full` / `entry` | 18/0/2 / 14/0/1 | 18/0/2 / 14/0/1 |
| form-designer a5 in place `up` / `entry` | **12/0/1 / 14/0/1**; protected editor rendered from the 0.9.12-written `_auth_token` without login; first load: 0 changing app writes (1 idempotent `_auth_token`) | 12/0/1 / 14/0/1 |
| form-designer a5 prod `up` / `entry`; routes | **12/0/1 / 15/0/0**; `/edit/form/1` `/form/1` `/responses/1` 200, `/nope` 404, `/login` 307 | same |
| form-designer a5 cold `up` | **12/0/1**; cold `.web/package.json` and file list == in-place | same |
| twitter prod+Redis 0.9.12 `base` / stale tab across stop -> upgrade -> a5 | 19/0/2 / **8/0/3** | 19/0/2 / 8/0/3 |
| twitter a5 prod `up` with the 0.9.12 tokens | **12/0/2: 0.9.12-pickled Redis sessions load on a5** (alice, bob logged in without re-login, rows intact) | 12/0/2 |
| twitter a5 prod `base` (new users) / rollback to 0.9.12 on the same Redis | **19/0/2 / 11/1/2** (the FAIL is the driver's "every session resets" expectation, as before) | 19/0/2 / 11/1/2 |
| twitter a4 -> a5 prod+Redis: a4 `base` / stale tab / a5 `up` with a4 tokens / a5 `base` | 19/0/2 / **8/0/3 / 12/0/2 (a4-pickled sessions load) / 19/0/2** | (a3 -> a4: 19/0/2, 8/0/3, 12/0/2, 19/0/2) |
| github-stats 0.9.12 `fresh` / a5 in place `persist` / a5 prod / a5 cold (widget page `/widget/Alice?appearance=dark`: its on_load reads `self.router.page.params`) | 14/0/2 / **12/0/2 / 13/0/1 / 14/0/2**; users + stats restored from 0.9.12-written LocalStorage; first load 0 changing writes; anomalies = the pre-existing widget dark-appearance (also 0.9.12) + React value-without-onChange | 14/0/2 / 12/0/2 / 13/0/1 / 14/0/2 |
| a4 -> a5 freeze diff | **only reflex + reflex-base 0.10.0a4 -> 0.10.0a5** (`up/freeze/twa4-base-to-up.diff`); `.web/package.json` after the first a5 run IDENTICAL to a4's (empty `up/pkg/twa4-base-to-up.package.diff`); `reflex.lock/package.json == .web/package.json` | (a3 -> a4 same) |
| 0.9.12 -> a5 freeze / package.json diffs | identical to the a4 pass's with reflex/reflex-base at a5 (35 lines; `up/pkg/*-base-to-up.package.diff` byte-identical for fd and twr) | |
Server logs: the same signatures as the a4 pass (form-designer's pydantic serializer UserWarning from the app's model, vite console relays;
granian's 9-workers-on-4-CPUs warning; `Warning: Frontend version 0.9.12 / 0.10.0a4 for session ... does not match the backend version
0.10.0a5` (F-019 style, log only) when the stale tab reconnects); 0 tracebacks, 0 TypeError. 0.9.12 dev shutdown leaves the node process on
the frontend port (known, fixed since a1); a5 exits 2-3 s after SIGTERM with all ports free.

## Part 3b — third-party auth flows on a5 (`tp/`; drivers from the a3 sweep unchanged; fresh app copy + fresh db per run)
```bash
$W/tp/bin/build_venv.sh                                                 # $SB/envs/a5_upgrade_ent-tp: a5 + the 22 packages (freeze tp/logs/a5-tp-freeze.txt)
$W/tp/bin/seq_tp.sh a5_upgrade_ent-tp a5 > $W/tp/logs/seq-tp-a5.txt     # la dev 3463/8463, la prod 8467, la prod+Redis 8469, ml dev, ml prod (ML_FORCE_DEV=1)
$W/tp/bin/run_google.sh a5_upgrade_ent-tp a5 > $W/tp/logs/run-google-a5.txt
# vs the a4 pass: tp/bin/cmp_checks.py <a4 report> <a5 report>; tp/bin/compare_console.py ... -> tp/logs/cmp_a4_a5_tp.txt
```
| flow | a5 | a4 pass | a3 sweep |
|---|---|---|---|
| reflex-local-auth demo dev / prod / prod+Redis (38 checks incl. login with `redirect_to`, `require_login` on_load redirect — `login.py:59` reads `self.router.url.path` —, protected on_load, second tab shares login, logout in one tab, short session expiry) | **36/38 each** (the known `_validate_fields` pair); Redis 24 keys | 36/38 each | 36/38 each — 0 differing checks vs both, 0 console diffs |
| reflex-magic-link-auth dev / prod (11 checks: link login — `page.py:16` on_load reads the link's query params —, cross-tab login/logout via `LocalStorage(sync=True)`, OTP reuse, rate limit) | **10/11 each** (known `/check-your-email` bounce) | 10/11 each | 10/11 — 0 differing |
| reflex-google-auth dev (13 checks: bogus token cleared, `/protected` not unlocked) | **12/13** (driver's "key discoverable" check) | 12/13 | 12/13 — 0 differing, same 11 anomaly signatures (Google endpoints blocked) |
0 tracebacks / 0 TypeError in every server log. One benign extra on a5 la dev: a dev-server vite module request
(`/app/routes/_index.jsx?import`) `net::ERR_ABORTED` during the logout navigation (failedreq=1; a4 pass 0) — a lazy route module fetch
cancelled by the navigation, dev only, not related to the a5 changes.

### 1d. Token expiry / proactive refresh / revocation on a5 (entauth, dev + Redis; `ent/auth/scripts/expiry_matrix.sh`)
```bash
$W/ent/auth/bin/infra.sh start; $W/ent/auth/scripts/expiry_matrix.sh a5-ent entauth_a5e a5e proactive expire_norefresh expire_closed_tab revoke; $W/ent/auth/bin/infra.sh stop
```
(the matrix restarts the mock IdP with each scenario's token lifetime, then the app; results `ent/auth/logs/expiry-a5e-<scenario>.json`,
IdP logs `mock-oidc-a5e-<scenario>.log`, server logs `entauth-dev-redis-a5e-expiry-<scenario>.log`)
| scenario | a5 | earlier passes (a2 10-07 / a3) |
|---|---|---|
| proactive: 75 s tokens + refresh token, idle 120 s | refreshed in the background (IdP: 2 token + 2 userinfo requests), still Alice at every 10 s sample, protected `reveal` allowed after 120 s, reload stays on /dashboard, 4 token cookies | same (a3: refreshed at +69 s, still Alice) |
| expire_norefresh: 30 s token, no refresh token, idle 40 s | still logged in, protected event ALLOWED (pre-existing enterprise behaviour: not re-validated until the userinfo cache lapses) | identical (a2 and 0.9.12) |
| expire_closed_tab: 40 s tokens, tab closed 50 s, new tab -> /dashboard | logged in (the new tab's cookie sync refreshed: 3 token requests) | same |
| revoke: IdP `revoke-tokens` (204) | protected event still allowed, reload still logged in; `force_refresh` -> refresh 400 `invalid refresh token` (ERROR + traceback in the server log, known) -> reload -> **`/login?redirect_to=%2Fdashboard`** (the on_load guard built the redirect from the right page) | same (a2: "stays on /dashboard until the next reload -> /login") |
0 page errors; failed requests only the pico.css tunnel error and cookie-sync keepalive aborts (benign).

### 1b. NEW #7360 probe: deep links, client nav, logout, router view, credential exposure (`vauthd` + `drivers/deeplink.py`)
App `ent/auth/src/vauthd` (vauth + an audit hook): `/` public (renders the deprecated `rx.State.router.headers.cookie`, the frontend
`raw_headers` keys and a click probe), protected `/vault`, `/vault2`, `/item/[item]` with an `on_load` (`Diag.on_page_load`) that records
what `self.router` shows server side (url, path, query, page.params, page.host, session client_token / session_id, the cookie NAMES in
`router.headers.cookie`, raw cookie header present). `AuthPlugin(audit="vauthd.audit.audit_auth")` writes every auth decision to
`logs/<label>.audit.jsonl`; its `page_load` record carries `route = str(state.router.url)` as the page guard (an on_load event, which a5 no
longer stamps with router_data) saw it; `drivers/audit_routes.py` summarizes. Scenarios per rep (fresh context each):
A anonymous full load `/vault?x=1&y=two%20words` -> `/login?redirect_to=...` -> mock IdP -> back on the same URL, on_load sees the query,
protected event attributed to alice@/vault; B the same for the dynamic route `/item/abc?z=9`; C anonymous CLIENT-SIDE link `/` ->
`/vault?x=nav` (redirect_to must be `/vault?x=nav`, not `/`); D signed in client nav `/` -> `/vault2?q=5&r=a%20b` -> `/item/xyz?k=1` ->
`/vault?x=nav`, each on_load must see its own page; E reload of `/item/xyz?k=1`; F logout from `/vault` (cookies cleared, revisit ->
`/login?redirect_to=/vault`); G no cookie/credential header key or cookie value inside `rx_router_headers` in any received websocket frame.
| run | A deep link | B dynamic | C anon client nav | D signed-in nav | E reload | F logout | G no router-header credential | audit page_load routes |
|---|---|---|---|---|---|---|---|---|
| **a5 dev+Redis x3** | **3/3** | **3/3** | **3/3** | **3/3** | **3/3** | **3/3** | **3/3** | all on the right page (0 stale) |
| **a5 prod+Redis 1w x2** | **2/2** | **2/2** | **2/2** | **2/2** | **2/2** | **2/2** | **2/2** | same |
| a4 dev+Redis x3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | **0/3** (leaks, = what #7360 fixed) | identical counts to a5 |
| a4 prod+Redis 1w x2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | **0/2** | identical counts to a5 |
| 0.9.12 + ent a5 dev+Redis x3 (`s912e5`) | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | **0/3** (same router-header leak: pre-existing since 0.9.12) | identical counts |
Details (`logs/<label>-deeplink.json`, `logs/seq-deeplink-<label>.txt`, `logs/deeplink_leak_summary.txt`):
- The on_load router view is complete on a5: `str(router.url)` = `http://localhost:3620/vault?x=1&y=two%20words`, `url.query_parameters`
  decoded, `page.params` (= route args + query, long-standing), `page.host` = the origin, `session.client_token` / `session_id` present, on
  first load, after login, on every client nav and on reload; the audit `page_load` routes (108 records dev, 72 prod) are the same on a4 and
  a5 to the count. `redirect_to` keeps the query (`%2Fvault%3Fx%3D1%26y%3Dtwo%2520words`); prod redirects `/vault` -> `/vault/` (static
  serving 307, same on a4), so prod returns to `/vault/?x=1&y=two%20words`.
- Logout (`AuthUserState.logout`) from `/vault` goes to the IdP's `end_session` (RP-initiated logout with `id_token_hint`), token cookies
  cleared, `/vault` afterwards -> `/login?redirect_to=%2Fvault`. Same on a4.
- **#7360's security claim holds from the enterprise angle.** On a4 the `rx_router_headers` delta carries `cookie` (30 frames dev / 20 prod)
  and, after a reload (the websocket handshake then carries the token cookies), the VALUES of the **HttpOnly** `_oidc_generic_id_token_partitioned`
  and `_oidc_generic_refresh_token_partitioned` cookies (9 / 6 frames) — i.e. enterprise's HttpOnly OIDC tokens were readable by page JS via
  the router state on a4. On a5: 0 such frames; the frontend `raw_headers` keys omit `cookie`; `State.router.headers.cookie` renders "".
  Server side the cookie header is still there on a5 (`router.headers.cookie` lists the `_oidc_*` names after a reload, raw cookie header
  present) — enterprise `auth/cookie.py:225` keeps working. (The server-side Cookie header is the websocket HANDSHAKE's, so cookies set
  after the socket connected — the token cookies, set by `/_reflex/cookies/sync` after the code exchange — appear there only after a
  reconnect/reload; same on a4, by design.)
- Frames with a cookie value OUTSIDE the router headers are identical on a4 and a5 and by enterprise design: the
  `granted_scopes` state var (its value equals the granted-scopes cookie, i.e. the scope string) and the IdP logout redirect's `id_token_hint`.
- Compile-time: `State.router.headers.cookie` in a component prints `DeprecationWarning: State.router.headers.cookie has been deprecated in
  version 0.9.13 ... Use rx.Cookie ... (vauthd/vauthd.py:122)` — points at the user's line (the 0.9.13 version string inside a 0.10 alpha is
  already noted by the orchestrator's preflight).
- Driver history (mine, fixed): attempt 1 used `time.sleep` in a sync-Playwright poll loop, which starves the event dispatch (`page.url`
  never updates) -> every wait timed out (`logs/attempt1/`); attempt 2 expected `page.params` without the query keys, compared prod paths
  without the trailing slash and counted by-design frames as leaks (`logs/attempt2/`). The final driver ran the a5 runs and the a4 prod run; the a4 dev run used it minus the trailing-slash normalization (irrelevant in dev).

### 3c. reflex-azure-auth 0.1.2 pointed at the mock IdP (`tp/az/`) — a downstream package whose on_load handlers read the router
`AzureAuthState.auth_callback` (on_load of `/authorization-code/callback`) reads `code`/`state` from `self.router.url.query_parameters`
and builds `redirect_uri` from `self.router.url`; `redirect_to_login` stores `self._redirect_to_url = self.router.url`. App
`tp/az/src/azapp`: `/protected` has an on_load `Guard.check` that returns `AzureAuthState.redirect_to_login` (a backend chain from an
on_load event — exactly what #7360 changed). Generic OIDC, so `AZURE_ISSUER_URI=http://localhost:8638` works.
```bash
$W/tp/az/bin/build_venvs.sh                                   # $SB/envs/a5_upgrade_ent-az (a5) / -az4 (a4): reflex+base pinned, pydantic<2.14, reflex-azure-auth==0.1.2, the offline ent wheel
$W/tp/az/bin/run_az.sh a5_upgrade_ent-az a5 dev,prod > $W/tp/az/logs/run-az-a5.txt     # dev 3463/8463, prod 8467; mock IdP 8638 via ent/auth/bin/infra.sh
$W/tp/az/bin/run_az.sh a5_upgrade_ent-az4 a4 dev,prod > $W/tp/az/logs/run-az-a4.txt
```
| check (`tp/az/drivers/drive_az.py`) | a5 dev / prod | a4 dev / prod |
|---|---|---|
| A anonymous deep link `/protected?x=1&y=two` -> on_load chain -> IdP -> callback on_load exchanges the code -> back on `/protected?x=1&y=two` with a token (`redirect_uri` = `http://localhost:<port>/authorization-code/callback`) | **pass / pass** (prod: `/protected/?x=1&y=two`, static-serving slash) | pass / pass |
| B login button on `/` -> back on `/` | **pass / pass** | pass / pass |
| C signed-in client nav `/` -> `/protected?x=nav`: on_load sees `/protected?x=nav`, no redirect | **pass / pass** | pass / pass |
Console: only the mock IdP's pico.css tunnel failure and its 404 (both versions); 0 tracebacks; `authlib.jose` deprecation from the package.
(Attempt 1 of this driver had the same `time.sleep` event-starvation bug as deeplink.py: `tp/az/logs/attempt1/`.)

## Observations (not issues)
- O-1 The enterprise token cookies are set by `/_reflex/cookies/sync` AFTER the websocket connected, so the server-side
  `router.headers.cookie` of that connection (the handshake's Cookie header) lacks them until the next reconnect / reload — on a5, a4 and
  0.9.12 alike; enterprise reads them through its own cache first (`auth/cookie.py`). Not a #7360 effect.
- O-2 `RouterData.page` (used by `page.params` / `page.host`) logs its 0.8.1 deprecation; `page.params` = route args + query params on every
  version tested.
- O-3 The `State.router.headers.cookie` deprecation names `deprecation_version 0.9.13` inside the 0.10 alpha (already in the preflight notes).
- O-4 Prod static serving redirects `/vault` -> `/vault/` (307), so enterprise's `redirect_to` and the post-login return carry the trailing
  slash in prod (`/vault/?x=1&y=two%20words`) — same on a4.
- O-5 local-auth dev on a5 had one extra benign `net::ERR_ABORTED` for a vite route module during the logout navigation (dev only).
- Known, not re-reported: A3-09 / A3-10, N-026 (flow reload race), N-028 (`window.onerror` null), F-019 (log-only version warning),
  granian's 9-workers warning, favicon / bg.svg 404s, AG Grid trial banners, mock-IdP pico.css tunnel error, cookie-sync keepalive aborts,
  the enterprise expiry behaviours (expired token without refresh keeps authorizing until the userinfo cache lapses; refresh-400 traceback),
  uv needing `--prerelease=allow` for an alpha pin, the `reflex.Model` 0.9.2 deprecation line.

## Harness slips (mine, fixed)
- `deeplink.py` / `drive_az.py` attempt 1 polled with `time.sleep` inside sync Playwright (no event dispatch -> `page.url` frozen): every
  wait timed out. Fixed with `page.wait_for_timeout` pumping; attempt logs kept under `ent/auth/logs/attempt1|2/`, `tp/az/logs/attempt1/`.
- `deeplink.py` attempt 2: wrong `page.params` expectation (it includes the query), prod trailing slash, by-design frames counted as leaks.
- First `n001.sh` uv venvs ran without `--prerelease=allow` (uv refuses; pre-existing uv semantics) -> rerun with the flag.
- A `pkill -f`-style kill in my own shell matched its own command line (exit 144); re-done by explicit PIDs; no other agent's process touched.

## Cleanup
Every server, Redis (8609, 8629, 8469), mock IdP (8638), GraphQL stub (8608) and Chromium I started was stopped; final check: no listener on
3600-3639, 8600-8639, 3460-3479, 8460-8479 and no process under `$SB/apps/a5_upgrade_ent`. Deleted every app `.web/` (incl. node_modules),
the Chromium profiles and the N-001 venvs. Venvs left (scratch): `$SB/envs/a5_upgrade_ent-{fd,gh,twr,twa4,tp,az,az4}`.

## Not covered
- Enterprise prod with the default 9 workers (N-033 territory) and the entauth prod suite; the expiry `restart_provider` scenario (known
  JWKS caching) and the expiry matrix on a4 (a5 matched the a2/a3 results).
- AG Grid demo app (ag_grid + QA pages); N-025 re-checked on the entv fixture + aggrid_min as in the a4 pass.
- reflex-examples `azure_auth` (MSAL, needs real Azure) and reflex-google-recaptcha-v2's `router.headers` read (server side, needs Google).
- Python 3.12/3.13 fresh installs for N-001 (3.11 and 3.14 per the brief; the shared a5 venvs are 3.12).
