# Hydration, browser storage and router fixtures

Reusable apps, drivers and runners for client-storage boot/hydration, `sync=True` LocalStorage cross-tab behaviour,
on_load / router data and the credential-header filter, reconnect / Redis restart / pre-connect navigation, and the
storage-level checks of reflex-local-auth / reflex-google-auth. Curated from the 0.10.0 campaigns (a5
`a5_hydration_router`, a4 `a4_hydration` + `verify_hydration`, a3 `a3_hydration` incl. its verifier, a2
`reverify_hydration`, a1 follow-up `hydration`); one up-to-date copy of each fixture. Full demo flows of the auth packages
live in the `upgrade` area; this area keeps the storage-level drivers.

Baseline: reflex **0.10.0** (released, venv `rel`) is the new previous stable. "Expected" below is what 0.10.0a5 did in
the a5 pass (0.10.0 = a5 for this area, see "Validated on 0.10.0"); rows marked **(re-validated)** were re-run on the
released 0.10.0 while curating.

## Layout
```
src/<app>/            Reflex apps (rxconfig.py + package + assets); srv.sh copies one into $W/run/<name> and runs it there
  bootecho  csbox  cvstore  f1combo  v2/f1combo  f1plain  google_auth_demo  h4mix  hydapp  local_auth_demo
  mini_writeback  rtr  syncstamp  vhsync
drivers/              Playwright drivers (driver venv), proxies, helpers (hydcommon.py, waitsrv.py)
drivers/tp/           auth-package drivers (local-auth 38-check flow, google-auth bogus token, fresh-profile storage)
cv/drivers/           cvstore (F-003) drivers + frame decoder
vh/drivers, vh/scripts  the independent verifier's 100 ms RTT multi-tab drivers (raw CDP real background tabs + Playwright)
probes/               offline python probe (no server)
expected/             small expected-output files the runners diff against (cvstore summaries)
scripts/              env.sh (sourced by everything), srv.sh, run_*.sh runners, run_area.sh, summarisers
```

## Environment
| var | meaning | default |
|---|---|---|
| `SB` | scratch root holding `envs/<venv>` | **required** |
| `WORK` | work dir for run dirs (`run/`), logs, results | `$SB/apps/hydration` |
| `NEW` | venv of the version under test (`run_area.sh`) | required by `run_area.sh` |
| `PREV` | previous release venv (today `rel` = reflex[db]==0.10.0) | optional |
| `CTRL_F002` / `CTRL_STORM` / `CTRL_RTR` | positive controls: 0.10.0a1 (F-002/F-003), 0.10.0a3 (A3-11/A3-12), 0.10.0a4 (#7360 leaks) | optional (`alpha`, `a3`, `a4` exist under today's `$SB/envs`) |
| `TP_NEW` | auth-package venv for NEW (`scripts/build_venvs.sh`) | optional |
| `DRV_VENV` | driver venv name (playwright, httpx, websockets) | `driver` |
| `REDIS_PORT` / `VREDIS_PORT` | redis for prod+Redis runs / vmatrix prodredis | `8149` / `8669` |
| `PORT_RANGES` | ports srv.sh accepts | `3140-3159 8140-8159 3660-3679 8660-8679` |

Every runner positional `<venv>` is a name under `$SB/envs`; the apps assert `reflex.__file__` contains `/envs/<venv>/`
(srv.sh exports `RVH_VENV`/`VERIFY_VENV`/`VH_VENV`), the drivers assert `/envs/$DRV_VENV/`. Runners `cd $WORK` first, so
nothing runs inside a checkout; client-side commands get `NO_PROXY`, servers never do. One app server at a time; every
runner stops what it starts (servers, proxies, redis). Chromium: `/opt/pw-browsers/chromium`. Needs `redis-server`,
`lsof`, and `xvfb-run` for the raw-CDP verifier scenarios.

**Ports** (this area): 3140-3159 / 8140-8159 (explorer runners; redis 8149) and 3660-3679 / 8660-8679 (race / verifier:
3660/8660 app, 8661 or 3663 latency proxy, 8669 redis, 8670 CDP). Defaults used in the commands below:
F-002 prod 3140, dev 3142/8142, prod+Redis 3144; cvstore/storm/stamp/rtr dev 3142/8142 (rtr header proxy 8143), prod 3144
(rtr proxy 3145, prod+Redis 3146/3147); h4mix 3146/8146; hydapp 3147/8147 or prod 3148 (+3149 proxy); reconnect 3150/3151;
csbox 3152/8152, mini 3141; local-auth 3153/8153.

**Venvs**: `$SB/envs/<NEW>` (reflex[db]), `$SB/envs/driver`; optional controls; auth venv:
`scripts/build_venvs.sh hydration-tp-new 'reflex[db]==<ver>' 'reflex-base==<ver>'` (PyPI only, cwd `$SB`).

## How to run the whole area
```bash
export SB=/path/to/scratchpad              # holds envs/<venv>, envs/driver
export WORK=$SB/apps/hydration NEW=<venv under test>
F=<this directory>
# for the direct driver calls in the table:
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python; cd $WORK
# optional: export PREV=rel CTRL_F002=alpha CTRL_STORM=a3 CTRL_RTR=a4 TP_NEW=hydration-tp-new
$F/scripts/run_area.sh quick 2>&1 | tee $WORK/area_quick.txt     # ~10 min: probe, F-002, F-003, A3-11, A3-12, #7360 dev
$F/scripts/run_area.sh full  2>&1 | tee $WORK/area_full.txt      # + prod/Redis legs and every other fixture (~2 h)
rm -rf $WORK/run/*/.web                                          # when done (node_modules)
```
Pass criteria: the "Expected" column below. Run a positive control first when a finding is re-verified (the control
must fail the way the record says, or the harness is not detecting anything).

## Fixtures
Runner names (`run_*.sh`, `srv.sh`, `lproxy.sh`, `vmatrix.sh`) are in `$F/scripts/`; driver paths are relative to `$F`.

| path | exercises | findings | run | expected on 0.10.0 | quirks |
|---|---|---|---|---|---|
| `src/f1combo`, `src/v2/f1combo`, `drivers/f1_check.py`, `drivers/f1_sync_tabs.py`, `scripts/run_f002.sh` | first page load must write NO client-storage default (plain, substate, uuid, clock var, ComponentState storage, cookie options, sync=True); returning visitor after every default changed (v2 build) sees the new defaults; sync=True two-tab race with one tab's socket held 2.5 s | F-002 (#7460), N-032 boot mechanism | `run_f002.sh $NEW prod new-prod 3140 3140`; dev `... dev new-dev 3142 8142`; prod+Redis: `redis-server --port 8149 --save '' --appendonly no &` then `... prod new-prodredis 3144 3144 REFLEX_REDIS_URL=redis://localhost:8149` (or `run_area.sh full`) | fresh x2: only `theme` (dev also `last_compiled_theme`); returning v2 shows `*-dark-v2` / `wu-sync-v2`; sync tabs converge on `sync-from-tabA` **(re-validated, prod)**. Control 0.10.0a1 writes LS `cu_ls,wt_ls,wu_ls,wu_sync`, SS `cu_ss,wu_ss`, cookies `wu_ck,cu_ck` | `ws-ls` stays `ws-light` in v2 (not changed in v2); prod `/favicon.ico` 404 benign |
| `src/f1plain` | minimal one-state F-002 app (theme/consent/tab) | F-002 | `srv.sh start f1p $NEW prod $F/src/f1plain 3140 3140`; `f1_check.py http://localhost:3140/ - st.json out.json theme,consent,tab` | nothing written on a fresh profile | — |
| `src/mini_writeback`, `drivers/mini_writeback_check.py`, `drivers/mini_choose.py` + `src/csbox`, `drivers/csbox_check.py`, `scripts/run_csbox_mini.sh` | mini: fresh profile writes nothing; restart with `MINI_THEME_DEFAULT=dark` -> returning visitor who never chose sees `dark`; a user choice (`blue`, cookie `mini_consent=granted`) persists. csbox: ComponentState + LocalStorage per-instance defaults via `__fields__[...].set_default` | F-002, #7461, N-005, A3-02, A3-03 | `run_csbox_mini.sh $NEW` | mini as described **(re-validated)**. csbox **(fixture changed for 0.10; re-validated)**: `set_default("dark")` makes the var ordinary (documented, not persisted in a new tab); `set_default(rx.LocalStorage(...))` persists under its own key; the undeclared box keeps `box_pref` | the app used `cls.pref = ...`, rejected since 0.10.0a4 (#7516) |
| `probes/cs_storage_default_probe.py` | offline: which per-instance default patterns keep a var browser storage | #7461, #7516, N-005, A3-02 | `$SB/envs/$NEW/bin/python -I $F/probes/cs_storage_default_probe.py $NEW` (from `$WORK`) | `assign_*`: #7516 TypeError naming `__fields__[...].set_default`; `field_plain`/`field_none`: ordinary var; `field_storage`: LocalStorage `box_pref_dark` **(re-validated)** | — |
| `src/cvstore`, `cv/drivers/drive_cvstore.py`, `drive_cvnav.py`, `decode_frames.py`, `drive_diag.py`, `expected/cvstore_*.summary.txt`, `scripts/run_cv.sh` | computed var that rewrites a LocalStorage / Cookie / SessionStorage / substate / plain var during hydration: variants a-j (a cached cv, b uncached cv, c on_load, d event, e cookie/session, f substate, g different plain var, i page with on_load, j state sent in full); `NAV=1` adds the client-navigation path | F-003 (#7460), N-015 (client-nav path seed-dependent, pre-existing), N-016 (uncached cv display stale until reload, pre-existing; variant b) | `run_cv.sh $NEW dev new-dev-s4 3142 8142 all PYTHONHASHSEED=4` (also seed 0, prod `3144 3144`); control: `EXPECT=$F/expected/cvstore_ctrl_a1_dev_abg.summary.txt run_cv.sh $CTRL_F002 dev ctrl-s4 3142 8142 "a b g" PYTHONHASHSEED=4` | prints `CVSTORE MATCHES cvstore_<mode>.summary.txt`: `[l='']` everywhere, b's `check=cleared-by-uncached-cv` until reload2 (N-016) **(re-validated, dev s4)**; control a1 `reload [l='bad']` for a/b/g | pass variants space-separated (`"a b g"`, not `a,b,g` -> KeyError); prod summary adds a favicon 404 line |
| `src/google_auth_demo`, `drivers/tp/drive_gauth.py`, `drive_google_auth.py`, `scripts/run_gauth.sh` | reflex-google-auth 0.2.0 demo with a dummy client id: a bogus `token_response_json` in localStorage must be cleared on the first reload and `/protected` stays locked (F-003 through a real package) | F-003 | `run_gauth.sh $TP_NEW dev new-dev-s4 3142 8142 4 [full]` | cleared (`""`) on the first reload, after nav and reload2; locked **(re-validated, dev s4)**. 0.9.12 control keeps `BOGUS` | real Google login impossible in the sandbox; console noise (gstatic tunnel, accounts.google.com 403, `gis is not defined`) is the network |
| `src/local_auth_demo`, `drivers/tp/drive_local_auth.py`, `drivers/la_storage.py`, `drivers/tp/drive_fresh_storage.py`, `scripts/run_la.sh` | reflex-local-auth 0.5.0: 38-check flow (register, login, guard redirect + `redirect_to`, reload, 2nd tab, fresh ctx, logout, expiry) + 14 storage checks (fresh profile writes nothing, `_auth_token` stored, reload / 2nd tab logged in, cross-tab logout after reload, bogus token -> /login, console clean); `drive_fresh_storage.py <base> <label> <out> <path>...` = what a fresh profile has after visiting pages | storage side of F-002, #7493 echo | `run_la.sh $TP_NEW dev new-dev 3153 8153` (prod `3152 3152`) | 36/38 + 14/14 **(re-validated, dev)**; the 2 fails = known demo pitfall `/tp-strict-register` (`_validate_fields` override), identical a3..a5 | after logout `_auth_token` keeps the old token (server deletes the session; all versions) |
| `src/bootecho`, `drivers/bootecho_check.py`, `drivers/cookie_raw.py`, `scripts/run_be.sh` | #7493 boot echo: fresh writes nothing; `get_delta` overrides see browser values once (sanitising `Guard` override reaches storage); computed vars over storage correct at first H:yes; on_load value wins; cookie max_age renewed at boot; raw cookies set outside reflex re-encoded | #7493, N-032 mechanism, A3-13 (storage cvs run twice per load, perf) | `run_be.sh $NEW dev new-dev 3142 8142` (prod `3144 3144`); `cookie_raw.py http://localhost:3142 out.json` | as a4/a5: override sees browser values once; `be_tok=bad-xyz` -> `""`; 4 inbound frames / 2 deltas on a returning boot | — |
| `src/bootecho`, `drivers/sync_race.py`, `scripts/run_storm.sh`, `summ_s.py`, `summ_storm.py` | A3-11 explorer series: tab0 + 6 tabs load concurrently while tab0 changes the synced value 5x (Part S); Part R: tab B's inbound messages held 2.5 s while A changes the value. Storm = not converged or >50 frames in the 2 s quiet window | A3-11 (fixed by #7505) | `run_storm.sh $NEW dev 3 3142 8142 S 6` then `$DRV $F/scripts/summ_s.py $WORK/results/sync/storm_${NEW}_dev_S_6_` (prod `3144 3144`; Part R: `R`) | 0 storms; all 7 tabs + localStorage on `s5`; 47-93 frames, 0 in the quiet window **(re-validated, dev)**. Control a3: 3/4 dev, 3/3 prod storm | the runner needs `summ_s.py` for the verdict (its own output is per-run JSON lines) |
| `src/syncstamp`, `drivers/stamp_storm.py`, `scripts/run_stamp2.sh` | A3-12: `/stamp`'s on_load writes a per-tab value into a sync=True var, N tabs load at once (session restore); `/same` = control | A3-12 (fixed by #7505) | `run_stamp2.sh $NEW dev 3142 8142 3 1 6` (prod `3144 3144`) | 0 storms, 80-160 frames total, 0 per 5 s afterwards, all tabs on ONE value; `/same` quiet **(re-validated, dev)**. Control a3: 2/2 storm (60k-130k frames / 5 s) | prints the compiled `state.js` md5 (0.10.0a4/a5: `b7915eda`) |
| `src/vhsync`, `vh/drivers/vh_rawcdp.py`, `vh_tabs.py`, `vis_probe.py`, `vh/scripts/{vraw,vrun}.sh`, `vtrigger.py`, `vsumm.py`, `vtrace.py`, `vrevert.py`, `scripts/vmatrix.sh`, `scripts/lproxy.sh`, `drivers/latency_proxy.py` | the independent verifier's A3-11 / A3-12 scenarios at 100 ms RTT: stock headful Chromium over raw CDP with REAL background tabs (hidden, throttled timers) + Playwright restore of 7 tabs with one click; 6 background tabs stamping `/doc/<slug>`; 4 stamping tabs + a dev backend hot reload. `vtrigger.py` shows whether a tab booted across the click (race hit) | A3-11, A3-12, #7505 | `vmatrix.sh $NEW dev 3 3` / `prod` / `prodredis` | 0 storms in every family, all tabs + localStorage on the user's value / one slug, race hit 3/3 (a4 pass). Control a3: storms 2/3-3/3 | needs `xvfb-run`; CDP port 8670; Playwright `write EPIPE` crashes only happen during storms (count as unknown) |
| `src/h4mix`, `drivers/h4_drive.py`, `drivers/capture_selftest.py`, `scripts/run_h4.sh` | #7505 regression hunt, every storage flavour in one app: C1 fresh writes, C2 sync=False + review bug, C3 sync=True follow / alternation, C4 sanitising `get_delta` override, C6 SessionStorage per tab, C7 cookie max_age renewal, C10 on_load write, C11 background task / yield chain / `""` / unicode / 6402-char values, C15 ComponentState, C20 returning-visitor writes, C21 `rx.remove_local_storage` / `clear_local_storage`, C23 two vars on one key | #7505, A4-03 (C3 gap0), C21 null sync (pre-existing) | `run_h4.sh $NEW dev new-dev 3146 8146 -` (prod `3148 3148`; subset: 6th arg `C1,C3`) | driver SUMMARY 39/39 **(re-validated, dev)**; C3 `alternate_gap0` converges on `c8` (A4-03, by design, counted as pass); C21: removed key stays removed, other tab keeps showing the old value and the server log gets `TypeError: object of type 'NoneType' has no len()` from the computed var (pre-existing, unfiled) | `h4mix` is the verifier's h4v superset (adds `#probe`, `/st/[slug]`, `/norm`, `/normslow`, `#bgloop`, `#slow9`, H4TRACE `ts`) |
| `src/h4mix`, `drivers/b2b_probe.py`, `drivers/race.py`, `drivers/bootwin.py`, `scripts/run_race.sh` | A4-03 two-tab write ordering: reporter's zero-gap alternation, gap sweep (0-150 ms), on_load / background-task races, `/norm` boot window (a booting tab's on_load re-assigns the stored value while another tab writes); optional 100 ms RTT proxy | A4-03 (LOW, by design: consistent last-storage-writer-wins; earlier write wins within ~1 RTT) | `run_race.sh $NEW new-dev 3660 8660 - 3`; at 100 ms RTT: `run_race.sh $NEW new-rtt 3660 8660 8661 3` | every run consistent (tabs = localStorage = backend), 0 storms; localhost gap0 c8 ~2/3, gap>=10 c9; RTT100 gap 20-80 c8, 150+ c9; `/norm` offsets 0-4 ms may end on the older `c5` **(re-validated, localhost, 2 reps)** | the CDP `freeze:` scenario of race.py is ineffective in headless Chromium |
| `src/rtr`, `drivers/rtr_drive.py`, `drivers/hdr_proxy.py`, `drivers/cmp_rtr.py`, `scripts/run_rtr.sh`, `run_rtr_redis.sh` | #7360: backend `self.router` in every on_load flavour (single, list, chain, background, redirect, redirect chain, dynamic, catch-all, frontend events from on_load) and after a dev hot reload; frontend rendering of router fields; credential headers injected by `hdr_proxy.py` (Authorization, Proxy-Authorization, Cf-Access-Jwt-Assertion, X-Forwarded-Access-Token, X-Auth-Request-Access-Token, X-Amzn-Oidc-*, X-Goog-Iap-Jwt-Assertion) + plain and HttpOnly cookie; scans every websocket frame, document, DOM, console for the 10 secrets | #7360 (security), reflex#7521 (dup cookie, pre-existing) | `run_rtr.sh $NEW dev new-dev 3142 8142 8143`; prod `run_rtr.sh $NEW prod new-prod 3144 3144 3145`; `run_rtr_redis.sh $NEW new-prodredis`; compare `$DRV $F/drivers/cmp_rtr.py $WORK/results/rtr/<A>.json $WORK/results/rtr/<B>.json` | 37 steps dev / 35 prod; **0 secrets** in received/sent frames, documents, DOM, console; backend still sees cookies and auth headers; `headers.cookie` renders `""`; cookie deprecation only in the server log **(re-validated, dev)**. Control a4 leaks all 10 secrets (17-21 frames) | Chromium does not send Playwright `extra_http_headers` on the websocket upgrade, hence the proxy; `NORELOAD=1` skips the hot-reload step |
| `src/rtr` minus `__init__.py`, `drivers/dbg_console.py`, `scripts/run_noinit.sh` | an app package without `__init__.py` | pre-existing (0.9.12-0.10.0a5), not filed: "no dispatch function" | `run_noinit.sh $NEW` | while unfixed: console `Cannot process state update: no dispatch function for substate(s) "reflex___state____state.rtr____other", ...`; is_hydrated stays false **(re-validated: still present on 0.10.0)**. A fix = no such error | `reflex init` creates the file; only hand-made layouts hit it |
| `src/hydapp`, `drivers/hyd_driver.py`, `scripts/cmp_hyd.py`, `drivers/s10_react_check.py`, `scripts/run_hyd.sh` | 16-page probe app, scenarios s1-s13 (see run_hyd.sh header); s5 = 300k chars ok / 1.2 MB LocalStorage value | F-008 (>1 MB storage reconnect storm, MED pre-existing), s4 int Cookie `abc` anomaly, s10 pre-hydration click, #7357 (s11) | `run_hyd.sh $NEW prod new-prod 3148 3148` (dev `3147 8147`; `--only`: 6th arg `s5`); diff two runs `$DRV $F/scripts/cmp_hyd.py <dirA> <dirB>` | all pass except s4 anomaly (pre-existing), s10 info; **s5 1.2 MB: still a storm** (600-870 websocket opens / 22 s, ~0.7-1 GB uploaded, never hydrates, no error shown) until F-008 is fixed; run_hyd.sh prints an `F-008 s5 1.2MB:` verdict line **(re-validated s1+s5, prod: 610 opens, not hydrated)** | hyd_driver reports s5 `pass` even while the 1.2 MB leg storms (read the verdict line); s10 lost a pre-hydration click ~1/32 prod runs (browser/prerender timing) |
| `src/hydapp`, `drivers/prenav_test.py`, `preconnect_click.py`, `f6_natural.py`, `prenav_natural.py`, `upgrade_delay_proxy.py`, `scripts/proxy.sh`, `scripts/summ.py`, `scripts/run_prenav.sh` | client-side navigation BEFORE the websocket CONNECT (socket held 2 s); click before connect; natural window via a websocket-upgrade delay proxy (D=800 ms) incl. the `/redir` hijack | F-010 (LOW, pre-existing since 0.10.0a1) | `run_prenav.sh $NEW new 3148 3149`; `prenav_natural.py <proxied base> <label> <runs> <out>` behind `lproxy.sh` | unchanged since a1: `/slow -> /other` runs the LEFT page's on_load (`slow_load run1 step1`, then `other_load`); `/items/1 -> /items/2`: id=1 then id=2; `/redir` hijack (`f6_natural.py ... /redir "#nav-item2" "*"`) 2/2 ends on `/other`; preconnect click processed after on_load 3/3 **(re-validated)** | 0.9.12 ran the new page's on_load twice instead |
| `src/hydapp`, `drivers/reconnect_driver.py`, `redis_restart_loop.py`, `token_leak_check.py`, `scripts/srv_hydapp.sh`, `scripts/run_reconnect.sh` | kill the prod server with a tab open (banner), restart: token / counter / storage kept (Redis); N stop/start rounds; leftover `token_manager_socket_record_*` keys; memory manager + changed default (returning visitor sees the new default) | F-017 (granian/pyo3 shutdown panic -> token record left -> `new_token`, state lost; LOW, pre-existing, flaky: a1 1/9, a2 0/9, a3 0/5, 0.10.0 1/9 stops), F-002 | `run_reconnect.sh $NEW 3150 3151 3` | Redis: token same, counter kept, 0 leftover keys, no `panicked`; memory: state reset by design, `sub-ls-NEWDEFAULT`. **Re-validated: reconnect + memory as expected, but F-017 reproduced in 1 of 2 restart-loop rounds** (see Validated) | 11 `WebSocket connection ... failed` console lines per outage (expected) |
| `src/hydapp`, `drivers/hmr_desync.py` | dev hot reload with a tab open (memory manager): UI resyncs with the backend | — | `srv.sh start hmr $NEW dev $F/src/hydapp 3147 8147 REFLEX_STATE_MANAGER_MODE=memory`; `$NP $DRV $F/drivers/hmr_desync.py http://localhost:3147 $WORK/run/hmr/hydapp/hydapp.py out.json` | reconnect boot `hydrate_and_load`, counter 3 -> 0 = backend, no desync | edits the RUN copy only |
| `src/hydapp`, `drivers/ab_timing.py`, `drivers/latency_proxy.py` | interleaved A/B first-load timing of two prod servers behind 80 ms RTT proxies | #7064 (one RTT saved vs 0.9.12) | `srv.sh start ab-new $NEW prod $F/src/hydapp 3150 3150 REFLEX_API_URL=http://localhost:3151` + `lproxy.sh start 3151 3150 40`, same for PREV on 3152/3153; `ab_timing.py http://localhost:3151 new http://localhost:3153 prev 12 /other out.json` | NEW within noise of PREV (both 0.10); ~170-180 ms faster than 0.9.12 | runs two servers at once (only exception to one-at-a-time; keep it short) |

Other helpers: `drivers/hydcommon.py` (shared Playwright helpers), `drivers/waitsrv.py` (poll URLs until 200),
`drivers/dbg_console.py` (console/page errors of one load), `scripts/trim_log.sh` (dedupe a server log),
`scripts/srv.sh` (start/stop/sync any app), `scripts/build_venvs.sh` (auth venvs), `scripts/run_area.sh`.

## Validated on 0.10.0
Run while curating (2026-10-09) with the reorganised copies and the commands above, `NEW=rel` (reflex 0.10.0 /
reflex-base 0.10.0 from PyPI), `SB=$SB WORK=$SB/apps/compact_hydration`, driver venv `driver`, one server at a time.

Static checks: `python3 -I -m py_compile` of every `.py` and `bash -n` of every `.sh` (from the work dir): clean.

| run (command as documented) | result on 0.10.0 | vs a5 record |
|---|---|---|
| `probes/cs_storage_default_probe.py rel` | `assign_*`: #7516 TypeError; `field_plain`/`field_none`: ordinary var; `field_storage`: LocalStorage `box_pref_dark` | **fixture changed**: the a2-era probe and the `csbox` app used `cls.pref = ...`, which 0.10.0a4+ rejects on purpose (#7516); both now use `__fields__[...].set_default` |
| `run_f002.sh rel prod rel-prod 3140 3140` (F-002) | fresh x2 and same-build returning visitor: only `theme=system` written; boot root `is_hydrated:false` then `true`; sync tabs: A, B2 and localStorage `sync-from-tabA`; v2 returning + v2 fresh: `pl/wu/cs/cu/wt-dark-v2`, `wu-sync-v2` | = a5 (45 s incl. build) |
| `run_cv.sh rel dev rel-dev-s4 3142 8142 all PYTHONHASHSEED=4` (F-003) | `CVSTORE MATCHES cvstore_dev.summary.txt` (variants a-j line for line; b keeps `check=cleared-by-uncached-cv` until reload2 = N-016) | = a5 = a3 baseline |
| `run_storm.sh rel dev 3 3142 8142 S 6` + `summ_s.py` (A3-11) | **storms 0/3**; all 7 tabs + localStorage `s5`; 55-63 frames, 0 in the quiet window | = a5 (0/5) |
| `run_stamp2.sh rel dev 3142 8142 3 1 6` (A3-12) | **0/3 storm**, 97-109 frames, one value in all 6 tabs, 0 frames per 5 s afterwards; `/same` quiet (48 frames); `state.js` md5 `b7915eda` (same template as a4/a5) | = a5 (0/3) |
| `run_rtr.sh rel dev rel-dev 3142 8142 8143` (#7360) | **0 secrets** for all 10 values in received frames / sent frames / documents / console / the `/front` DOM (257 in, 111 out frames, 34 sockets, 18 proxied upgrades); console only `/favicon.ico` 404; `cmp_rtr.py <a5dev.json from the archive> rel-dev.json`: `steps A=37 B=37 log/url diffs=0`, reconnect identical | = a5 |
| `run_noinit.sh rel` | console `Cannot process state update: no dispatch function for substate(s) "reflex___state____state.rtr____other", "reflex___state____state.rtr___rs"` | **still present** (pre-existing) |
| `run_csbox_mini.sh rel` | csbox: fresh writes nothing; choices persist across reload; new tab: undeclared box `user-none` (key `box_pref`), storage box `user-storage` (key `box_pref_storage`), plain box back to `dark` (ordinary var, documented); mini: fresh `{}`, choose -> `blue` + cookie `granted`, returning visitor after `MINI_THEME_DEFAULT=dark` sees `dark`, the chooser keeps `blue` | as designed |
| `run_h4.sh rel dev rel-dev 3146 8146 -` (#7505 hunt, merged h4mix) | `SUMMARY 39/39 pass`; C3 gap0 `c8` (A4-03), gap40/120 `c9`; C7 cookie expiry +4 s; C20 writes only `h4_nos`, `h4_sanns`; C21 server log `TypeError: object of type 'NoneType' has no len()` (pre-existing) | = a4/a5 |
| `run_race.sh rel rel-dev 3660 8660 - 2` (A4-03) | b2b alt `c8` 2/2; gap0 `c8` 2/2, gap 10-150 `c9`; pwalt `c8`; onload:0 one value; bg:570 `c9`; every run consistent, 0 storms; `/norm` 6 offsets: 1 lost (`c5`), all consistent | = a4 verifier (localhost) |
| `build_venvs.sh compact-hydration-tp-rel 'reflex[db]==0.10.0' 'reflex-base==0.10.0'`, `run_la.sh compact-hydration-tp-rel dev rel-dev 3153 8153` | local-auth 36/38 (the 2 known `/tp-strict-register` fails), `la_storage.py` 14/14; `auth_token` 2x in the reload's inbound deltas | = a5 |
| `run_gauth.sh compact-hydration-tp-rel dev rel-dev-s4 3142 8142 4` | fresh keys only `theme`, `last_compiled_theme`; bogus token cleared on the first reload, after index / client nav / reload2; protected locked | = a5 |
| `run_hyd.sh rel prod rel-prod 3148 3148 s1,s5` | s1 pass; s5: 300k hydrated in 0.22 s; **1.2 MB: 610 websocket opens, never hydrated** | F-008 **still present** (pre-existing) |
| `run_prenav.sh rel rel 3148 3149` (F-010) | `/slow -> /other`: trace `slow_load run1 step1`, `other_load#1` (2/2); `/items/1 -> /items/2`: id=1 then id=2 (2/2); preconnect click after load 3/3; delay proxy items cd 0/300: 4/4 in window, id=1 then id=2; `/redir` hijack 2/2: trace `redirect_load, item_load id=2, other_load#1`, user clicked `/items/2` and ends on `/other` (the first chain run without `"#nav-item2" "*"` timed out waiting for `/items/2`: the runner now passes them) | F-010 **still present** (pre-existing) |
| `run_reconnect.sh rel 3150 3151 2` | reconnect redis: banner while down, token same, counter 3 kept, storage kept, click works; memory `--default-change`: returning visitor `sub-ls-NEWDEFAULT`; token_leak_check 2/2 no leftover keys; **redis_restart_loop round 1 of 2: granian/pyo3 shutdown panic (`Cannot drop pointer into Python heap without the thread being attached`, granian 2.8.4), the tab's `token_manager_socket_record` key left in Redis, restart sends `new_token`, counter 2 -> 0 (state lost)** | **F-017 reproduced** (1 panic in 9 prod+Redis stops; a1 1/9, a2 0/9, a3 0/5) |
| `NEW=rel run_area.sh quick` (the recipe itself, 8.5 min) | probe as above; F-002 prod as above; `CVSTORE MATCHES cvstore_dev.summary.txt`; storm 3/3 converged on `s5`; stamp 0/2 storm + `/same` quiet; rtr 0 secrets (257 in / 111 out frames) | = the individual runs |
| `run_be.sh rel dev rel-dev 3142 8142` (#7493) | fresh `/` writes nothing (`/onload` only its on_load values); returning reload: overrides called Prefs 3 / SubPrefs 1 / Guard 1, 4 frames / 2 deltas; `be_tok=bad-xyz` -> `""`; on_load value wins; cookies with max_age slide 5-8 s | = a3/a4 |
| `vmatrix.sh rel dev 1 1` (100 ms RTT verifier families) | raw CDP 3 background tabs + 1 click: no storm, all tabs + localStorage `red` (visibility visible/hidden/hidden, bg timers 2 Hz); Playwright restore 7 + click: no storm, all `red`; raw CDP 6 stamping background tabs 2/2: no storm, one slug (`d2`, `d3`); 4 stamping tabs + dev hot reload 2/2: 8 frames in the reload window then 0, one slug. `vtrigger.py`: the booting tab read `red` (it booted after the click), i.e. the stale-boot race itself was not hit in this single run (a4 hit it 3/3 with 3 runs) | = a4 (0 storms); needs more runs to re-hit the race |

Procedural: the first validation chain edited `run_cv.sh` while it was executing; bash re-read the changed file, skipped the
server stop, and the next runner (storm) silently drove the still-running cvstore server. That is why `srv.sh start` now
refuses a port that is already listening (exit 5) and every runner aborts when the start fails; the storm series was re-run
cleanly afterwards (the numbers above). Don't edit a runner while it runs.
Not re-run while curating (expected values are the a5/a4 records): the prod and prod+Redis legs of rtr / storm / stamp /
cvstore / F-002, `vmatrix.sh prod|prodredis`, the 100 ms RTT `run_race.sh`, `hmr_desync.py`, `ab_timing.py`, `f1plain`,
`cookie_raw.py`, and the positive controls (a1 / a3 / a4 venvs). Work dir used: `$SB/apps/compact_hydration`
(`.web` dirs deleted afterwards).

## Dropped (and why)
* Campaign batch scripts (`p2_*.sh`, `batch2.sh`, `p2_chain.sh`, `sync_dest.sh`, `bisect.sh`), the compat `srv.sh` at the
  item root, `vsrv.sh` / `vlproxy.sh` (merged into `scripts/srv.sh` / `lproxy.sh`), `run_stamp.sh` (superseded by
  `run_stamp2.sh`), `cv/bin/*` (superseded by `run_cv.sh` / `run_gauth.sh`), `scripts/mini.sh` (-> `run_csbox_mini.sh`).
* `pr7505/scripts/*` (pointed at the PR worktree; the published-venv equivalents are `run_storm.sh`, `run_stamp2.sh`,
  `vmatrix.sh`), `vh/scripts/proto_patch_statejs.py` (patched the a3 `state.js`; the fix landed in #7505),
  `vh/scripts/vtable.py` (campaign-specific summary), `cv/drivers/drive_tp_ws.py` (its tp_patterns app is not here),
  the duplicate `tpdrive.py`, `src_noinit/` (generated by `run_noinit.sh`), the separate `h4v` app (folded into `h4mix`).
* All results, trimmed logs, frame dumps, screenshots, traces; the 0.9.x router/routing/bg_rehydrate items (routerlab
  #7068, routing #6593/#6790/#6953, #7072/#7073 state-expiry rehydrate) — their router-field and on_load coverage is
  superseded by `src/rtr` + `hydapp`; state-expiry rehydrate under Redis is NOT covered here (see 0.9.11a1
  `bg_rehydrate` in the archive if needed).
