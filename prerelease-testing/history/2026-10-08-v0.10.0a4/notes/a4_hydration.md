# Item `a4_hydration` — A3-11 / A3-12 re-verification + reflex#7505 regression hunt on reflex 0.10.0a4

Date 2026-10-08. Under test: **reflex 0.10.0a4 / reflex-base 0.10.0a4** (PyPI) in the shared read-only venv `$SB/envs/a4`.
Positive control / baseline: `$SB/envs/a3` (0.10.0a3), `$SB/envs/stable` (0.9.12). Browser: Playwright + `/opt/pw-browsers/chromium`
from `$SB/envs/driver` (the verifier's raw-CDP scenarios run a stock headful Chromium under Xvfb).
Nothing installed from / run inside a checkout: every app runs from `$W/run/<name>` (or `$W/v/run/<name>`) and asserts
`reflex.__file__` is under `/scratchpad/envs/$RVH_VENV/` (set by `scripts/srv.sh` / `verification/scripts/vsrv.sh` to the venv name);
drivers assert `/envs/driver/`. Ports: 3140-3159 / 8140-8159 (explorer scripts, h4mix, third-party), 3660-3679 / 8660-8679 (verifier
scenarios: 3660/8660 app, 8661 or 3663 latency proxy, 8669 redis, 8670 CDP). One app server at a time; a3/a4 comparisons were run
back to back under the same load (another agent shares the 4 CPUs).

Compiled frontend check: every a4 run dir's `.web/utils/state.js` has md5 `b7915eda` (= the a4 wheel's template, contains
`sentStorageValues`), every a3 one `caea5520` (a3 template); the a4 prod bundle contains the new code (grep `sentStorageValues`).

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a4_hydration
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
# To rerun elsewhere (the scripts hard-code W and W/v):
mkdir -p $W/{run,logs,results} $W/v/{run,logs,out}
cp -r src drivers scripts cv $W/ && cp -r verification/{src,drivers,scripts} $W/v/
```
(Optional speed-up used here: the run dirs were seeded with `cp -a` of the a3 pass's built run dirs
`$SB/apps/a3_hydration/run/{st,ss,la,ga}-*` and `$SB/apps/verify_hydration/run/vh-a3-*` to reuse `node_modules`; reflex
re-initialises `.web` on the version change, which the md5 check above confirms.)

## Verdicts
| item | verdict on 0.10.0a4 | evidence (a3 positive control -> a4) |
|---|---|---|
| **A3-11** boot-echo storm | **FIXED** (dev, prod, prod+Redis 9 workers) | explorer Part S dev 5/8 -> 0/8, prod 1/5 -> 0/5; verifier 100 ms RTT dev raw3 3/3 -> 0/3 (race hit 3/3), restore7 -> 0/3 (race hit 3/3), prod+Redis raw3 2/3 -> 0/3, restore7 2/2 -> 0/2; every a4 run: all tabs + localStorage on the user's LAST value |
| **A3-12** on_load stamp loop | **FIXED** (dev, prod, prod+Redis) | explorer `/stamp` 6 tabs dev 3/3 -> 0/4, prod 2/2 -> 0/3, 4 tabs 0/3; verifier 6 background `/doc` tabs dev 2/2 -> 0/2, prod+Redis 2/2 -> 0/2, 4 quiet tabs + dev backend reload 2/2 -> 0/2; all tabs + localStorage on ONE value |
| #7505 regression hunt | no functional regression found; one low-severity behaviour change (near-simultaneous cross-tab writes keep the storage-order last value) | h4mix 39/39 a4 dev/prod, 22/22 prod+Redis; review bug (sync=False write equal to the boot value after another tab wrote) OK; sanitising override output reaches localStorage at boot, from handlers and from synced raw values; a3 loses a yield chain's final value (fixed on a4) |
| F-002 / F-003 | still fixed | fresh profile writes nothing (dev, prod, prod+Redis); google-auth bogus token cleared on reload; sanitised boot values written |
| cookies / SessionStorage | unchanged vs a3 | max_age renewed at boot (+4 s, a3 +5 s, 0.9.12 +4 s); SessionStorage per tab |
| reflex-local-auth 0.5.0 / reflex-google-auth 0.2.0 | = a3 | 36/38 (known demo pitfall) + 14/14 storage checks; bogus token cleared |

## Part 1 — original failing repros (a3 positive control first, then a4, same machine, back to back)

### A3-11 (boot-echo storm), explorer driver `drivers/sync_race.py` Part S (`scripts/run_storm.sh <venv> <mode> <runs> <FP> <BP> S 6`)
tab0 + 6 tabs loading concurrently while tab0 changes the synced value 5x (250 ms apart), localhost. Storm = not converged or
>50 websocket frames in the 2 s quiet window. Summaries: `scripts/summ_s.py results/sync/storm_<venv>_<mode>_S_6_`.

| | a3 (positive control) | **a4** |
|---|---|---|
| dev (3142/8142), 8 runs | **5/8 storm** (22k-87k frames, tabs end split s2/s3 or s3/s4, localStorage on a stale value, 7.7k-20k frames in the 2 s quiet window) | **0/8 storm**; 8/8 all 7 tabs + localStorage = `s5` (user's last value); 61-79 frames total, 0 in the quiet window |
| prod (3144), 5 runs | **1/5 storm** (54k frames, tabs s0/s1, localStorage `s0`) | **0/5 storm**; 5/5 converge on `s5`; 87-95 frames, 0 quiet |

`results/p1_storm_dev_summary.txt`, `results/p1_storm_prod_summary.txt`. a4 server logs: only the shutdown-time
`[ERROR] Unexpected exit from worker-1` (pre-existing granian line).

### A3-11 / A3-12, the verifier's scenarios (100 ms RTT proxy) — `scripts/vmatrix.sh <a3|a4> <dev|prodredis> <raw_runs> <restore_runs>`
Copied from `a3_hydration/pr7505/scripts/vh_matrix.sh`, pointed at the published venvs; app `verification/src/vhsync`, drivers
`verification/drivers/vh_rawcdp.py` (stock headful Chromium under Xvfb, REAL background tabs: `visibility` hidden, timers 2-3 Hz) and
`vh_tabs.py` (Playwright). A returning user (profile holds `vh_theme=green`) clicks `pick-red` ONCE, 200 ms after the foreground tab
hydrates, while the other tabs boot (stagger 300 ms). Storm = >50 frames in the last 5 s window. `vtrigger.py` shows whether a tab
booted across the click holding the stale value (= the race was actually hit). Results `verification/out/<tag>_<i>.json`, log
`results/p1_vmatrix_dev.txt`, `results/p1_vmatrix_prodredis.txt`.

| scenario (dev: app 3660/8660, proxy 8661) | a3 (positive control) | **a4** |
|---|---|---|
| raw CDP, 3 restored background tabs + 1 click | **3/3 storm** (21-24k frames / 5 s; tabs end `green,green,green` / `red,green,green` / `red,green,red`, localStorage `red`,`red`,`green`); race hit 3/3 | **0/3 storm**, 0 frames in both 5 s windows; all tabs + localStorage `red` 3/3; race hit 3/3 (tab1 sent `green` at boot, its final boot delta echoed `green`, not written) |
| Playwright, 7 tabs restored 300 ms apart + 1 click | 0/2 storm + 1 Playwright `write EPIPE` crash (the known storm-time node crash, counted unknown); race NOT hit in the 2 completed runs (tab1 read `red`) | **0/3 storm**, all 7 tabs + localStorage `red`; race hit 3/3 |
| A3-12: raw CDP, 6 background tabs restored at once on `/doc/d0..d5` (on_load stamps the slug) | **2/2 storm** (25-27k frames / 5 s; tabs end on 3-4 different slugs) | **0/2 storm**, 0 frames; all 6 tabs + localStorage on ONE slug (`d5`, `d2`) |
| A3-12: 4 quiet tabs on `/doc/d0..d3` + one dev backend reload (append a comment to the app module) | **2/2 storm** (32-38k frames / 5 s, 3 different slugs) | **0/2 storm**: 8 frames in the reload window then 0; all 4 tabs + localStorage `d2` |

a4 server log: nothing but the shutdown `[ERROR] Unexpected exit from worker-1`. a3 log additionally: 21x `Failed to close
websocket ... Broken pipe` and `Received event from session ... with no associated` (storm-time, as in the a3 pass).

| scenario, **prod + Redis** (app 3662 one port, proxy 3663, redis 8669, 9 granian workers) | a3 (positive control) | **a4** |
|---|---|---|
| raw CDP, 3 restored background tabs + 1 click | **2/3 storm** (8-11k frames / 5 s; one run ends with localStorage on the OLD `green`); race hit 3/3 | **0/3 storm**, 0 frames, all tabs + localStorage `red`; race hit 3/3 |
| Playwright, 7 tabs restored 300 ms apart + 1 click | **2/2 storm** (11-16k frames / 5 s; tabs end mixed red/green, localStorage `green` = the user's click LOST) | **0/2 storm**, all 7 tabs + localStorage `red`; race hit 2/2 |
| A3-12: raw CDP, 6 background tabs on `/doc/d0..d5` | **2/2 storm** (16-17k / 5 s, 3-4 slugs) | **0/2 storm**, all 6 tabs + localStorage on one slug (`d2`, `d1`) |

Procedural: the first a4 prod+Redis attempt never started (the a3 leg's `redis-server` was still releasing port 8669, the new one
failed with `bind: Address already in use`, the app logged `Unable to connect to Redis` and exited); `vmatrix.sh` now waits for the
port to free and for `PONG`, and the a4 leg was re-run alone right after (`results/p1_vmatrix_prodredis_a4.txt`). a4 prod+Redis
server log: only the granian "more workers than CPU cores" warning and the deprecation warnings also present on a3.

### A3-12 (on_load stamp loop), explorer driver `drivers/stamp_storm.py` (`scripts/run_stamp2.sh <venv> <mode> <FP> <BP> <runs /stamp> <runs /same> <NTABS>`)
`src/syncstamp`: `/stamp`'s on_load sets a sync=True LocalStorage var to a per-tab value; N tabs load at once (session restore).
`/same` (every tab writes the same value) is the control. Frames counted in-page. Summary `results/p1_stamp_summary.txt`, raw lines `results/p1_stamp.txt`.

| | a3 (positive control) | **a4** |
|---|---|---|
| dev 6 tabs `/stamp` | **3/3 storm**: 64k-127k frames per 5 s, 245k-906k frames total, 3-4 different values across the tabs, localStorage on yet another | **0/4 storm**: 79-95 frames total, 0 per 5 s afterwards, all 6 tabs + localStorage on ONE value |
| dev 4 tabs `/stamp` | — | **0/3 storm**, one value (57-93 frames) |
| prod 6 tabs `/stamp` | **2/2 storm** (61k-105k per 5 s, 4-5 values) | **0/3 storm**, one value (79-107 frames) |
| `/same` control, 6 tabs | dev quiet 1/1 | dev quiet 1/1, prod quiet 1/1 |

## Part 2 — reflex#7505 regression hunt (`src/h4mix`, `drivers/h4_drive.py`, `drivers/b2b_probe.py`)

App `src/h4mix` (every storage flavour in one app): `Prefs` LS sync=True `h4_syn`, LS sync=False `h4_nos`, SS `h4_ses`, Cookie
`h4_ck` (max_age 3600), LS sync=True `h4_san` + LS sync=False `h4_sanns` both SANITISED by a `get_delta` override (lowercase + clamp to
12 chars), computed `syn_len`; substate `Sub` (LS sync=True `h4_sub`, Cookie `h4_subck` max_age 7200, and `shared_s` = sync=True on the
key `h4_shared` that `Prefs.shared_ns` (sync=False) also uses); `rx.ComponentState` `Box` x2 (LS sync=True + LS sync=False, no name);
`/stamp` on_load writes LS sync=True `h4_last` + sync=False `h4_visits`. Handlers: set by input (on_blur), fixed-value buttons
`#c0..#c9`, `same` (assign every storage var to itself), `""` and back (yield), unicode / JSON-looking / 6402-char strings, a yielded
chain into another handler, a background task writing inside `async with self`, `rx.remove_local_storage` / `rx.clear_local_storage`.

Driver `drivers/h4_drive.py BASE OUT_JSON [only=C1,C2,...]`: every check in a fresh browser context; records console
errors+warnings + pageerrors, failed requests / >=400 responses, websocket frames (in-page counter) and every `setItem` the page makes
(wrapped `Storage.prototype.setItem`). "Seed" writes come from a non-app page of the same origin (`/__seed`, routed by Playwright) =
another tab / devtools / another app version writing the key. Rerun: `scripts/run_h4.sh <venv> <dev|prod> <label> <FP> <BP> [only|-] [ENV=VAL...]`
(used: `a4 dev a4dev 3146 8146 -`, `a4 prod a4prod 3148 3148 -`, a4 prod+redis `a4prodredis 3148 3148 C1,C2,C3,C4,C7,C10
REFLEX_REDIS_URL=redis://localhost:8149` with `redis-server --port 8149 --save '' --appendonly no`). a3 / 0.9.12 were run against
`srv.sh start h4-a3dev a3 dev src/h4mix 3146 8146` / `h4-stabledev stable ...` with the same driver.

Driver fix during the run: the first version of `C3_alternate_gap*` / `C3_back_to_back_clicks` returned at the FIRST moment all tabs
agreed, which happens transiently on an older value before the last delta lands (it reported `c8`/`c6` on a3 AND a4 with 3-6 frames
still in flight). Those checks now wait 2.5 s, then read. Results below are from the fixed driver (`results/h4/a4dev_C3fix_*.json`).

### Rapid writes to a sync=True var from two tabs within one round trip (`b2b_probe.py BASE OUT REPS <one|two|alt|warm>`)
`alt`: t1 and t2 alternately click `#c0..#c9` with no pause (each Playwright click awaited, ~30-50 ms apart), 3 s settle.

| mode | a4 dev | a3 dev | 0.9.12 dev |
|---|---|---|---|
| `one` (1 tab, 10 clicks back to back) | 5/5 `c9` | — | — |
| `two` (t1 clicks, t2 follows) | 5/5 `c9`, t2 writes nothing | 5/5 `c9`, t2 rewrites every value (echo) | — |
| `warm` (alternate 120 ms apart first, then t1 back to back) | 4/4 `c9` | — | — |
| `alt` (zero-gap alternation) | **5/5 converge on `c8`** (t2's own last click `c9` lost), no ping-pong (t1 5 writes, t2 5 writes) | 5/5 `c9` after a short ping-pong (t1 10-20 writes, t2 13-22) | 3/4 `c9`, **1/4 `c5`**, long ping-pong (hundreds of writes) |
| h4_drive `C3_alternate_gap0` (same, after earlier activity) | `c8` 3/3 | `c9`* | `c9` |
| `C3_alternate_gap40` / `gap120`, `C3_back_to_back_clicks` | `c9` | `c9`* | `c9` |
(* a3 numbers for these rows are from the first driver version, which read too early, and were not re-run with the fix.)

Mechanism (a4, `results/b2b/a4dev_alt.json` rep 0 frame log): t1 sends `click_syn(c8)` at +0 ms, t2 sends `click_syn(c9)` at +32 ms; t2's
`c9` delta lands at +43 ms and is written; t1's `c8` delta lands at +49 ms and is written after it; t1's `storage` event for t2's `c9` is
turned into `update_vars_internal` only now and, by #7505's design ("a storage event sends the value stored NOW, not `e.newValue`"),
sends `c8`; t2 syncs t1's `c8`. Every tab and localStorage agree on `c8`, quietly, but t2's later click is lost and t2 visibly flips
`c9 -> c8`. a3 sent `e.newValue` (`c9`) and settled on `c9` after a ping-pong; 0.9.12 ping-pongs much longer and also lost the last
write once. Effect: with writes from two tabs closer than one round trip, a4 keeps the value whose delta was WRITTEN last (storage
order), not the one the user produced last. A human cannot click in two tabs that fast; programmatic writers (background tasks,
on_load in several tabs, `yield` chains) can, and at 100 ms RTT the window is ~one RTT wide. Low severity: always converges, no storm.

### Part 2 check matrix (`results/h4/<label>.json` / `.txt`)
| check | a4 dev | a4 prod | a4 prod+Redis | a3 dev | 0.9.12 dev |
|---|---|---|---|---|---|
| C1 F-002: fresh profile, `/` + client nav `/other` + new tab `/other`: no LS / SS / cookie written (only `theme`, `last_compiled_theme`, SS `token`) | pass | pass | pass | pass | pass |
| C1 fresh `/stamp`: only its on_load keys `h4_last`, `h4_visits` | pass | pass | pass | pass | pass |
| C2 sync=False written by a handler persists across reload | pass | pass | pass | pass | pass |
| C2 sync=False NOT followed by another tab | pass | pass | pass | pass | pass |
| C2 **review bug**: tab1 boots sending `h4_nos=A`, tab2 writes `B`, tab1's handler sets `A` (= its boot value) -> stored, reload shows `A` | pass (`setItem h4_nos A` seen) | pass | pass | pass | pass |
| C2 handler assigning every var to itself after another tab changed the key -> rewritten (also writes the defaults of never-set vars, same on all versions) | pass | pass | pass | pass | pass |
| C3 sync=True followed; tab1 sets the value it sent at boot after tab2 changed it -> stored and followed, 0 frames afterwards | pass | pass | pass | pass | pass (C3 only) |
| C3 two tabs alternating 40 / 120 ms apart; 10 back-to-back clicks in one tab -> all tabs + LS `c9` | pass | pass | pass | pass | pass |
| C3 two tabs alternating with no gap | **`c8`** (see above) | **`c8`** | **`c8`** | `c9` | `c9` |
| C3 three tabs follow a change in the third | pass | pass | pass | pass | pass |
| C4 **sanitising override**: boot value `HELLO World Mixed Case` -> LS `hello world ` (sync=True) / `nosync value` (sync=False) | pass | pass | pass | pass | pass |
| C4 handler value sanitised -> override output in LS | pass | pass | pass | pass | pass |
| C4 another tab writes raw `RAW Upper` -> app tab syncs it, override answers `raw upper`, **LS gets `raw upper`** (not the echo) | pass | pass | pass | pass | pass |
| C4 two app tabs + raw write -> both sanitise, converge, 0 frames afterwards; re-sending a value whose echo the override replaced; setting the sanitised form of an earlier replaced value | pass | pass | pass | pass | pass |
| C6 SessionStorage per tab, never synced, survives reload, new tab gets the default | pass | pass | — | pass | — |
| C7 cookie `max_age` renewed at boot (expiry +4-5 s after a 3 s wait) | pass (+4 s) | pass (+4 s) | pass | pass (+5 s) | pass (+4 s) |
| C10 on_load write stored + synced to the other tab; reload + client-nav re-run on_load (visits 3) | pass | pass | pass | pass | — |
| C11 background task write inside `async with self` -> stored + followed | pass | pass | — | pass | pass |
| C11 **yield chain** `chain-1 -> chain-2 -> yield chain_end (chain-3)` -> all tabs + LS `chain-3` | pass | pass | — | **FAIL: both tabs + LS end on `chain-1`** (stale echo lost the update) | pass |
| C11 `""` and back (yield) -> `chain-3-back` | pass | pass | — | **FAIL: `chain-1-back`** | pass |
| C11 set to `""` persists (reload shows `""`, not the default) | pass | pass | — | pass | pass |
| C11 unicode / JSON-looking / 6402-char value: LS exact, other tab follows, reload exact, quiet | pass | pass | — | pass | pass |
| C15 ComponentState: sync=True follows, sync=False does not, other instance untouched, reload; substate sync + cookie; client nav keeps values; close all tabs + reopen | pass | pass | — | pass | — |
| C20 returning visitor boot writes (diagnostic) | only sync=False `h4_nos`, `h4_sanns` (synced echoes skipped) | same | — | all 6 LS keys rewritten | all 6 rewritten |
| C21 `rx.remove_local_storage("h4_syn")` in tab1 / `rx.clear_local_storage()` | LS stays removed, 0 frames; tab2 keeps showing `keep-me`; backend `TypeError` (see anomaly) | same | — | same | same |
| C23 sync=False + sync=True var on ONE key | pass (ns write followed by the other tab's sync var; reload shows the last write in both) | pass | — | pass | pass |
| console errors/warnings, failed requests | none | none | none | none | — |
| server log | only `TypeError` from C21 + shutdown line | same | clean | same | same |

Totals: a4 dev 38/39 with the first driver (the 1 fail = the driver bug above; C3 re-run with the fixed driver 7/7 x3, `results/h4/a4dev_C3fix_*.json`), a4 prod 39/39 (fixed driver), a4 prod+Redis 22/22 (subset), a3 dev 36/39 (C11 chain x2 real failures; C3
back-to-back was the driver bug, `results/h4/a3dev_C3fix.json` 7/7), 0.9.12 dev 14/14 + 17/17 (subsets). The console capture was
verified with `drivers/capture_selftest.py` (catches error, warning and pageerror).

Anomaly, pre-existing on a3, a4 and 0.9.12 (C21): when one tab removes a synced key (`rx.remove_local_storage`), every other tab's
`storage` event carries `null`, `update_vars_internal` sets the `str` var to `None`, and a computed var over it (`len(self.syn)`) raises
`TypeError: object of type 'NoneType' has no len()` (`[Reflex Backend Exception]` traceback in the server log); that tab keeps showing
the old value. Same on all three versions, not caused by #7505; noted, not filed.

### Third-party auth (venv `$SB/envs/a4_hydration-tp-a4`: `reflex[db]==0.10.0a4 reflex-base==0.10.0a4 reflex-local-auth==0.5.0
reflex-google-auth==0.2.0 'google-api-python-client>=2.184.0' 'pydantic<2.14'`, freeze `results/a4_hydration-tp-a4.freeze.txt`)
| | a4 dev | a3 dev (a3 pass) |
|---|---|---|
| reflex-local-auth `drive_local_auth.py` (`scripts/run_la.sh a4_hydration-tp-a4 dev a4dev 3153 8153`) | 36/38, the 2 fails = the known `/tp-strict-register` demo pitfall (`_validate_fields` subclass override), identical text on a3 | 36/38 |
| `la_storage.py`: fresh profile writes nothing; login stores `_auth_token`; reload + second tab logged in; logout in tab A -> tab B logged out after reload; bogus token -> anonymous; console clean | **14/14**; `auth_token` in the reload's inbound deltas 2x (snapshot + echo, = a3) | 14/14 |
| reflex-google-auth bogus `token_response_json` (`scripts/run_gauth.sh a4_hydration-tp-a4 dev a4dev-s4 3142 8142 4`) | cleared on the first reload; protected page stays locked; result line identical to a3's saved `a3-dev-seed4.json` | cleared |

## Issues
1. (low, behaviour change vs a3; not a storm) Near-simultaneous writes from two tabs: a4 keeps the value written to storage last, not
   the one produced last (`C3_alternate_gap0` / `b2b_probe.py alt`: `c8` 5/5 + 3/3 dev, prod, prod+Redis; a3 `c9` 5/5 after a short
   ping-pong; 0.9.12 `c9` 3/4 / `c5` 1/4 after a long ping-pong). A consequence of #7505's documented "send the value stored now".
2. (pre-existing, all versions) C21 `None` into a `str` var when another tab removes a synced key -> computed-var `TypeError`.

## Not covered
* Enterprise auth-token storage / cross-tab logout (N-032) — not in this brief's list of runs; reflex-enterprise not exercised here.
* reflex-local-auth / google-auth in prod and prod+Redis on a4 (dev only; the a3 pass showed dev = prod = prod+redis for both).
* Browsers other than Chromium (Firefox/Safari storage-event timing differs); latency other than 0 and 100 ms RTT.
* 0.9.12 for Part 1 (the a3 pass already has 0.9.12 storming 9/10, 3/3, 6/6 on these drivers; not re-run).
* The verifier's 60 s long-run storms on a3 were not repeated (a3 positive controls fired on every scenario family here).

## Procedural notes
* One `python -c 'import reflex'` version check at the very start ran with the shell's cwd under
  `/home/user/reflex/prerelease_testing/2026-10-07-a3` (inside the checkout); it imported the venv's reflex (printed path under
  `$SB/envs/a4`). Every app server, driver and reflex import afterwards ran from `$SB/apps/a4_hydration`.
* A `pkill -f` used during cleanup matched its own shell (exit 144); cleanup was redone by PID. All servers, proxies, redis and
  browsers were stopped; `lsof` shows no listener in 3140-3159 / 8140-8159 / 3660-3679 / 8660-8679 at the end.
* `pr7505/scripts/*` are the a3 pass's originals for reference (they point at the PR worktree); `scripts/vmatrix.sh`,
  `scripts/run_storm.sh`, `scripts/run_stamp2.sh` are the published-venv equivalents used here.
