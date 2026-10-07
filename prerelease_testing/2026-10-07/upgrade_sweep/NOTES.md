# Cluster `upgrade_sweep`: 0.9.12 -> 0.10.0a2 in-place upgrade sweep + stock-install smoke (2026-10-07)

Host: 4-CPU Linux container shared with 3 other agents; Python 3.12.3, Node 22.22, bun 1.4.2, uv 0.11.32, Playwright 1.63 /
Chromium. Every framework install came from PyPI into isolated venvs `$SB/envs/upgrade_sweep-*` (uv, `--no-config`, cwd=`$SB`);
nothing was installed from or run inside `/home/user/reflex` or `/home/user/reflex-enterprise`. Servers ran one at a time on the reserved
ports 3140-3159 / 8140-8159 (redis 8159, GitHub GraphQL stub 8158).
`SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad`, `W=$SB/apps/upgrade_sweep`.
Apps: the 10-06 copies in `prerelease_testing/2026-10-06/upgrades_a/{form-designer,github-stats,clock}` and `upgrades_b/twitter`
(reflex-examples `ebe19ff`, with the two env-var-gated QA patches in `patches/`).

## Verdict

**No upgrade regression in form-designer, github-stats, clock or twitter.** Each was driven in Chromium on a fresh `reflex==0.9.12`
venv, upgraded in place with `uv pip install --prerelease=allow -U 'reflex==0.10.0a2' 'pydantic<2.14'` (same venv, same app dir with
`.web/`, `reflex.lock/`, `.states/`, `reflex.db`, same persistent browser profile), re-driven with the identical flows, then re-driven
after `rm -rf .web` (cold). Every check that passes on 0.9.12 passes on a2 (in place and cold, dev and prod where run); the
error/warning console signatures are identical to 0.9.12 and to the saved 0.10.0a1 results of 10-06
(`logs/compare_a1_a2.txt`); no page errors and no failed/4xx/5xx requests beyond the app-level ones that 0.9.12 has too.
Client storage written under 0.9.12 (LocalStorage `_auth_token`, github-stats JSON, the `rx.Cookie` zone) is restored after the upgrade and
**nothing is newly written on first load** (probe below, validated with a positive control that does catch the 0.10.0a1 bug).

Findings worth acting on (none is a regression of the 0.10.0a2 code against 0.9.12):
1. (HIGH, environment drift, hits 0.9.12 and 0.10.0a2 alike) a FRESH `reflex[db]` install now resolves SQLAlchemy 2.1.3, which does not
   depend on `greenlet`, so `import reflex.model` and therefore `reflex run` / `reflex db *` of every db app die with
   `ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed`.
2. (LOW, unchanged) `reflex component ...` fails with "No such command 'component'. Did you mean 'compile'?" and no migration pointer (F-014).
3. (LOW, unchanged) a stale prod tab left open across the upgrade gets no user-visible signal, only a server-side warning (F-019).

Re-verified from the 10-06 findings: F-002 FIXED, F-003 FIXED (deterministic now), F-005 FIXED (cap lifted, UTCDateTime migration works), F-006 FIXED
(`pip install -U 'reflex==0.10.0a2'` without `--pre` now pulls every component), F-014 unchanged, F-019 unchanged.

## Rerun instructions

```bash
export SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; export W=$SB/apps/upgrade_sweep   # set SB first: W=$SB/... in the same export line expands to a wrong path
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
# apps (copies of the 10-06 artifacts; patches/ are the opt-in QA patches already applied in those copies)
# per-app venv, baseline resolved like a stable user (NO prerelease flag); db apps additionally need `sqlalchemy<2.1` (finding 1)
cd $SB && uv --no-config venv --python 3.12 $SB/envs/upgrade_sweep-<app>
cd $SB && uv --no-config pip install --python $SB/envs/upgrade_sweep-<app>/bin/python -r $W/<app>/requirements.txt 'reflex==0.9.12' ['sqlalchemy<2.1']
# run helpers: bin/run_app.sh <appdir> <venv> <fp> <bp> <log> [reflex run args]   bin/stop_app.sh <appdir> <ports...>   (never pipe stop_app.sh into head: SIGPIPE aborts the cleanup)
$W/bin/run_app.sh $W/form-designer $SB/envs/upgrade_sweep-form-designer 3140 8140 $W/logs/fd-base-run1.server.log
$DRV $W/scripts/drive_form_designer.py http://localhost:3140/ $W/shots/fd fd-base-full full $W/profiles/fd 0.9.12
$W/bin/stop_app.sh $W/form-designer 3140 8140
FD_FIX_FIELD_NAME=1 $W/bin/run_app.sh ... ; $DRV $W/scripts/drive_form_designer.py ... fd-base-entry entry $W/profiles/fd 0.9.12
# pre-upgrade snapshot of the persistent profile + probe, in-place upgrade, first post-upgrade load, identical flows, cold
$DRV $W/scripts/storage_probe.py http://localhost:3140 $W/shots/fd fd-base-persist-editor $W/profiles/fd --path /edit/form/ --wait 6 --expect-text "Existing Forms" --forbid-writes
cd $SB && uv --no-config pip install --python $SB/envs/upgrade_sweep-form-designer/bin/python --prerelease=allow -U 'reflex==0.10.0a2' 'pydantic<2.14'
FD_FIX_FIELD_NAME=1 $W/bin/run_app.sh ... fd-up-run1.server.log     # first post-upgrade run: lockfile restore + bun add
$DRV $W/scripts/storage_probe.py ... fd-up-firstload-editor $W/profiles/fd --path /edit/form/ --keep _auth_token=<value from the base snapshot> --forbid-writes
$DRV $W/scripts/drive_form_designer.py ... fd-up-up up $W/profiles/fd 0.10.0a2 ; ... fd-up-entry entry ...
rm -rf $W/form-designer/.web ; run again ; drive again   # cold
# prod: REFLEX_API_URL=http://localhost:3140 $W/bin/run_app.sh <app> <venv> 3140 3140 <log> --env prod
```
Per app ports: form-designer 3140/8140 (prod 3140), github-stats 3144/8144 (needs `$SB/envs/driver/bin/python $W/scripts/github_stub.py 8158` and
`QA_GITHUB_GRAPHQL_URL=http://127.0.0.1:8158/graphql GITHUB_API_TOKEN=qa-dummy-token` in the server env; drivers `drive_github_stats.py <url> <out> <tag> fresh|persist <profile> http://127.0.0.1:8158`),
clock 3146/8146 (`drive_clock.py <url> <out> <tag>`, `clock_session.py <url> <out> <tag> <ctldir>` = one browser context across stop/upgrade/restart,
operator touches `<ctldir>/down` and `<ctldir>/up`), twitter 3150/8150 (`reflex db migrate` first; `drive_twitter.py <url> <out> <tag> base|up <tokfile>`, `QA_EXPECT_SESSION=0` for the disk state manager),
twitter + Redis prod: `redis-server --port 8159 --save '' --appendonly no`, venv `upgrade_sweep-twredis`, app copy `twitter-redis`,
`REFLEX_REDIS_URL=redis://localhost:8159 REFLEX_API_URL=http://localhost:3152` + `--env prod` on 3152, `stale_tab_twitter.py <url> <out> <tag> <ctldir>`
(env `QA_EXPECT_SESSION=1 QA_STALE_USER=daver QA_STALE_FOLLOW=alicer`). Other ports: f1combo F-002 control and cvstore F-003 3156 / 3158, dtapp 3144, SQLAlchemy-2.1 variants 3142, smoke 3157.

Drivers (`scripts/`, run with `$SB/envs/driver/bin/python`; `NO_PROXY` on the driver only, never in the server env): the 10-06 drivers
(`drive_*`, `stale_tab_*`, `harness.py`, `compare_runs.py`) plus the new `storage_probe.py` (init-script that logs every localStorage /
sessionStorage / cookie write before app JS runs, snapshot at document start, `--keep`, `--forbid-writes`), `clock_session.py`,
`compare_sets.py` (label=json comparison of runs from different campaigns), `dbdump.py`, `f3_table.py`, `run_f3.sh`, `sync_dest.sh`.

## Resolution and upgrade mechanics (`freeze/`, `pkg/`)

Baselines are what a stable user gets (`freeze/<app>-base.txt`): reflex/reflex-base 0.9.12, components code 0.9.6, core 0.9.10.post1,
gridjs 0.9.2.post1, markdown 0.9.4.post1, moment 0.9.4, plotly 0.9.7, radix 0.9.10.post1, recharts 0.9.4.post1, sonner 0.9.4,
dataeditor 0.9.3.post1, lucide 1.0.4, react-player 0.9.2, hosting-cli 0.1.72, wrapt 2.3.0 (db apps: sqlmodel 0.0.48, alembic 1.20.0,
reflex-local-auth 0.5.0; clock pytz 2022.7.1). For the db apps the baseline needed `sqlalchemy<2.1` (finding 1); a plain resolve gave
SQLAlchemy 2.1.3 without greenlet and the app could not even start (`freeze/*-fresh-resolution-sa2.1.3.txt`,
`logs/fd-base-run1-greenlet-importerror.server.log`).

`uv pip install --prerelease=allow -U 'reflex==0.10.0a2' 'pydantic<2.14'` (identical diff for all apps, `freeze/*-base-to-up.diff`):
reflex/reflex-base 0.10.0a2, reflex-build-sdk 0.1.0a1 (new), components code/core/gridjs/markdown/moment/plotly/radix/recharts 0.10.0a2,
**dataeditor 0.10.0a1, lucide 1.1.0a1, react-player 0.10.0a1, sonner 0.10.0a1 (these four did not move on a1)**, hosting-cli 0.2.0a1,
wrapt 2.5.0. So every component package now moves (#7464). (pydantic/annotated-types/typing-inspection show up as added only in the apps
that had no pydantic: they come from the explicit `'pydantic<2.14'` in the command; the stock a2 install has no pydantic at all.)
`uv pip check` is clean. SQLAlchemy stays 2.0.54 / sqlmodel 0.0.48 when `reflex[db]` is not re-requested.

`.web/package.json` after the upgrade (`pkg/<app>-base-to-up.package.diff`) is the same for every app: react/react-dom 19.2.8->19.3.0,
react-error-boundary 6.1.2->6.1.6, socket.io-client 4.8.3->4.8.4, autoprefixer 10.5.4->10.6.1, postcss 8.5.26->8.5.29, vite 8.2.2->8.3.2,
and moment 2.30.1->2.31.0 (form-designer). The a2 `package.json` is **byte-identical to the 10-06 a1 one** (`diff` of
`upgrades_a/pkg/form-designer-up.web.package.json` against `pkg/form-designer-up.web.package.json` is empty), nothing pruned, `mergician` still
`"v2.0.2"`. After every run `reflex.lock/package.json` == `.web/package.json`; the cold `.web` has the identical package.json and the identical
file set (`pkg/*-up.web.files` vs `*-cold.web.files`).

First post-upgrade run (`logs/fd-up-run1.server.log`): "Restoring lockfiles" -> `bun install --frozen-lockfile` reinstalls the 0.9.12 graph ->
two `bun add` calls move to the new pins -> "Saved lockfile"; no warnings, no npmmirror fallback; "UP" in 4-10 s with a warm bun cache. The startup
section of the a1 and a2 first-run logs is line-for-line identical apart from versions and set-iteration order (`diff` in the transcript).
Shutdown (SIGTERM, no TTY): a2 "Reflex app stopped" in 2-3 s every time with all ports free; 0.9.12 dev never exits in 15 s and leaves the
`react-router dev` node process on the frontend port (every baseline stop; #7328 is a positive change, as on a1).

## Per-app results (`shots/<app>/<tag>.json`; pass/fail/anomaly)

| app | 0.9.12 | a2 in place | a2 cold | a2 prod | 10-06 a1 (in place) |
|---|---|---|---|---|---|
| form-designer `full`/`up` | 16/0/4 `fd-base-full` | 12/0/1 `fd-up-up` | 12/0/1 `fd-cold-up` | 12/0/1 `fd-up-prod-up` | 10/0/2 |
| form-designer `entry` (FD_FIX_FIELD_NAME=1) | 14/0/1 `fd-base-entry` | 14/0/1 `fd-up-entry` | 14/0/1 `fd-cold-entry` | 15/0/0 `fd-up-prod-entry` | 14/0/1, prod 15/0/0 |
| github-stats `fresh` / `persist` | 14/0/2 `gh-base`; persist control 11/1*/2 `gh-base-persist` | 12/0/2 `gh-up` | 12/0/2 `gh-cold` | 13/0/1 `gh-up-prod` | 12/0/2, prod 13/0/1 |
| clock | 17/0/0 `ck-base` | 17/0/0 `ck-up` | 17/0/0 `ck-cold` | - | 17/0/0 |
| clock one-context stop/upgrade/restart | control 0.9.12->0.9.12 10/0/1 `ck-session-control0912` | 10/0/1 `ck-session-up-a2` | - | - | 8/0/1 (no new-tab step) |
| twitter dev (disk state) | `base` 21/0/0 `tw-base`; restart control `up` 14/0/0 `tw-ctl0912-up` | `up` 14/0/0 `tw-up` | `up` 14/0/0 `tw-cold`, `base` 21/0/0 `tw-cold-base` | - | 14/0/0, cold 14/0/0 + 21/0/0 |
| twitter prod + Redis | `base` 19/0/2 `twr-base-prod`; restart control `up` 12/0/2 `twr-base-restart` | tokens `up` 12/0/2 `twr-up-prod`, stale tab 8/0/3 `twr-stale-prod`, `base` 19/0/2 `twr-up-prod-base` | - | (is prod) | 12/0/2, 8/0/3, 19/0/2 |

Differences are explained, none is an a2 regression (`logs/compare_a1_a2.txt`): the a1 `fd-*-up` runs were done without FD_FIX_FIELD_NAME
(the FormMessage crash, an app bug on every version) and with an earlier driver version that lacked the `re-login: auto-redirects` check, which
is an anomaly on 0.9.12 too (the 10-07 0.9.12 baseline `fd-base-full` has it: login never leaves `/login`, app bug); *`gh-base-persist` has
one FAIL, "widget reload within 60s served from LocalStorage cache", a driver timing race (the fetch lands after the counter sample), which
passes on a1 and a2, so 0.9.12 is the only version that tripped it this time.

DB state across the upgrade (`logs/fd-db-base.txt` vs `fd-db-up.txt`, `tw-db-base.txt`/`tw-db-up.txt`): alembic head unchanged (`4c92535dbbbd`,
`79336c1da3d1`), every 0.9.12 row digest unchanged (users, session, forms, fields, options, follows, tweets), new rows added after the upgrade.
`reflex db migrate` and `reflex db makemigrations --message qa_probe` after the upgrade: rc 0, no new migration file.
Redis (twitter prod): the `State.user` SQLModel row pickled by 0.9.12 is unpickled by a2; sessions survive 0.9.12 -> a2 exactly like 0.9.12 -> 0.9.12.
With the disk state manager (dev) users are logged out after any restart (`reflex run` wipes `.states`, identical on 0.9.12: control `tw-ctl0912-up`).
Prod dynamic routes of form-designer answer 200 (`/edit/form/1`, `/form/1`, `/responses/1`), `/nope` 404, `/login` 307.

## Item 2: client-storage restoration and no first-load write-back (#7460)

Tool: `scripts/storage_probe.py` installs an init script before any app JS runs (snapshot of localStorage / sessionStorage / `document.cookie`
at document start; wrappers around `Storage.setItem/removeItem/clear` and the `document.cookie` setter), records the websocket frames, and
reports every write; framework keys (`token`, `theme`, `last_compiled_theme`, `debug`) are ignored in the verdict.
* **Positive control** (without it "no writes" would prove nothing): the 10-06 F-002 repro app `f1combo` (storage vars next to a
  `default_factory`, a `set[str]`, a clock-dependent var, a substate) under the same probe, fresh profile, `logs/f1combo-*`, `shots/f1/`:
  | version | dev | prod |
  |---|---|---|
  | 0.9.12 (`$SB/envs/stable`) | 0 app writes | 0 |
  | 0.10.0a1 (`upgrade_sweep-a1`) | 9 writes (`cu_ck cu_ls cu_ss ws_ls wt_ls wu_ck wu_ls wu_ss wu_sync`) | 8 writes |
  | 0.10.0a2 (`$SB/envs/alpha2`) | **0** | **0** |
  F-002 is fixed in both modes.
* form-designer (LocalStorage `_auth_token` + `rx.Cookie("")`), persistent profile written by 0.9.12: first alpha2 load of `/edit/form/` renders the protected
  editor without logging in, `_auth_token` byte-identical at the end, **0 app writes** (`fd-up-firstload-editor`, prod `fd-up-prod-firstload-editor`); the 0.9.12 snapshot
  (`fd-base-persist-editor`) shows one idempotent `setItem _auth_token` rewrite that a2 no longer does. Fresh profiles on `/`, `/login`, `/form/1`,
  `/responses/1`: 0 app writes (`fd-up-fresh*`).
* github-stats (LocalStorage JSON), profile written by 0.9.12: users + stats restored with no refetch, `selected_users_json` unchanged, 0 changing writes
  (`gh-up-firstload-home`, prod `gh-up-prod-firstload-home`); the `hydrate_and_load` connect frame carries the 0.9.12-written values. Fresh profile: one write,
  `user_stats_json='[]'`, identical on 0.9.12 (`gh-base-fresh-home`) and a2 (`gh-up-fresh`): it is the app's own `on_load`.
* clock (`rx.Cookie` zone, session cookie so the browser context must stay open): `clock_session.py` sets Europe/Paris on 0.9.12, stops the server, upgrades
  the venv, starts a2; a NEW TAB opened in the same context right after the upgrade shows Europe/Paris, writes nothing; the old tab then drives the
  new backend (zone -> Asia/Tokyo, switch/bg task) and the cookie survives a reload. The 0.9.12 -> 0.9.12 restart control shows the same, plus three
  idempotent cookie rewrites that a2 does not do. Fresh profile: 0 app writes on 0.9.12, a1 and a2 (`ck-*-fresh-home`): the real clock app does not hit the
  F-002 trigger, only the control app does.

### F-003 (computed var / on_load rewriting client storage during hydration, #7460), 10-06 `cvstore` app (`f3/cvstore-*`, `scripts/run_f3.sh`, `scripts/drive_cvstore.py`, `shots/f3/`, `logs/f3_table_all.txt`)
Each variant puts `'bad'` into its storage slot, reloads, and records the browser storage after reload / probe click / reload 2 (versions were confirmed from the server logs:
`logs/f3-*.server.log`, "Reflex <version>"). Storage value after the first reload:
| variant | 0.9.12 seed 4 | 0.9.12 seed 0 | 0.10.0a1 seed 4 | **0.10.0a2 seed 4** | **0.10.0a2 seed 0** |
|---|---|---|---|---|---|
| a cached computed var clears LocalStorage | `''` | `'bad'` | `'bad'` | **`''`** | **`''`** |
| b uncached computed var clears LocalStorage | `''` | `'bad'` | `'bad'` | **`''`** | **`''`** |
| e_cookie / e_session cached cv clears Cookie / SessionStorage | `''` | `'bad'` | `'bad'` | **`''`** | **`''`** |
| f substate cached cv clears its LocalStorage | `''` | `'bad'` | `'bad'` | **`''`** | **`''`** |
| c `on_load` clears LocalStorage/Cookie/SessionStorage | `''` | `''` | `''` | `''` | `''` |
| d clicked event clears them | `bad` until the click, then `''` (all versions) | same | same | same | same |
| g cached cv sets a different plain var (UI `plain=`) | `initial` until reload 2 | same | same | **`set-by-cv` immediately** | **immediately** |
**F-003 is FIXED** and deterministic: a2 clears the storage on the first reload for both hash seeds, while 0.9.12 only did so on some `PYTHONHASHSEED` values (seed 0 fails like a1);
the plain-var variant g is now delivered as well. No new problem seen in the websocket frames or console of the a2 runs.

### Returning visitors after an upgrade + changed source defaults, and the sync=True two-tab race (`f1ret-*`, `shots/f1ret/`, `shots/f1/f1-sync-tabs-*.json`, `scripts/f1_sync_tabs.py`)
Same `f1combo` app (storage vars + `default_factory`, 10-06 F-002 repro), same persistent profile on port 3156, step 1 first visit, step 2 returning visit after the app source changed its defaults to `*-v2`:
| first visit under -> returning visit under | step 1 writes | step 2 shows | step 2 writes |
|---|---|---|---|
| 0.9.12 -> **0.10.0a2** (in-place upgrade, same app dir) | 0 | **all v2 defaults** (`pl-dark-v2 wu-dark-v2 wu-sync-v2 cs-dark-v2 cu-dark-v2 wt-dark-v2`) | **0** |
| 0.10.0a1 -> 0.10.0a1 (control) | 9 defaults written | stale a1-written values (`wu-light wu-sync-default cu-light wt-light`), 5 more writes | - |
| 0.10.0a1 -> 0.10.0a2 | 9 written by a1 | the a1-written values persist (`wu-light wu-sync-default cu-light wt-light`; browsers cannot be repaired by a2) | 0 new writes |
So a2 neither writes defaults nor hides changed defaults from visitors that never got a1's write-back; visitors who loaded an a1 build keep the stale values that a1 stored.
`f1_sync_tabs.py` (tab B2 connecting while tab A changes a `sync=True` LocalStorage var): 0.9.12 and a2 end with `sync-from-tabA` everywhere and no `storage` event noise; a1 shows the
brief stale revert (`wu_sync: sync-from-tabA -> wu-sync-default -> sync-from-tabA`) and has written `wu-sync-default` into localStorage on first load; a2 does not.

### F-001 / F-004 / F-012 / F-013 bonus (python-only derive scripts from `thirdparty/verification/classattr`, `f1f4/`, `logs/f1f4-*.txt`; no server involved)
* F-001 (class-level backend var read): unchanged by design on a2 - `S._u_str` is still the `Field` (so `S._u_int + 1` raises TypeError, `rx.text(S._u_str)` raises ChildrenTypeError) -
  but `f"{S._u_str}"` now raises the intended `BackendVarFormatError: Backend var 'S._u_str' exists only on t...` instead of silently formatting the repr (#7456). The `__dunder__` half (#7465) was not
  exercised here (enterprise wrapper not in this cluster).
* F-004 (class-level assignment replaces the descriptor): FIXED - after `Cfg._key = 'sk_live'` a2 keeps `Field(default='sk_live')` in `Cfg.__dict__`, a fresh instance reads `'sk_live'`,
  `pickle` round-trips it, instance writes mark the var dirty and `reset()` works (a1: descriptor replaced, `a._key` lost on pickle, `c._key = ...` and `reset()` raise `SetUndefinedStateVarError`;
  0.9.12 ignores the class assignment for instances, `a._key` stays `None`).
* F-012 unchanged (`PageContext.get()` -> bare `LookupError: <ContextVar name='PageContext' ...>`), F-013 unchanged (the `rx.Model` deprecation location still points into site-packages).

## In-place a1 -> a2 (what an alpha tester does), `freeze/a1up-*.txt`, `pkg/clock-a1*.json`, `shots/ck/ck-a1-base.json`, `ck-a1toa2.json`
Venv with `reflex==0.10.0a1 pytz` and `reflex-hosting-cli==0.1.73a1` (what 10-06 testers had), clock app dir with the `.web/` built by a1:
`uv pip install --prerelease=allow -U 'reflex==0.10.0a2'` moves reflex, reflex-base, reflex-build-sdk 0.0.5->0.1.0a1, the 8 components that already had alphas, dataeditor 0.9.3.post1->0.10.0a1,
lucide 1.0.4->1.1.0a1, react-player 0.9.2->0.10.0a1, sonner 0.9.4->0.10.0a1 and **hosting-cli 0.1.73a1 -> 0.2.0a1** (the `!=0.1.73a1` exclusion works; a plain install without `-U` does the same).
`.web/package.json` after the upgrade is byte-identical to the a1 one; first run: Restoring lockfiles, frozen install, `bun add`; clock drives 17/0/0 before and after (`ck-a1-base`, `ck-a1toa2`).
`reflex export` (github-stats copy, `pkg/export-*.list`): the backend zip (11 files) and frontend zip (42 files) of 0.9.12 and a2 have identical name lists once the asset hashes are stripped.

## Item 3: stock install smoke (`smoke_blank/`, `shots/smoke/`, `freeze/smoke-stock.txt`, `pkg/smoke-*.json`)

`uv venv --python 3.12` + `uv pip install --prerelease=allow reflex==0.10.0a2` -> `reflex init --template blank` (1.3 s; writes `requirements.txt` = `reflex==0.10.0a2`,
`AGENTS.md`, `CLAUDE.md`, `.web/`, `reflex.lock/`) -> `reflex run` on 3157/8157 (up in 7 s with a warm bun cache) -> `reflex run --env prod` (9 s).
Resolved graph (`freeze/smoke-stock.txt`): reflex, reflex-base 0.10.0a2, reflex-build-sdk 0.1.0a1, components code/core/gridjs/markdown/moment/plotly/radix/recharts 0.10.0a2,
dataeditor/react-player/sonner 0.10.0a1, lucide 1.1.0a1, hosting-cli 0.2.0a1, granian 2.8.4, starlette 1.7.0, wrapt 2.5.0 and no pydantic.
Generated `.web/package.json` is **byte-identical** to the 10-06 a1 smoke and to the other 10-07 smoke agent's: react/react-dom 19.3.0, react-router/@react-router/* 8.4.0,
vite 8.3.2, @radix-ui/themes 3.3.0, lucide-react 1.26.0, socket.io-client 4.8.4, sonner 2.0.8, universal-cookie 8.1.2, tailwindcss + @tailwindcss/postcss 4.3.0, @tailwindcss/typography 0.5.20,
postcss 8.5.29, autoprefixer 10.6.1, react-error-boundary 6.1.6, react-helmet 6.1.0, isbot 5.2.2, mergician "v2.0.2".
Chromium: dev and prod show the welcome page, the colour-mode button toggles dark mode, no console errors, no failed requests (404 only for the
deliberate `/nope`), no storage writes besides the framework keys; prod `/ping` 200, `/sitemap.xml` 200. Python 3.10 is refused cleanly by both
installers (`logs/py310-*.log`): uv "reflex==0.10.0a2 depends on Python>=3.11,<4.0 ... unsatisfiable", pip "Ignored the following versions that require a different python
version: 0.10.0a2 Requires-Python <4.0,>=3.11 ... No matching distribution found" (plain `pip install reflex` on 3.10 resolves 0.9.12).

## Other re-verifications

* **F-005 (sqlmodel cap) FIXED**: `reflex[db]==0.10.0a2` requires `sqlmodel>=0.0.24` (no cap). `uv pip install --dry-run --prerelease=allow -U 'reflex[db]==0.10.0a2'` from a working
  0.9.12 db venv keeps sqlmodel 0.0.48 (no downgrade; `freeze/dt-dryrun-db-U.txt`). The 10-06 hard break is gone: with the dtapp (`rx.Model` with `created_at: datetime`),
  `reflex db init/makemigrations` on 0.9.12 + sqlmodel 0.0.48 writes `sqlmodel.sql.sqltypes.UTCDateTime()` into the migration; after the in-place upgrade to a2,
  `reflex db migrate` on a FRESH database rc 0 (a1: AttributeError, rc 1), on the existing DB rc 0 and `makemigrations` generates nothing; in Chromium (America/New_York) the app behaves
  exactly like 0.9.12 (aware insert fine, rows read back aware `+00:00`, naive insert rejected with sqlmodel's own clear message; `shots/dt/dt-0912.json` vs `dt-a2-inplace.json`, same 6/2 checks:
  the 2 "fail" checks are the naive-insert path, identical on both).
  Side effect to know: the db-extra upgrade (`-U 'reflex[db]==...'`) also moves SQLAlchemy 2.0.54 -> 2.1.3; the app keeps working because `greenlet` was already installed.
* **F-006 (component floors) FIXED**: reflex 0.10.0a2 requires `reflex-components-*>=<their 0.10 alpha>` and `reflex-hosting-cli!=0.1.73a1,>=0.2.0a1`. In a pip-managed 0.9.12 venv
  `pip install -U 'reflex==0.10.0a2'` (NO `--pre`) now installs reflex, reflex-base, reflex-build-sdk, all 13 component packages at their 0.10/1.1 alphas and hosting-cli 0.2.0a1
  (a1 left every component at 0.9.x); `pip check` clean (`freeze/pipup-*.txt`, `logs/pipup-upgrade-nopre.log`).
  `uv pip install [-U] reflex==0.10.0a2` without `--prerelease=allow` still fails ("pre-releases weren't enabled") with a clear hint, as on a1 (uv semantics).
* **F-014 unchanged**: `reflex component --help` -> `Error: No such command 'component'. Did you mean 'compile'?` rc 2 (`logs/reflex-component-cli-a2.txt`); 0.9.12 lists init/build/install/share.
* **F-019 unchanged**: the stale prod tab of the Redis twitter run (0.9.12 bundle) kept working against a2 with no UI signal; the only trace is
  `Warning: Frontend version 0.9.12 for session ... does not match the backend version 0.10.0a2` (`logs/twredis-up-prod.server.log:341`, and the same line in `ck-up-run1.server.log` for the dev clock tab).

## Issues / observations

### I-1 (HIGH, regression: no - 0.9.12 breaks identically on a fresh install; environment drift) fresh `reflex[db]` installs are unusable: SQLAlchemy 2.1 drops the greenlet dependency
sqlmodel 0.0.48 (uploaded 2026-10-06T21:44Z) widened its cap to `SQLAlchemy<2.2.0,>=2.0.14`; SQLAlchemy 2.1.0 (2026-09-24) .. 2.1.3 (2026-10-03) no longer installs `greenlet`
by default (it is the `asyncio` extra). reflex's db extra is `alembic<2,>=1.15.2`, `pydantic>=2.12`, `sqlmodel>=0.0.24` (0.9.12: `sqlmodel<0.1,>=0.0.24`): no `sqlalchemy[asyncio]`/`greenlet`.
`reflex/model.py:69` does `import sqlalchemy.ext.asyncio` at import time, which now raises.
```bash
cd $SB && uv --no-config venv --python 3.12 $SB/envs/x && uv --no-config pip install --python $SB/envs/x/bin/python --prerelease=allow 'reflex[db]==0.10.0a2'   # same with 'reflex[db]==0.9.12' and without --prerelease
uv --no-config pip freeze --python $SB/envs/x/bin/python | grep -iE '^(sqlalchemy|sqlmodel|greenlet)'      # sqlalchemy==2.1.3 sqlmodel==0.0.48, no greenlet
cd /tmp && $SB/envs/x/bin/python -c "import reflex.model"
# ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed.  In order to ensure this dependency is available, use the 'sqlalchemy[asyncio]' install target: ...
cd <any app with rx.Model> && $SB/envs/x/bin/reflex db init        # same ImportError traceback (logs/dbfresh-reflex-db-init.log); `reflex run` too (logs/dbfresh-run.log)
```
Same with plain `pip install` (pip 26.2.1) for both 0.9.12 and 0.10.0a2. Every example that uses `reflex[db]` (form-designer, twitter, basic_crud, reflex-local-auth apps, ...) is affected for new users, CI and Docker builds.
Workarounds, both verified: add `greenlet` (form-designer on SQLAlchemy 2.1.3 + greenlet passes the same flows on 0.9.12 and a2: `fdsa21-stable-full/entry` 18/0/2, 14/0/1 and `fdsa21-a2-*` identical;
SQLAlchemy 2.1.3 itself works with reflex) or `sqlalchemy<2.1`. Existing 0.9.12 installs that already have greenlet keep working, including after the in-place upgrade.
Fix direction: add `sqlalchemy[asyncio]` (or `greenlet`) to the `db` extra, ideally also as a 0.9.13 patch because stable users hit it today.
EVIDENCE: `logs/fd-base-run1-greenlet-importerror.server.log`, `logs/dbfresh-*.log`, `freeze/*-fresh-resolution-sa2.1.3.txt`, `freeze/fd-sa21-*.txt`.

### I-2 (LOW, no regression - unchanged) `reflex component` removal message (F-014), see above.

### Observations (not issues)
* The brief's `-U ... 'pydantic<2.14'` adds pydantic to apps that had none; stock a2 has no pydantic (smoke freeze).
* `--prerelease=allow` on a fresh `reflex[db]==0.10.0a2` lets sqlmodel pull pydantic 2.14.0b2 (beta); pinned `pydantic<2.14` in every run here.
* Chromium logs `www.google.com`/`ssl.gstatic.com` CONNECT rejections through the proxy (browser background traffic), nothing to do with reflex.
* The baseline 0.9.12 bun install prints the benign `incorrect peer dependency "react@19.3.0"` after the first upgrade.
* Process note: a helper script run with its output piped into `head -1` was killed by SIGPIPE halfway through its cleanup and left a 0.9.12 server alive; the first F-003 batch
  therefore ran every label against that one server and was thrown away (rerun with `scripts/run_f3.sh`, which aborts if the server did not start).

## Cleanup / deviations
All servers, redis, the GitHub stub and every Chromium started here were stopped; ports 3140-3159/8140-8159 are free. While setting up, a mistyped
`export SB=... W=$SB/...` (SB unset in the same expansion) created a stray `/apps/upgrade_sweep` tree at the filesystem root; its removal was blocked by the safety check, so
the files were copied to `$W` and **`/apps` is left for a human to remove (`rm -rf /apps`)**.

## Artifact map
```
NOTES.md                  this file
form-designer/ github-stats/ clock/ twitter/ twitter-redis/   app sources as run (QA patches applied; .web, .states, *.db, reflex.lock excluded)
bin/                      run_app.sh stop_app.sh ports.sh sync_dest.sh
scripts/                  drivers, storage_probe.py, clock_session.py, compare_sets.py, run_f3.sh, f3_table.py, dbdump.py ...
patches/                  the two opt-in QA patches
freeze/                   uv pip freeze per venv base/up + diffs + dry-runs
pkg/                      .web/package.json base/up/cold, diffs, reflex.lock hashes, .web file lists
logs/                     server logs, install logs, db dumps, comparison output, CLI output
shots/<app>/              <tag>.json (checks, console, network, ws frames trimmed) + a few screenshots
```
