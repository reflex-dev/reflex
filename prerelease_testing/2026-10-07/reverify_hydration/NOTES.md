# Cluster `reverify_hydration` — F-002/F-003/F-008/F-010/F-017 on reflex 0.10.0a2 + #7460 regression sweep

Date 2026-10-07. Version under test: **reflex 0.10.0a2 / reflex-base 0.10.0a2** (PyPI, train
`r/pre-2026.10.06-37579583012`) in the shared read-only venv `$SB/envs/alpha2`. Before/after: `$SB/envs/alpha`
(0.10.0a1) and `$SB/envs/stable` (0.9.12). For reflex-google-auth I built `$SB/envs/reverify_hydration-galpha2`
(`reflex==0.10.0a2 reflex-google-auth==0.2.0 google-api-python-client 'pydantic<2.14'`, all from PyPI, Python 3.12).
Browser: Playwright 1.63 + `/opt/pw-browsers/chromium` from `$SB/envs/driver`. Nothing was installed from or run
inside a checkout; every app runs from `$W/run/<name>` and asserts `reflex.__file__` is under
`/scratchpad/envs/$RVH_VENV/` (env var set by `scripts/srv.sh`).

`SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad`, `W=$SB/apps/reverify_hydration`.
Ports used (reserved 3220-3239 / 8220-8239): see each section. One server at a time.

## Layout of this folder
* `src/` — apps (copied from the 10-06 campaign, only the venv guard changed): `hydapp` (16-page probe app),
  `mini_writeback` (+ a `choose blue` button I added: a user choice must still be persisted), `f1plain`, `f1combo`,
  `v2/f1combo` (same app, every default changed), `cvstore` (computed-var-writes-storage variants a–g),
  `google_auth_demo` (reflex-google-auth 0.2.0 upstream demo).
* `scripts/srv.sh` — `srv.sh start <name> <venv> <dev|prod> <src> <FP> <BP> [ENV=VAL...]` / `srv.sh stop <name>`:
  copies sources to `$W/run/<name>`, runs `$SB/envs/<venv>/bin/reflex run --env <mode> --loglevel debug` in its
  own process group with `REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=...`, refuses ports outside the range.
* `drivers/` — hydration drivers from 10-06 (hyd_driver, f1_check, f1_sync_tabs, prenav_test, f6_natural, reconnect,
  redis loop, ab_timing, latency/upgrade-delay proxies) + new `mini_choose.py`.
* `cv/drivers/` — cvstore/google-auth drivers from the 10-06 verifier + new `drive_cvnav.py` (client-nav path).
* `results/` — JSON/text results per section. `logs/` — trimmed server logs. `shots/` — screenshots.

Common prefix for every driver command below:
```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/reverify_hydration
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
```

## 1. F-002 (first load persists client-storage defaults) — **FIXED** in 0.10.0a2 (dev + prod)

### How the fix works (published alpha2 sources, `$SB/envs/alpha2/lib/python3.12/site-packages`)
* `reflex/state.py:2338-2391` `State.hydrate_and_load`: resets client storage (2365), applies the browser `vars`
  (2367), **then `self._clean()` (2368, new)**, then sets `is_hydrated = False` (2372) so that flag is the only dirty
  var; snapshots `delta = _resolve_delta(self.dict())` (2375), diffs against compiled defaults (2376-2377), and
  **merges `await self._get_resolved_delta()` into it (2378-2380, new)** — this re-adds the dirty root
  `is_hydrated_rx_state_: false` that `_diff_against_initial_state` (2490-2541) drops as equal-to-default, plus any
  var a computed var wrote while `dict()` ran and the computed vars depending on it. After `emit_delta` it only
  `dirty_vars.discard("is_hydrated")` (2383, new) instead of `_clean()`, so vars dirtied during the snapshot are
  sent again by the event's normal follow-up delta — which has no `is_hydrated:false`, so the frontend writes them
  to browser storage (that's the F-003 fix).
* The frontend is unchanged: `reflex_base/.templates/web/utils/state.js` is byte-identical between 0.10.0a1 and
  0.10.0a2; `applyClientStorageDelta` (`state.js:1045-1060`) still skips storage writes only when the root delta
  carries `is_hydrated_rx_state_` falsy. So the fix took the "always keep `is_hydrated:false` in the diffed boot
  delta" route, on the backend.
* Wire evidence (`results/f002/f1combo_a2_prod_fresh_1.json`): first inbound delta root =
  `is_hydrated_rx_state_` **False** + the 5 `rx_router_*` vars; `WithUuid`, `ChildStorageUuid`, `WithClockVar`,
  `ParentUuid` still sent in full (hash mismatch, as designed); second delta `is_hydrated_rx_state_: True`.
  0.10.0a1 had the root without `is_hydrated_rx_state_`.

### Results (ports: f1combo prod 3220, mini prod 3221, f1combo dev 3222/8222)
| check | 0.10.0a1 (10-06) | **0.10.0a2** | 0.9.12 (10-06) |
|---|---|---|---|
| f1combo prod, fresh profile ×2: storage written | LS `cu_ls,wt_ls,wu_ls,wu_sync`, SS `cu_ss,wu_ss`, cookies `wu_ck,cu_ck` | **nothing** (only the frontend's own `theme=system`) | nothing |
| f1combo dev, fresh ×2 | same as prod | **nothing** (`theme`, `last_compiled_theme` only) | nothing |
| f1combo v1 visit → restart with `v2/f1combo` (all defaults changed) → returning visitor | v1 values for every triggered state | **all v2 values** (`wu-dark-v2`, `cu-dark-v2`, `wt-dark-v2`, …) | v2 |
| mini prod fresh | `mini_theme=light`, cookie `mini_consent=unset` | **`{}`, no cookie** | none |
| mini: restart with `MINI_THEME_DEFAULT=dark`, returning visitor who never chose | `light` (stale) | **`dark`** | dark |
| mini: user clicked "choose blue" (event writes LS + cookie), then default changed to dark | n/a | **`blue`, cookie `mini_consent=granted` kept** (user choices still persisted) | n/a |
| `sync=True` two tabs with B2's socket held 2.5 s while A changes the synced var (`f1_sync_tabs.py`, 2 runs) | transient revert in A (2 storage events, 2 extra round trips) | **no storage events in A, no revert, converges to `sync-from-tabA`** | same as a2 |

Console: only the prod `/favicon.ico` 404 (f1combo has no assets; known benign). No server errors/tracebacks.

Rerun:
```bash
$W/scripts/srv.sh start f1combo-a2 alpha2 prod $W/src/f1combo 3220 3220
$NP $DRV $W/drivers/waitsrv.py 400 http://localhost:3220/ http://localhost:3220/ping
$NP $DRV $W/drivers/f1_check.py http://localhost:3220/ - /tmp/s1.json out.json pl-ls,wu-ls,wu-sync,cs-ls,cu-ls,ws-ls,wt-ls
$NP $DRV $W/drivers/f1_sync_tabs.py http://localhost:3220/ sync.json 2500
$W/scripts/srv.sh stop f1combo-a2; $W/scripts/srv.sh start f1combo-a2 alpha2 prod $W/src/v2/f1combo 3220 3220
$NP $DRV $W/drivers/f1_check.py http://localhost:3220/ /tmp/s1.json - returning.json pl-ls,wu-ls,wu-sync,cs-ls,cu-ls,ws-ls,wt-ls
$W/scripts/srv.sh start mini-a2 alpha2 prod $W/src/mini_writeback 3221 3221            # then MINI_THEME_DEFAULT=dark
$NP $DRV $W/drivers/mini_writeback_check.py http://localhost:3221/ - /tmp/m1.json
$NP $DRV $W/drivers/mini_choose.py http://localhost:3221/ /tmp/m_chosen.json
# dev: $W/scripts/srv.sh start f1combo-a2dev alpha2 dev $W/src/f1combo 3222 8222 ; f1_check.py http://localhost:3222/ ...
```

## 2. F-003 (computed-var rewrite of client storage during hydration dropped) — **FIXED on the hydrate path**; client-nav path unchanged (pre-existing)

App `src/cvstore`, driver `cv/drivers/drive_cvstore.py` (sets the variant's key to `bad`, full reload, probe, noop,
client nav out/in, reload2). Ports: dev 3223/8223, prod 3224. FAIL = after the reload, browser storage/UI keep `bad`
while the backend holds `''`.

| variant | 0.10.0a1 (10-06, all seeds) | **0.10.0a2 dev s0 / s4** | **0.10.0a2 prod s0 / s4** | 0.9.12 (10-06) s0 / s4 |
|---|---|---|---|---|
| (a) cached cv clears LocalStorage | FAIL | **PASS / PASS** | **PASS / PASS** | FAIL / PASS |
| (b) uncached cv clears LocalStorage | FAIL | **PASS / PASS** (storage) — UI of `check` stale, see below | **PASS / PASS** (same note) | FAIL / PASS |
| (c) on_load clears LS+Cookie+SS | PASS | PASS / PASS | PASS / PASS | PASS / PASS |
| (d) clicked event clears LS+Cookie+SS | PASS | PASS / PASS | PASS / PASS | PASS / PASS |
| (e1) cached cv clears Cookie | FAIL | **PASS / PASS** | **PASS / PASS** | FAIL / PASS |
| (e2) cached cv clears SessionStorage | FAIL | **PASS / PASS** | **PASS / PASS** | FAIL / PASS |
| (f) cached cv on a substate | FAIL | **PASS / PASS** | **PASS / PASS** | FAIL / PASS |
| (g) cached cv sets a DIFFERENT plain var | FAIL (UI `plain=initial`) | **PASS / PASS** (UI `plain=set-by-cv` = backend) | **PASS / PASS** | FAIL / FAIL |
| (h1–h3) self-heal after a FAIL | no | n/a (no failure on reload) | n/a | no |

Sanity check that the driver still detects the bug: 0.10.0a1 dev seed 4, same driver, variants a/b/g → FAIL
exactly as on 10-06 (`results/f003/a1-dev-seed4.summary.txt`).

Wire (alpha2 dev seed 0, `results/f003/frames/a2-dev-seed0-a.json`, decode with
`cv/drivers/decode_frames.py <file> reload a_cached`):
```
sent CONNECT+EVENT hydrate_and_load {"...a_cached_cv.ls_rx_state_": "bad"}
recv DELTA {"reflex___state____state": {"is_hydrated_rx_state_": false}, "a_cached_cv": {"check_rx_state_": "value=''", "ls_rx_state_": ""}}
recv DELTA {"reflex___state____state": {"is_hydrated_rx_state_": true},  "a_cached_cv": {"ls_rx_state_": "", "check_rx_state_": "value=''"}}   <- follow-up, written to localStorage
```
The cached var shows its *recomputed* value (`value=''`), not the value it returned while clearing
(`cleared-by-cached-cv`) — consistent with the backend.

### Still open (pre-existing / side notes)
* **Uncached computed var display stays stale (side note from 10-06, still present):** variant (b): the boot delta
  carries `check="cleared-by-uncached-cv"` (value computed during the snapshot); the follow-up delta carries only
  `ls=''`; every later event recomputes `check` = `value=''` but the per-client dedup record (last value recorded
  on the *first* page load, `value=''`) drops it as unchanged, so the UI shows `cleared-by-uncached-cv` after probe,
  noop and even a client-side navigation, until the next full reload. 0.9.12 (fresh seeds) shows `value=''`
  throughout. PR #7436 ("record hydrated computed values", still OPEN, not in this train) is the related fix.
  Only reachable when a value changes inside the hydrate event (computed var that writes state). Low.
* **Client-side navigation path (`update_vars_internal` + `on_load_internal`, per-event delta) keeps the old
  hash-seed coin flip** — new driver `cv/drivers/drive_cvnav.py` (set `bad` from JS without reload, navigate
  home → back): alpha2 seed 0 FAIL a/b/e1/e2/f, seed 4 PASS; (g) FAIL on every seed. Identical on 0.10.0a1 (seed 4:
  same) and 0.9.12 (seed 0 all FAIL, seed 4 PASS except g) — `results/f003/cvnav.txt`. Pre-existing, not a
  regression; #7460 only changed `hydrate_and_load`.

### reflex-google-auth 0.2.0 demo (bogus `token_response_json` in localStorage)
`cv/drivers/drive_gauth.py` (inject bogus token, load `/protected`, `/`, client nav, reload2) on
`$SB/envs/reverify_hydration-galpha2`, `GOOGLE_CLIENT_ID=123456789012-dummyclientid.apps.googleusercontent.com`:

| run | 0.10.0a1 (10-06) | **0.10.0a2** | 0.9.12 (10-06) |
|---|---|---|---|
| dev seeds 0 / 4 / 10 | kept 8/8 | **cleared on the first reload, all 3 seeds** | cleared except seeds 4 and 10 |
| prod seed 4 | kept | **cleared** | kept |
| `/protected` unlocked by bogus token | no | no | no |

The boot delta now carries the corrected values (`token_response_json:""`, `access_token:""`, `id_token:""`,
`scopes:[]`, `protected_content:"Not logged in."`); 0.10.0a1 shipped `access_token:"ya29.bogus"` etc. The follow-up
delta repeats the same 8 vars once more (by design: they stay dirty so storage gets written) — a few hundred
redundant bytes, harmless. `drive_google_auth.py` full report `results/f003/gauth/a2-prod-seed4-report.json`:
13/14 checks ok; "token_response_json LocalStorage key discoverable" is False because a fresh load no longer
writes defaults (same as 0.9.12). Console noise (`ERR_TUNNEL_CONNECTION_FAILED` for gstatic, 403 from
accounts.google.com, `gis is not defined`) is the sandbox network + dummy client id, identical on 0.9.12 and 0.10.0a1.

Rerun:
```bash
$W/scripts/srv.sh start cv-a2dev alpha2 dev $W/src/cvstore 3223 8223 PYTHONHASHSEED=0   # and =4; prod: cv-a2prod ... prod ... 3224 3224
cd $W/cv/drivers && $NP $DRV drive_cvstore.py http://localhost:3223 /tmp/cvout a2-dev-seed0
$NP $DRV drive_cvnav.py http://localhost:3223 a2-dev-seed0
$W/scripts/srv.sh start gauth-a2dev reverify_hydration-galpha2 dev $W/src/google_auth_demo 3225 8225 PYTHONHASHSEED=4 GOOGLE_CLIENT_ID=123456789012-dummyclientid.apps.googleusercontent.com
$NP $DRV drive_gauth.py http://localhost:3225 out.json a2-dev-seed4 ; $NP $DRV drive_google_auth.py http://localhost:3225 /tmp/gout a2
```
