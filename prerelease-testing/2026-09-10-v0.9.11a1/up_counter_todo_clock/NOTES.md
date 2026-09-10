# up_counter_todo_clock — upgrade testing counter / todo / clock / linkinbio (0.9.10.post2 -> 0.9.11a1)

Cluster: upgrade-path testing of four reflex-examples apps (`counter`, `todo`, `clock`,
`linkinbio`) from reflex 0.9.10.post2 (previous stable) to 0.9.11a1, published to PyPI
2026-09-10. Per app: baseline on stable, in-place venv upgrade preserving `.web/` and
`reflex.lock/`, then a cold `rm -rf .web` run. All flows driven in real Chromium via
Playwright; console, page errors, failed requests, 4xx/5xx and the frames SENT on the
`/_event` socket captured on every run. Date: 2026-09-10. Ports used: frontend 4100-4105,
backend 9100-9105 (prod: 4103 for both).

## Verdict

**No functional regressions.** Every user flow behaves identically on 0.9.10.post2, on
0.9.11a1 upgraded in place, and on a cold 0.9.11a1 build, for all four apps, in dev and (for
linkinbio) prod. Deterministic screenshots are md5-identical across versions (counter
initial; todo initial/added/after-finish). Console is clean apart from the documented
benign lines.

Two things worth knowing, neither a blocker:

1. **`rx.moment` `on_change` now fires at mount (react-moment 2.0.2, `reflex-components-moment`
   0.9.4a1).** With react-moment 1.2.2 (0.9.10 and the reflex-only upgrade) `on_change` fired
   only from the interval; 2.0.2 additionally invokes it once on mount, and **twice in dev**
   (React StrictMode double-invokes the mount effect). One extra backend event per page
   load (two in dev). Downstream (react-moment) behavior change, low severity. Details below.
2. **Upgrade-path gotcha:** `uv pip install --prerelease=allow 'reflex==0.9.11a1'` upgrades
   ONLY `reflex` and `reflex-base`; the alpha sub-packages (radix/code/moment/plotly/
   recharts/sonner/hosting-cli) stay at their stable releases because reflex pins them with
   `>=`. To actually test the train you must pin them explicitly. Exact resolutions below.

## Results matrix

| app | flows | 0.9.10.post2 baseline | 0.9.11a1 in-place (reflex-only) | 0.9.11a1 cold (reflex-only) | 0.9.11a1 full train | notes |
|---|---|---|---|---|---|---|
| counter | 8 steps (`counter_drive.py`) | PASS `logs/counter-0910-report.json` | PASS `counter-0911-inplace` | PASS `counter-0911-cold` | in-place PASS `counterFT-0911-inplace`, cold PASS `counterFT-0911-cold` (fresh dir `counter_fulltrain_inplace/`, baseline `counterFT-0910` PASS) | HMR check PASS on both versions (`counterFT-0911-hmr`, `counterHMR-0910`) |
| todo | 9 steps (`todo_drive.py`) | PASS `todo-0910` | PASS `todo-0911-inplace` | PASS `todo-0911-cold` | PASS `todo-0911-fulltrain` (`@radix-ui/react-form` 0.1.16, sonner 2.0.8) | `on_submit expects ...` warning is the app's own annotation mismatch, present on both versions |
| clock | 10 steps (`clock_drive.py`) | PASS `clock-0910` | PASS `clock-0911-inplace` | PASS `clock-0911-cold` | PASS `clock-0911-fulltrain` + fresh re-run `clock-0911-fulltrain-verify` | background task ticking, radix select, `rx.Cookie` persistence all identical |
| linkinbio | 14 steps (`linkinbio_drive.py`) | PASS `linkinbio-0910` | PASS `linkinbio-0911-inplace` | PASS `linkinbio-0911-cold` | dev PASS `linkinbio-0911-fulltrain`, `-dev2`, `-dev-verify`; prod PASS `-prod-verify` (`-prod` = same run, 1 step failed only because the driver counted the prod-only "Built with Reflex" badge as a 5th link — driver fixed) | `rx.moment` on_change-at-mount behavior change (below); avatar URL is a placeholder and fails on both versions |

Every report JSON has `all_steps_ok`, per-step detail, full console, `unexpected_console`,
`page_errors`, `failed_requests`, `http_4xx_5xx`, websocket open/close and the raw
`/_event` frames sent.

## Upgrade-path observation: plain `reflex==0.9.11a1` does not pull the alpha sub-packages

Reproduced twice (prior attempt on clock/linkinbio, fresh on `counter_fulltrain_inplace`):

```
$ uv pip install --python <venv> --prerelease=allow 'reflex==0.9.11a1'
 - reflex==0.9.10.post2            + reflex==0.9.11a1
 - reflex-base==0.9.10.post2       + reflex-base==0.9.11a1
```
(`logs/pip/counterFT-upgrade-step1-reflex-only.txt`, `logs/*-pip-upgrade-0911.txt`). Everything
else stays: code 0.9.4, core 0.9.9, moment 0.9.3, plotly 0.9.5, radix 0.9.8, recharts 0.9.2,
sonner 0.9.2, hosting-cli 0.1.71, lucide 1.0.4, markdown 0.9.3, dataeditor 0.9.2, gridjs 0.9.1,
react-player 0.9.2.

Pinning the train explicitly:
```
$ uv pip install --python <venv> --prerelease=allow 'reflex==0.9.11a1' 'reflex-base==0.9.11a1' \
    'reflex-components-radix==0.9.9a1' 'reflex-components-code==0.9.5a1' \
    'reflex-components-moment==0.9.4a1' 'reflex-components-plotly==0.9.6a1' \
    'reflex-components-recharts==0.9.3a1' 'reflex-components-sonner==0.9.3a1' \
    'reflex-hosting-cli==0.1.72a1'
 - reflex-components-code==0.9.4      + 0.9.5a1
 - reflex-components-moment==0.9.3    + 0.9.4a1
 - reflex-components-plotly==0.9.5    + 0.9.6a1
 - reflex-components-radix==0.9.8     + 0.9.9a1
 - reflex-components-recharts==0.9.2  + 0.9.3a1
 - reflex-components-sonner==0.9.2    + 0.9.3a1
 - reflex-hosting-cli==0.1.71         + 0.1.72a1
```
(`logs/pip/counterFT-upgrade-step2-fulltrain.txt`, `logs/pip/todo-upgrade-fulltrain.txt`,
`logs/*-pip-upgrade-0911-fulltrain.txt`; full lists in `logs/pip/*pip-list*.txt`). A user who
just runs `pip install -U reflex` once 0.9.11 is stable will get the new sub-packages only if
their own `>=` resolution happens to pick them up — with the alpha, it never does.

Consequence for this campaign: the "in-place"/"cold" columns above exercised reflex/reflex-base
0.9.11a1 with STABLE component packages; the "full train" column exercised the alpha
component packages too. Both paths were run for every app.

## Migration observations (first 0.9.11a1 run after in-place upgrade)

From `logs/server/counter_fulltrain_inplace_run_0911_inplace_fulltrain.log` (fresh) and
`<app>/logs/run_0911_inplace.log` (prior attempt, all four apps). Identical sequence everywhere:

- **bun**: 0.9.10 accepted the system bun 1.3.11 (`Minimum: 1.3.0`, "Skipping bun
  installation"). 0.9.11a1 requires 1.4.0 (`[Bun 1.3.11 (Minimum: 1.4.0)]`), downloads
  `bun_install.sh` and installs bun 1.4.0 into `$REFLEX_DIR/bun` ("bun was installed
  successfully"). Later runs: "Skipping bun installation".
- `.web/` is re-templated ("Copying .../reflex_base/.templates/web to .web"), the lockfile is
  restored from `<app>/reflex.lock/bun.lock` ("Restoring lockfiles"), then
  `bun install --legacy-peer-deps --frozen-lockfile` **succeeds against the 0.9.10 lockfile**
  (installs the OLD pins: react-router 8.3.0, vite 8.2.0 — 238 packages) — no "lockfile had
  changes" error. Then `bun add -d <new dev pins>` and `bun add <new runtime pins>` bump the
  versions and "Saved lockfile"; `.web/bun.lock` + `.web/package.json` are copied back to
  `reflex.lock/`. Restarts afterwards report "Checked N installs across M packages (no changes)".
- Two transient `warn: incorrect peer dependency "react-router@8.3.0"` lines during the
  dev-deps step (react-router still 8.3.0 while `@react-router/dev@8.3.1` is added; the very
  next step bumps react-router). Same class of warning appears on the 0.9.10 fresh install
  (`warn: incorrect peer dependency "react-router@8.3.1"` / `"react@19.3.0"`). Benign, final
  lock consistent (0 stale `react-router@8.3.0`/`vite@8.2.0` entries in `reflex.lock/bun.lock`).
- **`bun.lock` stays `lockfileVersion: 1, configVersion: 1`** after in-place AND cold runs
  (`logs/*bun.lock.head3.*`).
- **#7071 stale `utils/context.js` removal verified**: before upgrade `.web/utils` =
  `components context.js helpers react-theme.js state.js theme.js`; after the first 0.9.11a1
  compile = `components context-registry.js context.jsx helpers react-theme.js state.js theme.js`
  (`logs/counterFT-web-utils-listing.0910` vs `.0911-inplace`). The removal is silent (no log
  line, even at debug).
- `.web/reflex.json` version 0.9.10.post2 -> 0.9.11a1, project_hash unchanged; new field
  `last_version_check_attempt_datetime` (#7050 PyPI check caching).
- "Latest version of reflex: 0.9.10.post2" — the PyPI check ignores the alpha, so no
  upgrade nag on 0.9.10.
- **Cold run converges**: `rm -rf .web` then run -> `.web/package.json` byte-identical to the
  in-place result, `.web/bun.lock == reflex.lock/bun.lock`, frozen install 224 packages,
  no `bun add` churn beyond the standard "done" no-ops, no warnings.
- vite prints `Re-optimizing dependencies because lockfile has changed` once after the
  full-train install (expected).

### package.json diffs (0.9.10.post2 -> 0.9.11a1)

`.web/package.json` and `reflex.lock/package.json` diffs are identical in every case.

reflex-only upgrade (all four apps; `logs/*-web-package.json.diff`, `logs/counter/…`):
```
@react-router/node 8.3.0 -> 8.3.1     react-router 8.3.0 -> 8.3.1
@react-router/dev  8.3.0 -> 8.3.1     @react-router/fs-routes 8.3.0 -> 8.3.1
isbot 5.2.1 -> 5.2.2                  vite 8.2.0 -> 8.2.2
postcss 8.5.23 -> 8.5.26              postcss-import 16.1.1 -> 17.0.0
```
Full train adds (`logs/counterFT-web-package.json.diff`, `logs/todo-web-package.json.fulltrain.diff`,
`logs/clock-web-package.json.fulltrain.diff`, `logs/linkinbio-web-package.json.fulltrain.diff`):
```
sonner 2.0.7 -> 2.0.8                        (every app: toast provider is always compiled in)
@radix-ui/react-form 0.1.14 -> 0.1.16        (todo: rx.form)
react-moment 1.2.2 -> 2.0.2                  (linkinbio: rx.moment; moment stays 2.30.1)
```
Unchanged: react/react-dom 19.2.8, @radix-ui/themes 3.3.0, lucide-react 1.26.0,
socket.io-client 4.8.3, universal-cookie 8.1.2, react-error-boundary 6.1.2, react-helmet 6.1.0,
@emotion/react 11.14.0, autoprefixer 10.5.4. (clock/linkinbio pull no radix primitives, so
accordion/dialog bumps did not apply to any app here.)

## Per-app details

### counter (`counter/`, `counter_fulltrain_inplace/`) — 4100/9100, 4104/9104
Flows: initial render 0, Increment x2, Decrement, Randomize (0..100), Decrement after
randomize, 5 rapid increments all land, color-mode toggle light->dark, reload re-hydrates
the same count. All PASS on every run; `counter*-initial.png` md5 `01b53511…` on all six runs.
HMR (`counter_hmr_drive.py`, edits the "Increment" label while the page is open): label
swapped in 0.8 s, `window` marker survived (no full reload), count 3 survived, app
interactive afterwards — same on 0.9.10.post2 (`counterHMR-0910`) and 0.9.11a1 full train
(`counterFT-0911-hmr`).

### todo (`todo/`) — 4101/9101
Flows: 3 seed items, add via button (input cleared by `reset_on_submit`), add via Enter,
empty submit no-op, add `Café <b>&amp;</b> 50%` (rendered as text), finish middle item,
finish first item, lucide check icons present in every finish button, reload keeps items.
All PASS on all four runs; three deterministic screenshots md5-identical across versions.
Server log on all versions: `Warning: Event handler on_submit expects (dict[str, typing.Any])
-> () but got (dict[str, str]) -> () as annotated in State.add_item` — the example's own
annotation; printed cleanly on 0.9.11a1 (the 0.9.9a1 `dict\[str` escape leak from the
previous campaign is gone).

### clock (`clock/`) — 4102/9102
Flows: digital + analog render (3 rotated separators), clock stopped on load, switch starts
the `@rx.event(background=True)` ticker (values advance), default zone US/Pacific correct
to the hour, radix select -> Asia/Tokyo correct, reload keeps zone via `rx.Cookie` (cookie
`reflex___state____state.clock___clock____state.zone_rx_state_=Asia%2FTokyo`) and the
clock is stopped again, switch off stops ticking, Europe/London + start ticks in the new
zone. All PASS on five runs; console clean.

### linkinbio (`linkinbio/`) — 4103/9103, prod 4103
`launchdarkly-server-sdk==9.8.0` installs fine; without `LD_SDK_KEY` the app takes the
`rx.cond` false branch ("Bio Page if False") — nothing stubbed, that is the app's own
behavior; the LD-flag branch was not exercised (needs a real key). Flows: heading/bio text,
4 external link buttons with correct href + `target=_blank`, one lucide svg per link, radix
avatar (fallback, image URL is the example's placeholder `<your_username_here>` ->
`ERR_CONNECTION_RESET` on both versions), hover style change, click opens new tab,
`rx.moment(interval=3000, format="HH:mm:ss", on_change=State.on_update)` renders a `<time>`
matching the browser clock, ticks every 3 s, `on_update` frames reach the backend and the
handler prints `0 :: HH:MM:SS` in the server log, reload re-renders and ticks. All PASS in
dev (reflex-only and full train) and prod (full train).

**react-moment 2.0.2 differences (full train only):**
- `<time datetime>` is now ISO-8601 (`datetime="2026-09-10T13:28:50.551Z"`); 1.2.2 emitted
  epoch milliseconds (`datetime="1789033879117"`, invalid per the HTML spec). Improvement.
- **`on_change` fires at mount.** Evidence, dev (StrictMode on, the default):
  frontend frames `['13:28:35','13:28:35','13:28:38',…]` and after reload
  `['13:28:59','13:29:00','13:29:00','13:29:03',…]`; server log
  `0 :: 13:28:35` twice and `0 :: 13:29:00` twice
  (`logs/linkinbio-0911-fulltrain-dev-verify-report.json`,
  `logs/server/linkinbio_run_0911_fulltrain_dev_verify.log`; same in `-fulltrain`, `-dev2`).
  Prod (`-prod-verify`): no duplicates, but one extra event at mount (`13:30:52 -> 13:30:54`,
  a 2 s gap right at the reload). Baseline 0.9.10.post2 (react-moment 1.2.2) and the
  reflex-only 0.9.11a1 runs: frames strictly 3 s apart from ~3 s after load, zero
  duplicates, zero mount events (`logs/linkinbio-0910-report.json`, `-0911-inplace`, `-0911-cold`).
  Root cause in `react-moment/dist/index.mjs` (2.0.2) `useMomentUpdate`:
  `useEffect(() => { onChangeRef.current?.(propsRef.current) }, [])` — an unconditional
  mount effect; StrictMode runs mount effects twice. 1.2.2 only called `onChange` from its
  interval callback. Impact: one extra `on_change` backend event per mount (two in dev) with
  the initially rendered content. Upstream/downstream behavior (react-moment), surfaced by the
  0.9.4a1 migration (#7003); not a reflex-core defect. Severity low; a handler that treats
  `on_change` as "the displayed value changed" now also runs at mount.

## Anomalies / benign observations (both versions unless stated)

1. `/_event` websocket console errors during a hot edit: `WebSocket connection to
   'ws://localhost:9xxx/_event/…' failed: net::ERR_CONNECTION_REFUSED` (x2) while granian
   restarts the worker on a backend source change ("Changes detected, reloading workers");
   socket.io reconnects and the app keeps working. Identical on 0.9.10.post2
   (`logs/counterHMR-0910-report.json`) and 0.9.11a1 (`logs/counterFT-0911-hmr-report.json`).
2. The granian reloader watches every top-level directory of the app, including a `logs/`
   directory you create there: writing files into `<app>/logs/` triggers "Changes detected,
   reloading workers" (visible in `counter/logs/run_0911_inplace.log`). Both versions
   (`Reload paths:` lists `…/counter/logs`). This is why the fresh runs log to
   `logs/server/` outside the app dirs.
3. On SIGTERM shutdown the log says `error: script "dev" exited with code 143` /
   `Starting frontend failed with exit code 143` — 143 is just SIGTERM; wording is misleading
   but identical on 0.9.10.post2.
4. `Debug: Unable to bind to any port for 10: [Errno 97] Address family not supported by
   protocol` during the port check — no IPv6 in this sandbox; falls back to AF_INET. Both versions.
5. `SitemapPlugin ... enabled by default, but not explicitly added to the config` warning on
   every start (examples do not list plugins). Both versions.
6. prod mode appends a "Built with Reflex" badge (`<a href="https://reflex.dev" target=_blank>`)
   — expected for non-cloud prod builds; the first prod report (`linkinbio-0911-fulltrain-prod`)
   flagged it as a 5th link, fixed in `linkinbio_drive.py` (`built_with_reflex_badge` step).
7. linkinbio avatar `https://avatars.githubusercontent.com/%3Cyour_username_here%3E` ->
   `net::ERR_CONNECTION_RESET` + `Failed to load resource` console error: the example's
   placeholder URL; both versions; radix avatar falls back correctly.
8. Known-benign console lines seen on every run (per brief): React Router HydrateFallback
   "💿" log, vite connecting/connected, React DevTools line.
9. `logs/counter/run_0910_DISCARDED_sharedbun14.log`: the prior attempt's first baseline ran
   with the shared `~/.local/share/reflex` REFLEX_DIR where bun 1.4.0 already existed, so
   0.9.10 used bun 1.4.0. Discarded; all kept runs use a private `REFLEX_DIR=$SB/envs/rxdir_<app>`
   so 0.9.10 sees only the system bun 1.3.11 and 0.9.11a1 performs the real 1.3.11 -> 1.4.0
   migration.

## How to rerun

Everything below assumes `SB=<scratchpad>` with this directory's contents at
`$SB/apps/up_counter_todo_clock` (`C`), the Playwright driver venv `$SB/envs/driver`
(playwright + chromium at `/opt/pw-browsers/chromium`), and uv. Never run from the reflex
checkout. `<app>` is one of `counter todo clock linkinbio` (or `counter_fulltrain_inplace`,
`counter_hmr0910` — clean copies of `counter`). Ports: counter 4100/9100, todo 4101/9101,
clock 4102/9102, linkinbio 4103/9103 (prod: 4103/4103).

```bash
SB=/tmp/.../scratchpad; C=$SB/apps/up_counter_todo_clock; cd $C
# 0. fresh app copy (never modify the examples checkout)
cp -r /home/user/reflex-dev/reflex-examples/<app> $C/<app>

# 1. baseline venv + run + drive (0.9.10.post2, no --prerelease so requirements resolve as a user's would)
uv venv $SB/envs/up_counter_todo_clock_<app> --python 3.11
( cd $C/<app> && uv pip install --python $SB/envs/up_counter_todo_clock_<app>/bin/python 'reflex==0.9.10.post2' -r requirements.txt )
./run_server.sh <app> <FP> <BP> run_0910            # logs to logs/server/<app>_run_0910.log, private REFLEX_DIR, --loglevel debug
./wait_200.sh http://localhost:<FP>/ 420
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python <app>_drive.py http://localhost:<FP>/ shots/<app>-0910 logs/<app>-0910-report.json
cp <app>/.web/package.json logs/<app>-web-package.json.0910; head -3 <app>/reflex.lock/bun.lock > logs/<app>-bun.lock.head3.0910; ls <app>/.web/utils > logs/<app>-web-utils-listing.0910
./stop_server.sh <app> run_0910

# 2. in-place upgrade (keep .web/ and reflex.lock/)
( cd $C/<app> && uv pip install --python $SB/envs/up_counter_todo_clock_<app>/bin/python --prerelease=allow 'reflex==0.9.11a1' )   # reflex-only
# full train (what the "full train" column used):
( cd $C/<app> && uv pip install --python $SB/envs/up_counter_todo_clock_<app>/bin/python --prerelease=allow 'reflex==0.9.11a1' 'reflex-base==0.9.11a1' 'reflex-components-radix==0.9.9a1' 'reflex-components-code==0.9.5a1' 'reflex-components-moment==0.9.4a1' 'reflex-components-plotly==0.9.6a1' 'reflex-components-recharts==0.9.3a1' 'reflex-components-sonner==0.9.3a1' 'reflex-hosting-cli==0.1.72a1' )
./run_server.sh <app> <FP> <BP> run_0911_inplace && ./wait_200.sh http://localhost:<FP>/ 420
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python <app>_drive.py http://localhost:<FP>/ shots/<app>-0911-inplace logs/<app>-0911-inplace-report.json
diff logs/<app>-web-package.json.0910 <app>/.web/package.json; head -3 <app>/reflex.lock/bun.lock; ls <app>/.web/utils
./stop_server.sh <app> run_0911_inplace

# 3. cold
rm -rf <app>/.web && ./run_server.sh <app> <FP> <BP> run_0911_cold && ./wait_200.sh http://localhost:<FP>/ 420
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python <app>_drive.py http://localhost:<FP>/ shots/<app>-0911-cold logs/<app>-0911-cold-report.json
./stop_server.sh <app> run_0911_cold

# prod (linkinbio): same port for both
./run_server.sh linkinbio 4103 4103 run_prod --env prod && ./wait_200.sh http://localhost:4103/ 420

# HMR check (counter): edits counter/counter.py while the page is open and reverts it
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python counter_hmr_drive.py http://localhost:<FP>/ $C/<app>/counter/counter.py shots/<app>-hmr logs/<app>-hmr-report.json

# rx.moment on_change-at-mount repro (linkinbio, full-train venv, dev): after the drive,
grep -E '^[0-9]+ :: ' logs/server/linkinbio_run_0911_inplace.log | uniq -d     # duplicates => mount double-fire (dev)
python3 -c "import json,re;r=json.load(open('logs/linkinbio-0911-inplace-report.json'));print([re.search(r'\"date\":\"([^\"]+)\"',f).group(1) for f in r['event_frames_sent'] if 'on_update' in f])"
```

## File index

- `counter/ todo/ clock/ linkinbio/` — app copies used by the prior attempt (all runs:
  0910, 0911-inplace reflex-only, 0911-cold, plus fulltrain for clock/linkinbio); their
  `logs/` hold those runs' server logs (`run_0910.log`, `run_0911_inplace.log`,
  `run_0911_cold.log`, `run_0911_fulltrain*.log`) and package.json/lockfile snapshots.
- `counter_fulltrain_inplace/` — fresh copy: 0910 baseline -> in-place full-train upgrade ->
  cold (this attempt). `counter_hmr0910/` — fresh copy for the 0.9.10 HMR baseline.
- `logs/server/` — this attempt's server logs (outside app dirs):
  `counter_fulltrain_inplace_run_{0910,0911_inplace_fulltrain,0911_cold}.log`,
  `todo_run_0911_fulltrain.log`, `clock_run_0911_fulltrain_verify.log`,
  `linkinbio_run_0911_fulltrain_{dev,prod}_verify.log`, `counter_hmr0910_run_0910.log`.
- `logs/*-report.json` — Playwright reports (steps, console, frames). `logs/pip/` — exact
  pip resolutions. `logs/*package.json*`, `logs/*bun.lock.head3*`, `logs/*utils-listing*` —
  before/after snapshots and diffs. `logs/*reflex.lock.*/` — full reflex.lock dirs (linkinbio).
- `shots/` — screenshots per run (`<app>-<version>-<moment>.png`).
- `*_drive.py`, `drive_common.py` — Playwright drivers; `run_server.sh`, `stop_server.sh`,
  `wait_200.sh` — server helpers.

## VERIFICATION: rx.moment on_change fires at mount after react-moment 1.2.2 -> 2.0.2 migration (reflex-components-moment 0.9.4a1): once in prod, twice in dev (StrictMode)

Independent adversarial re-verification (verifier agent, own venv + own minimal app, ports 4600/9600 dev, 4601 prod).
Artifacts: `verification/` (app `momentapp/`, driver `drive_moment.py`, `logs/*-report.json`, trimmed server logs, screenshots).

**Verdict: CONFIRMED, and broader than claimed.** Genuine behavior change surfaced to reflex users by the react-moment
2.0.2 pin bump (#7006, reflex-components-moment 0.9.4a1). Regression vs 0.9.10.post2: yes. Not a reflex-core code
defect (mechanism is upstream react-moment and React StrictMode), but reflex ships it undocumented under "Bug Fixes"
while `docs/library/data-display/moment.md` and the `on_change` field doc ("Fires when the date changes.") still describe
the 1.2.2 semantics. Severity: low (not release-blocking), worth acting on (changelog/docs note at minimum; optionally
restore 1.2.2 semantics by skipping the mount callback in the component wrapper).

### What I did (all from PyPI, never from the checkout; app asserts `"/envs/verify_up_counter_todo_clock_0/" in reflex.__file__`)

Minimal app `verification/momentapp/momentapp/momentapp.py`: one page with THREE `rx.moment` instances, each with its own
`on_change` handler that increments a state counter, appends the payload to a list var, and prints
`EVT seq=N kind=... payload=... server_time=...` to stdout:
- `#interval`: `rx.moment(interval=3000, format="HH:mm:ss", on_change=State.tick)` (the claimant's case)
- `#static`:   `rx.moment(date="2020-01-02T03:04:05Z", format=..., on_change=State.static_change)` (no interval prop)
- `#zero`:     `rx.moment(interval=0, format="HH:mm:ss", on_change=State.zero_change)` (the pattern used by the reflex docs demo)
Plus a second route `/other` to test a client-side remount. `drive_moment.py` opens the page in Chromium (Playwright),
records every frame SENT on the `/_event` socket with a wall clock, waits 10 s, reloads, waits 10 s, navigates
client-side to `/other` and back, waits 10 s, and reads the on-page counters.

```bash
SB=/tmp/.../scratchpad; W=$SB/apps/verify_up_counter_todo_clock_0; cd $W
uv venv $SB/envs/verify_up_counter_todo_clock_0 --python 3.11
uv pip install --python $SB/envs/verify_up_counter_todo_clock_0/bin/python 'reflex==0.9.10.post2'            # A: baseline (moment 0.9.3 / react-moment 1.2.2)
# per run (dev):  cd $W/momentapp && REFLEX_TELEMETRY_ENABLED=false setsid $SB/envs/verify_up_counter_todo_clock_0/bin/reflex run --frontend-port 4600 --backend-port 9600 --loglevel debug > $W/logs/server_<run>.log 2>&1 &
#                 poll http://localhost:4600/ for 200, then:
#                 NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_moment.py http://localhost:4600/ shots/<run> logs/<run>-report.json 10
uv pip install --python ... --prerelease=allow 'reflex==0.9.11a1'                                             # B: reflex-only upgrade (moment stays 0.9.3 / react-moment 1.2.2)
uv pip install --python ... --prerelease=allow 'reflex==0.9.11a1' 'reflex-components-moment==0.9.4a1'         # C: react-moment 2.0.2
# C prod: reflex run --env prod --frontend-port 4601 --backend-port 4601 ; C dev no-strict: rxconfig react_strict_mode=False (verification/momentapp/rxconfig.nostrict.py)
```

### Results (mount-time `on_change` frames per moment, per mount; `verification/logs/<run>-report.json` + `server_<run>.log.trimmed`)

| run | react-moment | mode | `#interval` at mount | `#static` at mount | `#zero` (interval=0) at mount | counters after ONE page load (tick/static/zero) |
|---|---|---|---|---|---|---|
| `0910-dev` (A) | 1.2.2 | dev, StrictMode on | 0 | 0 | n/a (probe added later) | 3 / 0 / - |
| `0911_moment093_dev` (B) | 1.2.2 | dev, StrictMode on | 0 | 0 | 0 | 3 / 0 / 0 |
| `0911_moment094a1_dev` (C) | 2.0.2 | dev, StrictMode on | **2** | **2** | **2** | **5 / 2 / 2** |
| `0911_moment094a1_dev_nostrict` (C) | 2.0.2 | dev, `react_strict_mode=False` | **1** | **1** | **1** | 4 / 1 / 1 |
| `0911_moment094a1_prod` (C) | 2.0.2 | prod | **1** | **1** | **1** | 4 / 1 / 1 |

Same pattern on every mount kind: initial load, hard reload (new `/_event` socket) and client-side route remount
(`/other` -> `/`). A/B: first `tick` frame arrives ~3.1 s after `hydrate`, then strictly every 3 s, and the
static/zero handlers never run. C dev: e.g. `hydrate` 13:43:48.857, then `tick`, `static_change`, `zero_change`,
`tick`, `static_change`, `zero_change` all at 13:43:48.915-916 (payload `13:43:48` twice), server log
`EVT seq=1..6` at 13:43:48.915-.924, then the 3 s cadence. No console errors/page errors in any run
(prod has the usual unrelated 404 for a missing asset). The `<time datetime>` attribute also changed from epoch ms
(`datetime="1789047659093"`) to ISO-8601 (`datetime="2026-09-10T13:43:57.915Z"`) as the claimant noted.

### Refutation attempts
- Environment quirk? No: same machine/proxy/ports for A, B, C; only the react-moment version differs between B and C
  (`.web/package.json` `"react-moment": "1.2.2"` vs `"2.0.2"`, `Debug: installed react-moment@2.0.2` in the log).
- reflex/reflex-base 0.9.11a1 change? No: run B (reflex 0.9.11a1 + moment 0.9.3) is byte-for-byte the baseline pattern.
- Example-app bug? No: reproduced with a 60-line minimal app with no launchdarkly / no rx.cond.
- Flaky? No: 3 mounts x 3 moments x 3 configurations gave the exact expected count every time (0 / 2 / 1).
- Documented behavior? Upstream YES (react-moment 2.0.2 README "#### OnChange": "called with the current displayed
  content when the component mounts, and again after each automatic update ... Set `interval={0}` to disable periodic
  updates while still receiving the initial callback on mount"; `dist/types.d.ts:227` "Callback invoked with the
  displayed content on mount and after each interval tick"; MIGRATION.md "### `onChange` fires on mount" lists it as a
  breaking change vs 1.2.3: "If you previously assumed `onChange` only ran after the first `interval` elapsed, initialize
  state from rendered output or accept the extra mount callback." — saved to `verification/logs/react-moment-MIGRATION.md`).
  Reflex NO: `packages/reflex-components-moment/CHANGELOG.md` v0.9.4a1 lists the migration under "Bug Fixes" with no
  behavior note; `docs/library/data-display/moment.md` still says the handler "will be called every time the date is
  updated" and its demo (`interval=rx.cond(MomentLiveState.updating, 5000, 0)`, `on_change` -> `rx.toast(f"Date updated: {date}")`)
  will now toast on page load with `updating=False` (my `#zero` probe confirms `interval=0` fires the handler at mount).

### Mechanism (file:line)
- react-moment 2.0.2 `dist/index.mjs` (single minified line; `/root/.bun/install/cache/react-moment@2.0.2@@@1/dist/index.mjs`,
  identical to the copy bun installs into `.web/node_modules`), hook `useMomentUpdate` (`function $(t,e){...}`):
  `H(()=>{var i;(i=r.current)==null||i.call(r,o.current)},[])` — an unconditional `useEffect(..., [])` that calls the
  `onChange` ref once on mount, BEFORE the interval effect (`if(n||t.interval===0)return; ... setInterval(...)`); the
  `Moment` component (`var xt=t=>{... $(t,f=>{f.onChange&&f.onChange(C(f,e))}) ...}`) passes `props.onChange(getContent(props))`.
  react-moment 1.2.2 `src/index.jsx:303-308` `componentDidMount(){ this.setTimer(); ... }` only starts the timer;
  `onChange` was called solely from `update()` (`src/index.jsx:387-395`), i.e. after the first interval elapsed.
- Reflex side: `packages/reflex-components-moment/src/reflex_components_moment/moment.py:34` `library = "react-moment@2.0.2"`
  (commit 0008768b, #7006); `on_change: EventHandler[passthrough_event_spec(str)]` is passed straight through as the
  `onChange` prop, so the mount callback becomes a backend event.
- Double fire in dev: `reflex/compiler/compiler.py:1038-1041` wraps the app in `<StrictMode>` when
  `config.react_strict_mode` (default `True`, `packages/reflex-base/src/reflex_base/config.py:237`); React dev builds
  re-run mount effects (mount -> cleanup -> mount) under StrictMode, so the mount callback fires twice. Confirmed by the
  `react_strict_mode=False` run (exactly 1) and prod (exactly 1). Note reflex's own `on_mount` is the same kind of
  `useEffect(() => {...}, [])` (`reflex_base/components/component.py:1900-1907`), so a dev-only double mount event is
  consistent with existing reflex dev behavior; the NEW part is that `rx.moment.on_change` is now a mount event at all.

### Judgment
- confirmed: yes. regression: yes (0.9.10.post2 / react-moment 1.2.2: never at mount). downstream: yes (root cause is
  react-moment 2.0.x by design; surfaced by reflex's pin bump).
- severity: low. Impact per page mount: one extra backend event per `rx.moment(on_change=...)` (two in dev), delivered
  with the initially rendered content, including for `interval=0` and static-date moments where 1.2.2 never called the
  handler at all; handlers with side effects (toasts, counters, writes) now run on load. No errors, no broken rendering.
- suggested action: document as a behavior change (news fragment `breaking`/`misc` + docs: "on_change also fires once
  when the component mounts, with the initial content"), and/or wrap `onChange` in the component to drop the mount
  invocation if 1.2.2 semantics are wanted. Add an integration test for `on_change` timing
  (`tests/integration/test_moment.py` currently has zero `on_change` coverage).

All servers/browsers started by this verification were stopped (`ps` shows none on 4600-4603/9600-9603).

### Re-verification pass 2 (same verifier task re-launched; live re-execution, 18:06-18:09 machine time)

The VERIFICATION section above was already complete when this pass started (own venv `$SB/envs/verify_up_counter_todo_clock_0`,
own app `$SB/apps/verify_up_counter_todo_clock_0/momentapp`, own reports). To not merely trust the earlier logs, both ends of the
comparison were re-executed live on ports 4600/9600, from the written repro alone, and the source mechanism was re-read:

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad; W=$SB/apps/verify_up_counter_todo_clock_0
# C (venv already at reflex 0.9.11a1 + reflex-base 0.9.11a1 + reflex-components-moment 0.9.4a1; `uv pip list` checked first):
cd $W/momentapp && REFLEX_TELEMETRY_ENABLED=false setsid $SB/envs/verify_up_counter_todo_clock_0/bin/reflex run --frontend-port 4600 --backend-port 9600 --loglevel debug > $W/logs/server_0911_moment094a1_dev_rerun.log 2>&1 &
cd $W && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_moment.py http://localhost:4600/ shots/0911_moment094a1_dev_rerun logs/0911_moment094a1_dev_rerun-report.json 10
# A (baseline, downgrade in place — note the explicit moment pin, otherwise the already-installed 0.9.4a1 pre-release is kept):
cd $SB && uv pip install --python $SB/envs/verify_up_counter_todo_clock_0/bin/python 'reflex==0.9.10.post2' 'reflex-components-moment==0.9.3'
# then the same reflex run / drive_moment.py with run name 0910_dev_rerun
```

| run (this pass) | react-moment (`Debug: installed …` in server log) | mode | `#interval` at mount | `#static` at mount | `#zero` (interval=0) at mount | tick/static/zero counters after one load | backend `EVT` lines total (3 mounts) |
|---|---|---|---|---|---|---|---|
| `0911_moment094a1_dev_rerun` | 2.0.2 | dev, StrictMode default | **2** (`18:06:11` x2, 91 ms after `hydrate`) | **2** | **2** | **5 / 2 / 2** | **27** = (6 mount + 3 ticks) x 3 |
| `0910_dev_rerun` | 1.2.2 | dev, StrictMode default | 0 (first `tick` 3.09 s after `hydrate`) | 0 | 0 | 3 / 0 / 0 | 9 = 3 ticks x 3 |

Identical to pass 1 on every count (initial load, hard reload = new `/_event` socket, client-side `/other` -> `/` remount); no
console errors, no page errors either run. Evidence: `verification/logs/0911_moment094a1_dev_rerun-report.json`,
`verification/logs/0910_dev_rerun-report.json`, `verification/logs/server_*_rerun.log.trimmed` (every `EVT seq=` line the backend
printed), `verification/shots/*_rerun-*.png`. `<time datetime>` again epoch-ms on 1.2.2 (`datetime="1789063721436"`) vs ISO on
2.0.2 (`datetime="2026-09-10T18:06:20.369Z"`).

Additional refutation angles checked this pass:
- **"Maintainers knowingly accepted it / documented behavior on the reflex side?"** No. PR #7006 ("Migrate react-moment to 2.0.2",
  merged 2026-09-08) body, Greptile review and the full diff never mention `onChange`/`on_change`; the news fragment
  `packages/reflex-components-moment/news/7003.bugfix.md` is the one-liner that became the CHANGELOG "Bug Fixes" entry; the new
  `tests/integration/test_moment.py` (2 tests: `parse=[…]` and `duration`+`trim`) has zero `on_change` coverage; the `on_change`
  field doc on the release branch is still `"Fires when the date changes."` (`moment.py:115-117`). Issue #7003 (masenf) explicitly
  scoped the migration as "any that moved or disappeared needs a deprecation path since `rx.moment` is public API" — the changed
  `on_change` timing is exactly such a public-surface change and was not mapped.
- **Mechanism re-read (exact lines):** react-moment 1.2.2 `src/index.jsx:303-308` `componentDidMount(){ this.setTimer(); … }` and
  `:345-354` `setTimer` only arms `setInterval(() => this.update(this.props), interval)` when `interval !== 0`; `onChange` is called
  solely from `update()` at `:387-395` (`this.setState({content}, () => { onChange(content) })`). react-moment 2.0.2 `dist/index.mjs`
  `useMomentUpdate` (`function $(t,e){…}`) runs `H(()=>{…(i=r.current)==null||i.call(r,o.current)},[])` = `useEffect(() => onChange(props), [])`
  unconditionally before the interval effect (`if(n||t.interval===0)return`), so the callback fires on mount even for `interval=0`
  and for static dates; `dist/types.d.ts:227` documents it ("on mount and after each interval tick"). Reflex wires the prop straight
  through (`on_change: EventHandler[passthrough_event_spec(str)]`), and `reflex/compiler/compiler.py:1038-1041` wraps the app in
  `<StrictMode>` when `config.react_strict_mode` (default `True`, `reflex_base/config.py:237`) -> mount effect runs twice in dev.
- Housekeeping: after this pass the verifier venv is left at the BASELINE (`reflex==0.9.10.post2`, `reflex-components-moment==0.9.3`);
  re-pin `'reflex==0.9.11a1' 'reflex-components-moment==0.9.4a1' --prerelease=allow` before re-running configuration C. All servers
  and browsers started by this pass were killed (process-group TERM/KILL + cwd sweep; no process with cwd under the verifier app dir
  remains, no listener on 4600-4603/9600-9603). `reflex run` processes from OTHER agents (`envs/smoke`, ports 3221/8221/8180) were
  running concurrently and were left untouched.

**Verdict unchanged: CONFIRMED (genuine behavior regression 0.9.10.post2 -> 0.9.11a1 via reflex-components-moment 0.9.4a1),
severity low, downstream root cause (react-moment 2.0.x by design), reflex-side gap is missing changelog/docs note (or a wrapper
that drops the mount callback) — not release-blocking, worth acting on.**
