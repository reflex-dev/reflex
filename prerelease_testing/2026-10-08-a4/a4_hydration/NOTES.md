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
