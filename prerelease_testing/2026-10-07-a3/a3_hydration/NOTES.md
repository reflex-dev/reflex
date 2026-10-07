# Item `a3_hydration` — reverify_hydration suite + reflex#7493 boot-echo regressions on reflex 0.10.0a3

Date 2026-10-07 (evening). Under test: **reflex 0.10.0a3 / reflex-base 0.10.0a3** (PyPI) in the shared read-only venv
`$SB/envs/a3`. Baselines: `$SB/envs/alpha2` (0.10.0a2), `$SB/envs/stable` (0.9.12); positive controls on `$SB/envs/alpha`
(0.10.0a1, which had F-002/F-003). Browser: Playwright + `/opt/pw-browsers/chromium` from `$SB/envs/driver`.
Nothing was installed from / run inside a checkout: every app runs from `$W/run/<name>` and asserts that `reflex.__file__`
is under `/scratchpad/envs/$RVH_VENV/` (env var set by `scripts/srv.sh` to the venv name). Ports used: 3140-3154 /
8142-8153, redis 8149. One server at a time; everything stopped at the end (`lsof` shows no listener in 3140-3159/8140-8159).

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_hydration
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
# To rerun elsewhere: mkdir -p $W && cp -r src drivers scripts probes cv srv.sh $W/  (the scripts hard-code W)
```

## Verdicts
| item | verdict on 0.10.0a3 | key evidence |
|---|---|---|
| F-002 (first load writes storage defaults) | **still fixed** (dev, prod, prod+redis; plain, substate, ComponentState, cookie options, sync=True; local-auth, google-auth) | §1, §2; positive control catches 0.10.0a1 |
| F-003 (cv storage rewrite at hydration dropped) | **still fixed** (cvstore a–j, seeds 0/4, dev/prod/prod+redis, line-for-line = a2; google-auth bogus token cleared) | §4; positive control catches a1 |
| reverify_hydration sweep (hydapp s1–s13, reconnect redis/memory, redis restart loop, token leak, prenav, preconnect, csbox, mini) | **every a2 pass still passes**; only timing/port/id diffs | §5 |
| #7493 (a)–(e) | pass: nothing written on first load; `get_delta` override sees browser values once (= 0.9.12; a2 never); no extra frame vs a2; computed vars correct at boot; on_load value wins | §2 |
| **#7493 (f) many tabs + sync=True** | **NEW REGRESSION vs a2** (`a3_hydration-1`, medium): a stale boot echo starts an endless cross-tab ping-pong; a2 0/15, a3 11/17, 0.9.12 9/10 | §3 |
| sync=True written by several tabs at once (on_load stamp) | **NEW, pre-existing on all versions** (`a3_hydration-2`, medium) | §3b |
| #7493 (g) F-008 >1 MB storage | unchanged (still storms: 774 dev / 741 prod websocket opens in 22 s) | §5 s5 |
| reflex-local-auth / reflex-google-auth | pass, = a2 = 0.9.12 (local-auth 36/38 known demo pitfall + 14/14 storage checks) | §6 |

## Layout
* `src/` — apps from `../../2026-10-07/reverify_hydration/src` (hydapp, f1combo, v2/f1combo, f1plain, mini_writeback,
  cvstore, csbox, google_auth_demo), `local_auth_demo` (from `../../2026-10-07/thirdparty_a2/apps`, venv guard added) and new
  **`bootecho`** (§2) and **`syncstamp`** (§3b).
* `scripts/srv.sh start <name> <venv> <dev|prod> <src> <FP> <BP> [ENV=VAL...]` / `stop <name>` (copies sources into
  `$W/run/<name>`, `reflex run --loglevel debug`, own process group, refuses ports outside 3140-3159/8140-8159).
  One-command runners: `run_f002.sh`, `run_be.sh`, `run_storm.sh`, `run_stamp.sh`, `run_cv.sh`, `run_la.sh`, `run_gauth.sh`;
  `build_venvs.sh` (third-party venvs), `cmp_hyd.py`, `summ_storm.py`, `trim_log.sh`, `sync_dest.sh`.
* `drivers/` — reverify_hydration drivers (redis port changed to 8149) + new `bootecho_check.py`, `sync_race.py`,
  `stamp_storm.py`, `la_storage.py`, `cookie_raw.py`; `drivers/tp/` = thirdparty_a2's `drive_local_auth.py` + `tpdrive.py`.
* `cv/drivers/` — cvstore / google-auth drivers (unchanged).
* `results/` — JSON per run (websocket `*.raw.json` dumps not copied); `results/env/*.freeze.txt`; `trimmed/` — trimmed server logs.

## Venvs (PyPI only, cwd=$SB, `uv --no-config`, Python 3.12) — `scripts/build_venvs.sh`
* `$SB/envs/a3_hydration-tp-a3`: `reflex[db]==0.10.0a3 reflex-base==0.10.0a3 reflex-local-auth==0.5.0 reflex-google-auth==0.2.0 'google-api-python-client>=2.184.0' 'pydantic<2.14'` (greenlet 3.5.6 via the db extra)
* `$SB/envs/a3_hydration-tp-a2`: same with `reflex[db]==0.10.0a2 reflex-base==0.10.0a2 'greenlet>=3.3'`
* `$SB/envs/a3_hydration-tp-s912`: same with `reflex[db]==0.9.12 'greenlet>=3.3'`

## 0. Positive controls (the harness can still fail)
| control | result |
|---|---|
| F-002 `f1_check.py`, f1combo prod, **0.10.0a1** fresh profile | **bug detected**: LS `cu_ls,wt_ls,wu_ls,wu_sync`, SS `cu_ss,wu_ss`, cookies `cu_ck,wu_ck` written; boot delta root without `is_hydrated_rx_state_` (`results/posctl/`) |
| F-003 `drive_cvstore.py`, cvstore dev seed 4, **0.10.0a1**, variants a/b/g | **bug detected**: `reload [l='bad']` for a/b/g, byte-identical to the saved a1 summary (`results/f003/a1-dev-seed4.summary.txt`) |
| F-003 google-auth, **0.9.12** dev seed 4 | bogus token kept (`BOGUS` after reload) — the driver still sees the failure |
| #7493 bootecho on **a2** | a2's known gap is visible: sanitising `get_delta` override never reaches the browser (`be_tok` stays `bad-xyz`) |
| sync storm drivers on **0.9.12** | storms 9/10 (Part S) and 3/3 (`/stamp`) — the drivers detect a ping-pong when there is one |

## 1. F-002 on a3 — still fixed
`scripts/run_f002.sh <venv> <dev|prod> <label> <FP> <BP>`: f1combo fresh ×2, returning visitor (same build), `f1_sync_tabs.py`,
restart with `src/v2/f1combo` (every default changed), returning visitor, fresh v2. Ports: prod 3140, dev 3142/8142.

| check | a2 prod (rerun today) | **a3 prod** | **a3 dev** | 0.9.12 (10-06) |
|---|---|---|---|---|
| fresh ×2: storage written | nothing | **nothing** | **nothing** (theme, last_compiled_theme only) | nothing |
| v1 visit → v2 build → returning visitor | all v2 | **all v2** | **all v2** | v2 |
| `f1_sync_tabs.py` (B2 socket held 2.5 s while A changes the synced var) | converges, no storage event in A | **same** | **same** | — |
| boot delta root | `is_hydrated:false` + router | same | same | — |

mini_writeback a3 prod (`srv.sh start mini-a3 a3 prod src/mini_writeback 3141 3141`, `mini_writeback_check.py`, `mini_choose.py`):
fresh `{}` and no cookie; restart with `MINI_THEME_DEFAULT=dark` → returning visitor who never chose sees `dark`; a user who
chose `blue` keeps `blue` + cookie `mini_consent=granted` (`results/f002/mini/`). Identical to a2.

## 2. #7493-specific: `src/bootecho` + `drivers/bootecho_check.py`
reflex#7493 (`reflex/state.py:2401`, `2420-2422` in the published a3): `hydrate_and_load` re-marks every browser-provided
client-storage var dirty after the boot snapshot, so the final boot delta (`is_hydrated:true`) carries each browser value again
(the "echo"); it passes through `get_delta` overrides and the frontend writes it back to storage.

App `src/bootecho`: `Prefs` (LS sync=True `be_theme`, LS `be_note`, SS `be_sess`, Cookie `be_ck`, Cookie `be_ckopt` path=/
max_age=3600 same_site=strict, cached cv `theme_upper`, uncached cv `note_len`, cv `ck_combo`, logging `get_delta` override),
substate `SubPrefs` (LS + Cookie max_age 7200 lax, cv `sub_combo`, own override), `Guard` (LS `be_tok`; override sanitises a
`bad*` value to `""` in the delta = an auth-like filter), `Srv` (`/onload` page whose on_load sets LS + Cookie), `/plainload`
(no-op on_load), two `Box` ComponentState instances (LS + Cookie max_age, no `name`). Every override call prints
`BOOTTRACE GD {...}` with the tab token; the driver counts calls and inbound deltas per page load.
Rerun: `$W/scripts/run_be.sh <venv> <dev|prod> <label> <FP> <BP> [REFLEX_REDIS_URL=redis://localhost:8149]`
(labels used: a3dev, a2dev, s912dev on 3142/8142; a3prod, a3prodredis, a2prod, s912prod on 3144).

| check | a2 (dev = prod) | **a3 (dev = prod = prod+redis)** | 0.9.12 (dev = prod) |
|---|---|---|---|
| (a) fresh `/`, `/plainload`: written | nothing | **nothing** | nothing |
| (a) fresh `/onload` | only its on_load values `be_srv`, `be_srv_ck` | same | same |
| returning user (values set by events, both Box instances): reload keeps all | yes | yes | yes |
| (c) boot inbound, returning user `/`: frames / deltas / bytes | 4 / 2 / 3372 B | 4 / 2 / **4198 B** (+826 B, +24 %: each browser value sent twice) | 6 / 4 / 4866 B |
| (c) boot inbound, fresh `/` | 4 / 2 / 2118 B | 4 / 2 / 2118 B | 5 / 3 / 3504 B |
| (b) `get_delta` overrides see browser values at boot | **never** (N-032 mechanism) | **once**, in the final delta (Prefs 3 calls, SubPrefs 1, Guard 1) | once (update_vars_internal delta; Prefs 4, SubPrefs 1, Guard 1) |
| (b) sanitising override (`be_tok=bad-xyz`) reaches the browser | no (`bad-xyz` kept) | **yes** (`""`) | yes |
| (d) computed vars over storage at the first `H:yes` | correct (`T:BLUE`, `N:5:hello`, `subval+blue`) | correct | correct |
| (e) on_load value beats the browser's (`/onload`) | yes (value in 2 deltas) | yes (3 deltas: snapshot, echo, on_load) | yes (3) |
| cookie with max_age rewritten at boot (expiry slides +5–8 s after a 3 s wait) | no | **yes** | yes |
| raw cookie set outside reflex (`be_ck={"a":1}`, `%41BC`) after a reload (`drivers/cookie_raw.py`) | untouched | **re-encoded** (`%7B%22a%22%3A1%7D`, `ABC`) | re-encoded |
| console errors / failed requests | only prod `/favicon.ico` 404 | same | same |

So #7493 restores 0.9.12's boot semantics (override sees the browser value once, sanitised values reach storage) with one
frame fewer than 0.9.12 and no extra frame vs a2. Side effects shared with 0.9.12 (not with a2): every returning visit rewrites
every client-storage value (cookie expiry slides, raw cookie values re-encoded) and doubles those bytes in the boot traffic.

## 3. sync=True LocalStorage across tabs — `drivers/sync_race.py` — NEW REGRESSION vs a2 (`board/findings-inbox/a3_hydration-1.md`)
Part R: tab B boots with its inbound websocket messages held 2.5 s (Playwright `route_web_socket`; B's CONNECT already carried
`be_theme=v1`) while tab A changes the synced value v1→v2. Part S: tab0 + 6 tabs loading concurrently while tab0 changes the
value 5× (250 ms apart); convergence and websocket traffic in a 2 s window 4 s later.
Rerun: `$W/scripts/run_storm.sh <venv> <dev|prod> <runs> <FP> <BP> <S|R> [NTABS]` (dev 3142/8142, prod 3144 3144);
long form: `$NP $DRV $W/drivers/sync_race.py http://localhost:3142 out.json 2500 6 S 60`.

| | a2 | **a3** | 0.9.12 |
|---|---|---|---|
| R: A shows the stale v1 again after its own change | dev 0/2 (no storage event in A) | **dev 1/2** (A: v2→v1→v2; 2 storage events, 2 extra update_vars_internal) | dev 2/2 (4 storage events in A) |
| S, 6 tabs: endless ping-pong, tabs never converge | **dev 0/10, prod 0/5** (always `s5`, ~75–95 frames) | **dev 6/9 + 3/3 (60 s runs), prod 2/5** | dev 9/10 |
| S, 5 tabs / 3 tabs / 2 tabs | — | 3/6 / 0/6 / 0/6 | — |

A storm never decays: 60 s observation windows of 5 s each carried 8k–39k frames (`storm_long_a3_dev_*.json`), 2–9k storage
events per tab in 6 s, tabs end on mixed stale values (s2/s3/s4 — the user's last value s5 is lost), the backend process sat at
~50–70 % CPU. No console error, no server error (only `Attempting to send delta to disconnected client` after the tabs closed).
Mechanism: a booting tab echoes the value it read when it built the CONNECT; if another tab changed the key meanwhile, that stale
`localStorage.setItem` fires `storage` in every other tab (`state.js:1267` → `update_vars_internal`), whose deltas write back
again; with two values in flight and ≥4 tabs the loop sustains itself. a2 never wrote at boot, so this trigger did not exist.

### 3b. Pre-existing: sync=True written by several tabs at once (`src/syncstamp`, `drivers/stamp_storm.py`) — `a3_hydration-2`
`/stamp`'s on_load sets a sync=True LocalStorage var to a per-tab value (e.g. "last page seen"); N tabs load at once (session
restore). Frames counted in-page (WebSocket wrapper; Playwright frame events crashed the node driver with `write EINVAL` at
this volume). Rerun: `$W/scripts/run_stamp.sh <venv> dev <runs> 3142 8142 /stamp <N>`.

| | a2 | a3 | 0.9.12 |
|---|---|---|---|
| 6 tabs `/stamp` | storm 2/2 completed (118k–137k frames / 5 s; 2 driver crashes) | storm 2/2 completed (41k–234k / 5 s; 2 driver crashes) | storm 3/3 (40k–64k / 5 s) |
| 3 tabs / 2 tabs `/stamp` | 2/3 / 0/3 | — | — |
| control `/same` (every tab writes the same value), 6 tabs | — | quiet 3/3 | — |

Not caused by a3 (state.js byte-identical a1→a3); reported as new because no earlier campaign recorded it.

## 4. F-003 on a3 — still fixed (`scripts/run_cv.sh`)
| variant | a2 (saved) dev s0/s4, prod s0/s4, prod+redis s0 | **a3 dev s0 / s4** | **a3 prod s0 / s4** | **a3 prod+redis s0** |
|---|---|---|---|---|
| a b c d e_cookie e_session f g | PASS everywhere | **identical summaries, line for line** | **identical** | **identical** |
| i (on_load page), j (state sent in full) | PASS | PASS | PASS | PASS |
| client-nav path (`drive_cvnav.py`, seed 0) | a/b/e/f/g FAIL (N-015, pre-existing) | **same** | — | — |
| (b) uncached cv shows its hydrate-time value until next reload | yes (N-016, pre-existing) | **same** | same | same |

reflex-google-auth 0.2.0 demo (`scripts/run_gauth.sh`, dummy client id): bogus `token_response_json` cleared on the first
reload — a3 dev seeds 0/4/10 and prod seed 4 (a2 dev seed 4 too; 0.9.12 dev seed 4 keeps `BOGUS`, rerun today). Full report
(`drive_google_auth.py`) 12/13, same check outcomes as a2 (the one "fail" = no default write-back, as on 0.9.12); console noise
is the sandbox network (gstatic tunnel failure, accounts.google.com 400/403, `gis is not defined`).

## 5. reverify_hydration sweep on a3 (vs the saved a2 results in `../../2026-10-07/reverify_hydration/results`)
| test | a3 | vs a2 |
|---|---|---|
| hydapp `hyd_driver.py` s1–s13 dev (3147/8147) and prod (3148) | s1–s3, s5–s9, s11–s13 pass; s4, s10 anomaly | `cmp_hyd.py`: identical statuses; diffs only timing/ports/session ids; prod s10 lost no click this time (a2 lost 1); s13 boot bytes unchanged |
| F-008 (s5, 1.2 MB LS) | still storms: 774 opens dev / 741 prod in ~22 s | unchanged (a2: 593/646) |
| reconnect_driver prod + redis (3150) | kill → banner, restart → token same, counter 3 kept, LS kept, click works | identical fields |
| reconnect_driver memory `--default-change` (3151) | state reset by design, token same, returning visitor sees `sub-ls-NEWDEFAULT` | identical |
| redis_restart_loop (F-017) 5 rounds | 5/5 token + counter kept, no leftover keys, no panic | same (a2 6/6) |
| token_leak_check 2 rounds | no leftover `token_manager_socket_record_*` | same |
| prenav_test (F-010) | `/slow → /other`: left page's on_load still runs; `/items/1 → /items/2`: id=1 then id=2 | unchanged (pre-existing) |
| preconnect_click (socket held 2.5 s) | click processed after on_load, 3/3 | same |
| csbox (ComponentState storage, dev 3152) | `plain` instance now persists (N-005 fixed); instances with the same declared `name` share the key | a2 lost the plain choice in a new tab |
| server logs | only `[ERROR] Unexpected exit from worker-1` at SIGTERM (pre-existing granian line) and the intentional hydapp s4/s6 errors | same |

Rerun: `srv.sh start hyd-a3dev a3 dev src/hydapp 3147 8147; (cd drivers && hyd_driver.py --base http://localhost:3147 --label a3-dev --out $W/results/hyd/a3-dev)`;
`$DRV scripts/cmp_hyd.py results/hyd/a3-dev <a2 dir>`; redis: `redis-server --port 8149 --save '' --appendonly no`;
`drivers/reconnect_driver.py --venv a3 --port 3150 --manager redis --out results/reconnect-a3-redis`;
`drivers/redis_restart_loop.py a3 3150 5`; `drivers/reconnect_driver.py --venv a3 --port 3151 --manager memory --out results/reconnect-a3-memory --default-change`;
`drivers/token_leak_check.py a3 3150 2`; `drivers/prenav_test.py http://localhost:3148 a3-prod out.json 2000`;
`drivers/preconnect_click.py http://localhost:3148 a3-prod out.json 2500`; `drivers/csbox_check.py http://localhost:3152 out.json`.

## 6. Third-party auth packages
reflex-local-auth 0.5.0 demo (`scripts/run_la.sh <venv> <dev|prod> <label> <FP> <BP> [REFLEX_REDIS_URL=...]`, dev 3153/8153,
prod 3154): thirdparty_a2's `drive_local_auth.py` (38 checks: register, login, redirect_to, reload, second tab, fresh context,
logout, session expiry, …) + new `la_storage.py` (fresh profile writes nothing on 4 pages; login stores `_auth_token`; reload and
second tab stay logged in; logout in tab A → tab B logged out after reload; bogus token → anonymous; console clean).

| | a3 dev | a3 prod | a3 prod+redis | a2 dev | 0.9.12 dev |
|---|---|---|---|---|---|
| drive_local_auth | 36/38 | 36/38 | 36/38 | 36/38 | 36/38 |
| la_storage | 14/14 | 14/14 | 14/14 | 14/14 | 14/14 |
| `auth_token` occurrences in the reload's inbound deltas | 2 (snapshot + echo) | 2 | 2 | 1 | 2 (`''` then token) |

The two failures are the known `/tp-strict-register` demo pitfall (subclass `_validate_fields` override ignored), identical on
every version (thirdparty_a2 NOTES §4). After logout the token stays in localStorage (local-auth deletes the DB session, by
design); a bogus token stays in storage and the user is anonymous — same on all versions.
reflex-google-auth: see §4 (real Google login/logout impossible in the sandbox; bogus-token + fresh-storage + protected-page checks only).

## Issues raised
1. `a3_hydration-1` (medium, regression vs a2, not vs 0.9.12): §3.
2. `a3_hydration-2` (medium, pre-existing all versions): §3b.
3. Reverify files: `a3_hydration-3` (F-002 fixed), `a3_hydration-4` (F-003 fixed).

## Not covered
* Real Google OAuth login/logout (sandbox network); reflex-google-auth only with a dummy client id.
* Python versions other than 3.12; browsers other than Chromium.
* Hydration timing at 80 ms RTT (a3 vs a2) — frame counts are equal, so not re-measured.
* Dev hot reload (`hmr_desync.py`) not re-run on a3.
