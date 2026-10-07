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
  `v2/f1combo` (same app, every default changed), `cvstore` (computed-var-writes-storage variants a–g, plus my new
  (i) on_load page and (j) state sent in full), `google_auth_demo` (reflex-google-auth 0.2.0 upstream demo),
  `csbox` (new: ComponentState + LocalStorage + #7461 per-instance default).
* `scripts/srv.sh` — `srv.sh start <name> <venv> <dev|prod> <src> <FP> <BP> [ENV=VAL...]` / `srv.sh stop <name>`:
  copies sources to `$W/run/<name>`, runs `$SB/envs/<venv>/bin/reflex run --env <mode> --loglevel debug` in its
  own process group with `REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=...`, refuses ports outside the range.
* `drivers/` — hydration drivers from 10-06 (hyd_driver, f1_check, f1_sync_tabs, prenav_test, f6_natural, reconnect,
  redis loop, ab_timing, latency/upgrade-delay proxies) + new `mini_choose.py`, `csbox_check.py`, `s10_react_check.py`.
* `scripts/` — also `cmp_hyd.py` (field diff of hyd_driver results across runs), `lproxy.sh`/`proxy.sh` (latency /
  upgrade-delay proxies), `trim_log.sh`, `sync_dest.sh`.
* `cv/drivers/` — cvstore/google-auth drivers from the 10-06 verifier + new `drive_cvnav.py` (client-nav path).
* `results/` — JSON/text results per section (hydapp screenshots under `results/hyd/<mode>/shots/`; `*.raw.json`
  websocket captures were not copied, they are 1–7 MB each). `trimmed/` — trimmed server logs (head, deduped
  warnings/errors with counts, HYDTRACE lines, tail). `probes/` — offline python probes. `srv.sh` — compat wrapper
  for the 10-06 reconnect drivers.

Common prefix for every driver command below:
```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/reverify_hydration
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
```

## Verdicts

| finding | verdict on 0.10.0a2 | key evidence |
|---|---|---|
| F-002 first load persists client-storage defaults (HIGH) | **FIXED** (dev + prod) | boot delta root now carries `is_hydrated_rx_state_: false`; fresh profile: nothing written (f1combo ×4, mini, hydapp s1b); returning visitor sees changed defaults (f1combo v2, mini dark, reconnect `sub-ls-NEWDEFAULT`); user choices still persisted; `sync=True` race no longer reverts |
| F-003 computed-var storage rewrite during hydration dropped (MED) | **FIXED on full load/reconnect** (all variants a–g incl. (g) plain var, cookie, session, substate, on_load page, full-sent state; seeds 0+4; dev, prod, prod+redis); reflex-google-auth bogus token cleared on all seeds | client-side navigation path (`update_vars_internal`) keeps the pre-existing hash-seed coin flip (unchanged vs 0.10.0a1/0.9.12); uncached computed var's own display stays stale until next reload (side note, still present; PR #7436 open) |
| F-008 >1 MB client-storage value → reconnect storm (MED) | **STILL BROKEN** (unchanged) | 602–654 websocket opens / 22 s, 0.72–0.78 GB uploaded, never hydrates |
| F-010 pre-CONNECT client nav runs the left page's on_load (LOW) | **STILL PRESENT** (unchanged) | prenav_test 8/8; redirect hijack at D=800 2/2 (final `/other`) |
| F-017 redis restart token loss after granian panic (LOW) | **NOT REPRODUCED** (0/9 multi-worker stops; was 1/9) | restart loop 6/6 token+state kept, no `panicked` in 7+2 logs; still granian 2.8.4 — flaky, can't call it fixed |
| hydapp s1–s13 sweep | **no new regression** (dev + prod) | every scenario identical to 0.10.0a1 except s1b (now pass) |
| timing (80 ms RTT) | alpha2 ≈ 0.10.0a1; ~170–180 ms faster than 0.9.12 | §7 |

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

## 3. Full regression sweep of the hydration probe app (s1–s13), dev + prod on 0.10.0a2

`src/hydapp` (unchanged source except the venv guard), `drivers/hyd_driver.py`. alpha2 dev 3227/8227, alpha2 prod
3228. Compared field-by-field against the saved 10-06 results with `scripts/cmp_hyd.py <a2> <alpha> <stable>`
(ignores timestamps/ids/ports).

| scenario | a2-dev | a2-prod | 0.10.0a1 dev/prod (10-06) | 0.9.12 dev/prod (10-06) | notes |
|---|---|---|---|---|---|
| s1 storage roundtrip, on_load sees restored values | pass | pass | pass/pass | pass/pass | a2 no longer has `hyd_sub_*` defaults in storage after the first load (a1 did) |
| s1b keys written by a fresh first load | **pass (none)** | **pass (none)** | anomaly/anomaly (`hyd_sub_ls`, `hyd_sub_ss`, cookie `hyd_sub_ck`) | pass/pass | F-002 fixed |
| s2 `sync=True` two tabs, tokens per tab, `window.open` dup, new ctx | pass | pass | pass | pass | `b_counter_after_close_a` differs by run timing only (driver reads before/after the click lands) |
| s3 clear storage / `remove_local_storage` | pass | pass | pass | pass | identical fields |
| s4 int Cookie set to `abc` | anomaly (same) | anomaly (same) | anomaly | anomaly | pre-existing API looseness, identical values |
| s5 300k LS ok; 1.2M LS storm | pass / **storm** | pass / **storm** | pass / storm | pass / storm | F-008 unchanged, see §4 |
| s6 redirect, bg, raising, multi, call_script, LsLoad | pass | pass | pass | pass | identical |
| s6b slow on_load superseded by link / back | pass | pass | pass | pass | a2-dev pressed Back at step 2 (a1/stable at 1) — timing; the chain stops where it was on all |
| s7 `is_hydrated` gate flips once | pass | pass | fail*/pass | pass/pass | *a1-dev driver artifact noted on 10-06 |
| s8 defaults displayed == backend, per-session ids | pass | pass | pass | pass | |
| s9 dynamic + catch-all routes, back/forward | pass | pass | pass | pass | identical traces |
| s10 click during on_load | info | info (1/3 runs lost the pre-hydration click, see below) | info | info | |
| s11 #7357 upload + nav supersedes slow on_load | pass | pass | pass | **fail** | fix still holds |
| s12 event list + failing `rx.set_value` | pass | pass | pass | pass | |
| s13 boot bytes | in 3044 / out 414 (dev), 3049/416 (prod) | | 3014/414, 3019/416 | 4711/292, 4716/296 | +30 B inbound = the explicit `"is_hydrated_rx_state_":false` now in the boot delta |

No console errors/warnings, page errors, failed requests or HTTP ≥400 in any alpha2 scenario (benign lines filtered).
Server logs: only the expected `Expected field 'State.ck_int' ...` (s4) and the intentional `ValueError: boom from on_load`
(s6) — same as 10-06. **No scenario that passed on 0.10.0a1 fails on 0.10.0a2.**

s10 anomaly (a2-prod, 1 of 3 runs in the sweep): the "always visible" button clicked before hydration never produced a
websocket event (frames in `results/hyd/a2-prod/s10.raw.json` were not kept; summary in `s10.json` run[1]): the frontend
never sent `cf_click(always)`, i.e. the click hit the prerendered HTML before React attached its root listeners. 3 more
`--only s10` repetitions (9 runs) and `drivers/s10_react_check.py` (20 runs, records `__reactProps` presence at click
time) never lost a click again (12/20 clicks landed before React attached and were still replayed by React). Classified
as browser/prerender timing, not a hydration regression; 0/6 in the 10-06 alpha/stable prod runs, so the rate is ~1/32.

Rerun:
```bash
$W/scripts/srv.sh start hyd-a2dev alpha2 dev $W/src/hydapp 3227 8227
$NP $DRV $W/drivers/hyd_driver.py --base http://localhost:3227 --label a2-dev --out $W/results/hyd/a2-dev
$W/scripts/srv.sh start hyd-a2prod alpha2 prod $W/src/hydapp 3228 3228   # --base http://localhost:3228
$DRV $W/scripts/cmp_hyd.py $W/results/hyd/a2-prod /home/user/reflex/prerelease_testing/2026-10-06/hydration/results/{alpha-prod,stable-prod}
```

## 4. F-008 (oversized client-storage value → reconnect storm) — **STILL BROKEN** (unchanged, pre-existing)

s5 with `localStorage.hyd_big = 'x'.repeat(1200000)` then reload (`results/hyd/s5_storm_summary_a2.json`):

| run | websocket opens | window | opens/s | uploaded | hydrated |
|---|---|---|---|---|---|
| a2 dev | 602 | 22.4 s | 26.9 | 721 MB | no (`H:no`, compiled defaults) |
| a2 prod | 654 | 22.1 s | 29.5 | 784 MB | no |
| a1 dev (10-06) | 866 | 22.2 s | 39.1 | 1038 MB | no |
| 0.9.12 dev (10-06) | 754 | 22.2 s | 33.9 | ~900 MB | no |

Mechanism unchanged: the 1.2 MB value rides in the socket.io CONNECT (`40/_event,{"event":{"name":"...hydrate_and_load","payload":{"vars":...` len 1200808),
Engine.IO `maxPayload` 1000000 closes it, the client reconnects immediately. No banner, no console error, no server log line.
300k chars still hydrates in 0.2–0.3 s. (The lower connect rate vs 10-06 is not a fix: the loop is the same; the machine was shared with other agents.)

## 5. F-010 (client-side navigation before the websocket CONNECT runs the left page's on_load) — **UNCHANGED**

`state.js` is byte-identical to 0.10.0a1 (`bootAuth()` at `state.js:703-708`, assigned once at mount `:728`).
* `drivers/prenav_test.py` (2 s `route_web_socket` hold), a2 prod 3228, 2 invocations × 2 runs each × 2 cases = 8/8:
  `/slow → /other`: trace `slow_load run1 step1`, `other_load#1`, `#slow-progress-other=1` lands on `/other`;
  `/items/1 → /items/2`: `item_load id=1` then `item_load id=2`. Identical to 0.10.0a1 (0.9.12: new page's on_load twice).
  Backend trace `results/f010/prenav_a2.hydtrace.log`.
* Redirect hijack with the verifier's websocket-upgrade delay proxy (`drivers/upgrade_delay_proxy.py`, D=800 ms,
  app rebuilt with `REFLEX_API_URL=http://localhost:3229`, proxy 3229→3228), `drivers/f6_natural.py ... 2 0 /redir`:
  **2/2 trace `redirect_load, item_load id=2, other_load#1`, final URL `/other`** (user clicked `/items/2`, got bounced) —
  same as 0.10.0a1 2/2; 0.9.12 stays on `/items/2`. `/items/1 → /items/2` at click delay 0 and 300 ms: 4/4 in-window,
  `item_load id=1` then `id=2` (`results/f010/f6nat_a2_d800.json`, `f6redir_a2_d800.json`).

Rerun:
```bash
$W/scripts/srv.sh start hyd-a2prod alpha2 prod $W/src/hydapp 3228 3228
$NP $DRV $W/drivers/prenav_test.py http://localhost:3228 a2-prod prenav.json 2000
$W/scripts/srv.sh stop hyd-a2prod; $W/scripts/srv.sh start hyd-a2prod alpha2 prod $W/src/hydapp 3228 3228 REFLEX_API_URL=http://localhost:3229
$W/scripts/proxy.sh start 3229 3228 800 proxy-a2-d800
$NP $DRV $W/drivers/f6_natural.py http://localhost:3229 a2-redir redir.json 2 0 /redir
$NP $DRV $W/drivers/f6_natural.py http://localhost:3229 a2-items items.json 2 0,300
$W/scripts/proxy.sh stop 3229
```

## 6. F-017 (redis prod restart lost token after a granian/pyo3 shutdown panic) — **NOT REPRODUCED** (0/9 stops)

redis-server on 8239 (`--save '' --appendonly no`), prod 9 workers (granian 2.8.4, same as before).
* `drivers/reconnect_driver.py --venv alpha2 --port 3230 --manager redis` (`results/reconnect-a2-redis/result.json`):
  kill with tab open → "Cannot connect to server" banner; restart → token same, counter 3 kept, `ls-A`/`sub-ls-S1` kept,
  boot CONNECT carries only `vars` (no hashes → full snapshot), load-count 1→2, click works (4), no panic in either log.
* `drivers/redis_restart_loop.py alpha2 3230 6`: **6/6 rounds** token same, counter kept (1→6), no leftover
  `token_manager_socket_record_*` keys, no `panicked` in any of the 7 server logs, no `new_token` frames.
  (`results/redis_restart_loop_alpha2.json`)
* Memory manager (`--manager memory --default-change`, port 3231): restart → counter 0 (state gone, by design), client
  storage re-applied, token same; **returning visitor after `HYD_SUB_LS_DEFAULT=sub-ls-NEWDEFAULT` sees
  `sub-ls-NEWDEFAULT`** (0.10.0a1: stale `sub-ls-default`; 0.9.12: NEWDEFAULT) — F-002 fixed in the full app too.
Console during outages: only the expected `WebSocket connection ... failed` lines (11 per outage).

Rerun:
```bash
cd $W/run && setsid redis-server --port 8239 --save '' --appendonly no &      # kill when done
$NP $DRV $W/drivers/reconnect_driver.py --venv alpha2 --port 3230 --manager redis --out $W/results/reconnect-a2-redis
$NP $DRV $W/drivers/redis_restart_loop.py alpha2 3230 6
$NP $DRV $W/drivers/reconnect_driver.py --venv alpha2 --port 3231 --manager memory --out $W/results/reconnect-a2-memory --default-change
```
(`$W/srv.sh` is a compat wrapper giving these 10-06 drivers the old `srv.sh start <name> <venv> <mode> <FP> <BP>` signature.)

## 7. Hydration timing, 80 ms RTT (alpha2 vs 0.10.0a1 vs 0.9.12)

`drivers/latency_proxy.py` (40 ms each way) in front of each prod server, app built with `REFLEX_API_URL` = the proxy
port; `drivers/ab_timing.py` interleaves fresh-context loads between TWO servers (warm-up excluded, n=12 each).
Pairwise to keep at most two servers up: alpha2 (3232, proxy 3233) vs 0.10.0a1 (3234/3235), then alpha2 vs 0.9.12
(3236/3237). Medians in ms since navigation start (`results/timing/*.json`):

| pair, path | alpha2 hydrated | other hydrated | Δ | alpha2 CONNECT→hydrated | other CONNECT→hydrated |
|---|---|---|---|---|---|
| a2 vs 0.10.0a1, `/` | 625.5 | 626.0 | 0 | 102 | 98 |
| a2 vs 0.10.0a1, `/other` | 673.0 | 650.5 | +22.5 | 96 | 98 |
| a2 vs 0.10.0a1, `/other` (repeat) | 683.5 | 701.0 | −17.5 | 101 | 98 |
| a2 vs 0.9.12, `/` | 791.5 | 969.5 | **−178** | 108 | 204.5 |
| a2 vs 0.9.12, `/other` | 752.0 | 921.5 | **−169.5** | 94.5 | 192 |

alpha2 = 0.10.0a1 within noise (the ±20 ms swings are in `connect_sent`, i.e. bundle load, and flip sign on repeat);
the #7064 win over 0.9.12 is intact: one RTT saved between CONNECT and hydrated, ~170–180 ms sooner end-to-end
(10-06: 158–180 ms). The machine was shared (load average 2.3 → 10 during the stable pair), which inflates absolute
numbers in the second pair; the comparison is interleaved, so the delta stands. Boot bytes: +30 B inbound vs a1 (s13).

Rerun:
```bash
$W/scripts/srv.sh start ab-a2 alpha2 prod $W/src/hydapp 3232 3232 REFLEX_API_URL=http://localhost:3233
$W/scripts/srv.sh start ab-a1 alpha  prod $W/src/hydapp 3234 3234 REFLEX_API_URL=http://localhost:3235
$W/scripts/lproxy.sh start 3233 3232 40; $W/scripts/lproxy.sh start 3235 3234 40
$NP $DRV $W/drivers/ab_timing.py http://localhost:3233 alpha2 http://localhost:3235 alpha 12 /other out.json
# then stop ab-a1 + proxy 3235; ab-st stable prod 3236 (REFLEX_API_URL=http://localhost:3237) + lproxy 3237->3236
```

## 8. Extra regression hunting around #7460 / #7461

| check | result |
|---|---|
| cvstore a–g on **alpha2 prod + redis (9 workers)**, seed 0 (`results/f003/a2-prod-redis-seed0.summary.txt`) | identical to disk-manager runs: all storage corrections reach the browser; (d)'s `fix` event and (g)'s probe see the browser value applied by the hydrate (`backend ls='bad'`) → the new `_clean()` before the snapshot does not stop the hydrated client-storage values from being persisted (`_was_touched` still set) |
| new variant **(i)**: cached cv clears LocalStorage on a page **with an on_load** (`hydrate_and_load` returns `on_load_internal`) | alpha2 dev s4 + prod/redis s0: PASS (storage `''`, on_load ran, loads=2); 0.10.0a1 dev s4: FAIL (`bad` kept) |
| new variant **(j)**: cached cv resets LocalStorage in a state the diffed boot sends **in full** (`default_factory` uuid in the same state) | alpha2: fresh load writes nothing (`v_j` absent), reload with `bad` → storage reset to `j-default`, PASS; 0.10.0a1: fresh load WRITES `v_j=j-default` (F-002) and reload keeps `bad` (F-003) |
| dev hot reload with a tab open (`drivers/hmr_desync.py`, memory manager, 3229/8229) | same as 0.10.0a1/0.9.12: reconnect boot `hydrate_and_load`, counter 3→0 matches backend, no desync. The reconnect now carries no `vars` because nothing was persisted by the first load (0.10.0a1 sent the leaked `hyd_sub_*` defaults back) |
| s8 first paint of non-deterministic defaults | unchanged: compiled build-time values (uuid, list without the lifespan mutation) for ~1 frame, then backend values; displayed == backend after hydration |
| ComponentState + browser storage + #7461 per-instance default (`src/csbox`, `drivers/csbox_check.py`, `probes/cs_storage_default_probe.py`) | **anomaly (new-feature trap, not a regression):** in `get_component`, `cls.pref = "dark"` on a var declared `rx.LocalStorage("light", name=...)` silently turns it into a plain state var on 0.10.0a2 (`_is_client_storage('pref')` False, `default='dark'` plain `str`): the user's choice is kept only in the server-side session and is lost in a new tab (`new_tab_same_browser.shown.plain = 'dark'`), nothing in localStorage, no warning. Assigning `rx.LocalStorage("dark", name=...)` (or a factory returning one) keeps storage and persists (`user-storage` survives a new tab). On 0.9.12/0.10.0a1 the assignment never reached the field at all (rendered a static `dark`, all instances shared the `box_pref` key). See ISSUE "plain default assignment drops browser storage". |

Rerun (csbox): `$W/scripts/srv.sh start csbox-a2 alpha2 dev $W/src/csbox 3238 8238; $NP $DRV $W/drivers/csbox_check.py http://localhost:3238 out.json`;
probe: `cd $W/probes && $SB/envs/alpha2/bin/python cs_storage_default_probe.py alpha2` (also `alpha`, `stable`).

## Issues / anomalies raised by this cluster

1. **F-008 still open** (MEDIUM, pre-existing, not a regression): see §4. Repro: hydapp prod,
   `localStorage.setItem('hyd_big','x'.repeat(1200000))`, reload → endless reconnect loop (`hyd_driver.py --only s5`).
2. **F-010 still open** (LOW, pre-existing race, alpha-only redirect-hijack symptom): see §5.
3. **Uncached computed var shows the value it returned during hydration until the next full reload** (LOW, side
   note of F-003, still present): cvstore variant (b); PR #7436 (open) is the related fix. Only reachable when a
   value changes during the hydrate event itself (a computed var that writes state).
4. **Client-side-navigation path still drops computed-var writes depending on PYTHONHASHSEED** (LOW, pre-existing on
   0.9.12/0.10.0a1; #7460 only fixed `hydrate_and_load`): `cv/drivers/drive_cvnav.py`, seed 0 FAIL / seed 4 PASS,
   (g) always FAIL. Any ordinary event whose computed var writes a var that wasn't already dirty has the same gap.
5. **New-feature trap (#7461): plain default assignment drops browser storage** (LOW, not a regression):
   `cls.pref = "dark"` in `ComponentState.get_component` on an `rx.LocalStorage` var makes it a non-persisted
   state var silently (§8). Suggest: keep the storage settings (wrap the value in the declared storage type) or
   raise/warn; at least document "assign `rx.LocalStorage(...)` to keep storage".
6. s10 pre-hydration click lost once in 32 prod runs (anomaly, browser/prerender timing, §3) — not attributed to Reflex.
7. Residual from 0.10.0a1 (expected, not testable from here without a deployed a1 history): browsers that visited a
   0.10.0a1 deployment keep the leaked defaults in localStorage/cookies; 0.10.0a2 cannot distinguish them from user
   choices, so those users keep the old defaults after upgrading.

## Not covered
* Build-env ≠ runtime-env default mismatch via `reflex export` + separately started backend (whole-list hash mismatch path).
* F-017 frequency beyond 9 stops; bfcache; other browsers; real mobile network shaping.
* 0.9.12/0.10.0a1 were not re-run for every table cell — baselines for the cvstore variant table and hydapp sweep are
  the saved 10-06 results; I re-ran 0.10.0a1 (cvstore a/b/g/i/j + client-nav, timing) and 0.9.12 (client-nav, csbox,
  timing) where the comparison mattered.

## Environment notes
* `$SB/envs/reverify_hydration-galpha2`: `uv --no-config venv --python 3.12` then
  `uv --no-config pip install --prerelease=allow 'reflex==0.10.0a2' 'reflex-google-auth==0.2.0' 'google-api-python-client>=2.184.0' 'pydantic<2.14'`
  (cwd `$SB`). No `[db]` extra, so the greenlet issue (N-001) does not apply.
* All servers, proxies and redis were stopped at the end (`lsof` shows no listeners in 3220-3239/8220-8239).
