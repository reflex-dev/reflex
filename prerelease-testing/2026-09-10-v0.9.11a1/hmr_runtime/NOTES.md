# hmr_runtime — reflex 0.9.11a1 pre-release testing notes

Cluster: dev-server hot-update runtime stability (#7071), stale `utils/context.js` removal on upgrade (#7071),
Safari cache-bust plugin streaming rewrite (#7048), dev-server knobs `REFLEX_DEV_PROD_REACT` /
`REFLEX_VITE_WARMUP_ROUTES` (#7021).

Everything here was run against **published PyPI packages only** (`$SB/envs/smoke` = reflex 0.9.11a1,
`$SB/envs/base0910` = reflex 0.9.10.post2, `$SB/envs/hmr_pre7048` = reflex 0.9.10.post1 built for one
sensitivity check), in a real Chromium (Playwright, `/opt/pw-browsers/chromium`), never from the checkout.
`SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad` in every command below;
the copies in this directory are under `prerelease-testing/2026-09-10-v0.9.11a1/hmr_runtime/`.

## Layout of this directory

| path | what |
|---|---|
| `hmr_app/` | the test app (rxconfig.py + `hmr_app/hmr_app.py`). `scripts/hmr_app_pristine.py` is the exact source every run starts from; the driver edits `hmr_app/hmr_app/hmr_app.py` in place while the server runs |
| `scripts/hmr_driver.py` | Playwright (async) driver: loads the app, interacts, then applies 8 source edits while clicking, and records per edit: page errors, console, Vite HMR frames (`update`/`full-reload`), socket.io websocket attempts vs successful connections, `utils/state.js` refetches, `utils/context.jsx` fetches, DOM-node survival (JS property stamped on nodes), counter vs clicks issued during the update, `rx.set_focus` after the edit, `client_state` value, an uncontrolled `<input>` value (React remount detector), ComponentState value, todos |
| `scripts/double_edit_probe.py` | saves the source twice with a configurable gap and checks whether the second save reaches the compiled `.web/app/routes/_index.jsx` |
| `scripts/safari_test.py` | loads `/`, `/about`, `/long` with a Safari UA and a Chrome UA (browser + raw HTTP), checks the HTML is HTML, text intact, `__reflex_ts` rewriting, Safari/Chrome equality after stripping the param |
| `scripts/knobs_test.py` | per dev-server mode: first-visit latency of unvisited routes (client nav + cold full loads), dev/prod markers in the served React prebundle, fiber `_debugOwner` presence, events/navigation, and an edit → `update` vs `full-reload`, page reload count, client-state reset |
| `scripts/start_server.sh`, `stop_server.sh` | start `reflex run` in the background and wait for HTTP 200; stop it and free the ports (uses `fuser`) |
| `scripts/run_new2.sh`, `run_base_and_upgrade.sh`, `run_knobs.sh`, `run_base_safari_headmeta.sh`, `run_pre7048_safari.sh` | the exact pipelines that produced `logs/` |
| `scripts/summarize_report.py` | prints an `hmr_driver.py` report side by side |
| `logs/` | server logs (`dev_*.log`), driver reports (`hmr_*/report.json`, `driver.log`, screenshots), Safari reports, knob reports, probe JSON |

## The app (`hmr_app/hmr_app/hmr_app.py`)

Five pages (`/`, `/about`, `/long`, `/page2`, `/page3`). Index combines: `State` vars (`count`, `label`, `todos`,
`new_todo`, `bg_ticks`, `bg_running`), `rx._x.client_state` (`cs_val`), a `@rx.memo` component with state-bound
props (`counter_display(count=State.count, label=State.label)`), an `rx.ComponentState` toggle, `rx.input`
+ `rx.set_focus("todo_input")` (element refs), `rx.foreach` over todos, `rx.cond` on `count > 5`, a
`@rx.event(background=True)` ticker, and an uncontrolled `rx.el.input#scratch` used purely as a React
remount detector. `/about` has emoji/CJK/accented text, `/long` has 700 paragraphs of mixed multibyte text
(~82 KB of rendered text). `rx.App(head_components=[rx.el.title("HMR — café 日本語 🎉"), rx.el.meta(description=~70 KB
multibyte)])` puts multibyte content into the *server-rendered* head (dev mode renders route bodies client side, so
this is the only way to push >64 KB of multibyte HTML through the Safari rewriter).

Edits the driver applies (markers in the source): `text` (heading text), `default` (`label` default
"Counter" → "Compteur"), `newvar` (add `extra: int = 7` and render it), `handler` (add `add_ten` handler + button),
`props` (memo component `size="6"` → `size="8", color_scheme="red"`), `double` (two saves 0.5 s apart),
`double_long` (two saves 2.5 s apart), `hold` (change the default again while every `utils/context.jsx*` request
is held for 3 s and the page navigates to `/page3` and back during the hold — the "forced ordering" of PR #7071).

## Rerun commands

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
R=$SB/apps/hmr_runtime           # or a copy of this directory
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1   # for curl/Playwright only, never for the server

# 1. HMR runtime on 0.9.11a1 (fresh state, pristine source), then Safari test, then stop
$R/scripts/run_new2.sh                     # -> logs/dev_run2.log logs/hmr_new2/ logs/safari_new/
$SB/envs/driver/bin/python $R/scripts/summarize_report.py $R/logs/hmr_new2/report.json

# 2. Baseline 0.9.10.post2 (same app in hmr_app_base) + upgrade of that .web to 0.9.11a1
$R/scripts/run_base_and_upgrade.sh         # -> logs/dev_base.log logs/hmr_base/ logs/safari_base/ logs/double_probe_base.json
                                           #    logs/dev_upgrade.log logs/upgrade_* logs/hmr_upgrade/
# 3. Knobs (#7021), four modes on ports 3103/8103
$R/scripts/run_knobs.sh                    # -> logs/dev_knobs_<mode>.log logs/knobs_<mode>/report.json logs/knobs_<mode>_vite.config.js
# 4. Manual pieces
env -u NO_PROXY -u no_proxy $R/scripts/start_server.sh $SB/envs/smoke $R/hmr_app 3100 8100 $R/logs/dev.log $R/logs/dev.pid
$SB/envs/driver/bin/python $R/scripts/hmr_driver.py --url http://localhost:3100 --backend-port 8100 \
    --app-file $R/hmr_app/hmr_app/hmr_app.py --web-dir $R/hmr_app/.web --out $R/logs/hmr_x --label x
$SB/envs/driver/bin/python $R/scripts/double_edit_probe.py --app-file $R/hmr_app/hmr_app/hmr_app.py \
    --web-dir $R/hmr_app/.web --server-log $R/logs/dev.log --gaps 0.3,0.5,1.0 --out $R/logs/probe.json [--vary-length]
$SB/envs/driver/bin/python $R/scripts/safari_test.py --url http://localhost:3100 --out $R/logs/safari_x
curl -s --noproxy '*' -A 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15' \
    -H 'Accept: text/html' -D - http://localhost:3100/long | head -c 600
$R/scripts/stop_server.sh $R/logs/dev.pid 3100 8100
```

Always restore `scripts/hmr_app_pristine.py` over `hmr_app/hmr_app/hmr_app.py` before a driver run (the
pipelines do this).

## How a Python edit propagates in `reflex run` (context for every result below)

granian runs the backend with `reload=True` watching the app package; a save → granian stops the worker →
new worker imports the app → `app._compile()` writes `.web/**` → Vite pushes HMR frames → the new worker starts
listening ~0.6–0.75 s after the save. So **every** Python edit necessarily drops the socket.io connection once
(backend gone for ~0.6 s; the browser logs 2–5 `ERR_CONNECTION_REFUSED` attempts, then one successful
reconnect). The number to watch is *successful* socket.io connections per compile: 1 = only the unavoidable
backend restart, 2 = the frontend also tore down its provider tree. Dev mode persists state with
`StateManagerDisk`, so backend state survives the restart **unless the state schema changed** — a changed
default or a new var raises `StateSchemaMismatchError` on load and the state starts fresh (by design, both
versions; `reflex/state.py:_deserialize`, `reflex/istate/manager/disk.py:load_state`).

## Results — HMR runtime (#7071)

Per-edit results (`logs/hmr_new2/report.json` for 0.9.11a1, `logs/hmr_base/report.json` for 0.9.10.post2;
`summarize_report.py` prints these tables):

| check | 0.9.11a1 (`hmr_new2`) | 0.9.10.post2 (`hmr_base`) |
|---|---|---|
| page crash / `Cannot read properties of null` | none in 8 edits | **`TypeError: Cannot read properties of null (reading 'count_rx_state_')` at `Bare (hmr_app.jsx)`** during the `hold` edit, caught by the ErrorBoundary (plus its fallback's `Invalid DOM property stroke-linecap/…` warnings) — exactly the PR's table row |
| clicks issued during the update window counted | all (text: 12/12; handler 8/8; props 8/8; double 10/10; …). On schema-changing edits the fresh state starts at 0 and the 1 click that reached the old worker before it stopped is lost with the discarded state (7/8) | same pattern, but 6/8 on the `default` edit (2 lost) |
| `rx.set_focus` after every edit | works (8/8) | works |
| `client_state` value (`cs-changed`) | preserved across all 8 edits | **reset to `cs-initial`** on the first context-changing edit (`default`) and never recovered |
| uncontrolled `#scratch` input value | preserved through `text` and `default` (lost at `newvar` because a new sibling was inserted before it — plain React reconciliation, expected) | **lost at `default`** |
| DOM nodes stamped before the edit still present | yes for `text`/`default`/`handler`/`props`/`double*`; replaced at `newvar` (sibling insertion) and `hold` (navigation) | **replaced at `default`** (whole tree remounted) |
| successful socket.io connections per compile | 1 (single edits), 2 for the double-edit steps (two restarts) | 2 on `newvar` and `hold` (extra provider-remount reconnect) |
| browser refetches `utils/state.js` during the update | 0 in every step | 1 on every context-changing edit (`default`, `newvar`, `hold`) |
| Vite frames | `update` only, never `full-reload` | `update` only |
| `WebSocket is closed before the connection is established` / `addEvents called before EventLoopProvider mounted` | 0 | 0 |
| new handler (`add_ten`) usable right after HMR | +10 click works | works |
| memo component prop change (`size="8"`) visible after HMR | yes (`rt-r-size-8`) | yes |
| navigation to all pages after 8 edits | ok (94–340 ms) | ok |

Pre-existing behaviour observed in both versions (not regressions):

* **Background task dies with the worker.** `start_bg` ticks stop at the first edit and, because the disk
  state was flushed with `bg_running=True`, the UI shows `running` forever until the next schema reset or
  `stop bg` click (`bg_after_text_edit` in both reports). Expected for a process restart; noted as a dev-mode quirk.
* **Schema change resets the state** (see above): `todos` fall back to `["first todo"]`, toggle/ticks reset.
* **Duplicate HMR frames per compile**: each rewritten file produces 2–3 `update` frames (`context.jsx` is
  fetched 3× with `t=` values 1–2 ms apart; `_index.jsx` 2–4×). Server logs show the same duplicated
  `(client) hmr update` lines in both versions (`dev_run2.log` 34 lines / 10 reloads, `dev_base.log` 47 / 21).
  Likely the non-atomic `Path.write_text` (truncate + write) seen by chokidar as several change events.
* **`[vite] invalidate /utils/context.jsx: Could not Fast Refresh (consistent-components-exports)`** is logged
  in the browser on every context-changing compile in 0.9.11a1 (the generated module also exports
  non-components, so Vite cannot self-accept it and propagates the update to `root.jsx` + 4 importers).
  Outcome is still correct (providers re-render in place, no remount, 1 socket connection) — recorded as a
  surprising-but-benign line. Baseline (`context.js`, no JSX) never enters Fast Refresh at all.
* **`bun install --frozen-lockfile` + two `bun add` runs on every hot reload** (~8 ms each, "no changes"):
  `dev_run2.log` 11 installs + 22 adds for 10 reloads; `dev_base.log` 21 + 44 for 21 reloads. Cosmetic/CPU.
* `Debug: Unable to bind to any port for 10: [Errno 97] Address family not supported` ×2 at startup —
  this sandbox has no IPv6; both versions.
* `[vite] (ssr) page reload utils/context.jsx` (server log) on context-changing compiles — SSR module graph
  invalidation, no browser `full-reload` frame followed; both versions.

### Second save within the same second can be lost (pre-existing, both versions)

`logs/double_probe_new.json`, `logs/double_probe_new_varylen.json`, `logs/double_probe_base.json`.
Two saves of `hmr_app.py` 0.3 s or 0.5 s apart where the second edit has the **same byte length** as the
first: granian logs two reloads, but the compiled `.web/app/routes/_index.jsx` keeps the *first* edit's text
and the browser never receives the second (recovers on the next save). With a different byte length, or
a 1 s+ gap, the second save is compiled. Cause: the restarted worker imports `__pycache__/hmr_app.cpython-311.pyc`
written by the previous worker; Python's pyc validity check is source mtime (whole seconds) + size, so a
same-size save inside the same second is considered unchanged. Neither reflex nor granian sets
`sys.dont_write_bytecode`. Identical on 0.9.10.post2 (same granian 2.8.2 / watchfiles 1.2.0) → not a
regression; a realistic user hit is "fix a one-character typo and save twice".

## Results — upgrade path (#7071 stale `context.js`)

`hmr_app_base/` was initialised and run under 0.9.10.post2 (`.web/utils/` = `components context.js helpers
react-theme.js state.js theme.js`, `logs/upgrade_web_utils_before.txt`), stopped, and the **same directory**
run under 0.9.11a1 on 3102/8102 (`logs/dev_upgrade.log`). Result (`logs/upgrade_web_utils_after.txt`):
`context.js` removed, `context.jsx` + `context-registry.js` present; the web dir was re-initialised on the
version change (templates re-copied). No duplicate-module / stale-import errors in the server log or the
browser console (`logs/upgrade_index.json`: RESULT clean; counter, client_state, toggle, `/about`, `/long`
all work), and two hot edits in the upgraded directory behave like a fresh 0.9.11a1 install
(`logs/hmr_upgrade/report.json`: both OK, 1 socket connection, 0 `state.js` refetches, client state kept).

## Results — dev-server knobs (#7021)

`scripts/run_knobs.sh` starts the 0.9.11a1 dev server four times on 3103/8103 (`plain`, `prod_react`,
`warmup`, `both`), copies the generated `.web/vite.config.js` to `logs/knobs_<mode>_vite.config.js`, and runs
`scripts/knobs_test.py` (`logs/knobs_<mode>/report.json`; `python scripts/summarize_knobs.py logs` prints the table).
Generated config: `REFLEX_DEV_PROD_REACT=1` adds the `prodReactPrebundle()` resolve plugin under
`optimizeDeps.rolldownOptions.plugins`, `oxc.jsx.development: false`, the `process.env.REFLEX_DEV_PROD_REACT`
define, and `fullReload()` in `plugins`; `REFLEX_VITE_WARMUP_ROUTES=1` adds `server.warmup.clientFiles:
["./app/routes/**/*.jsx"]` — exactly what the PR describes, nothing else changes.

| | plain | prod_react | warmup | both |
|---|---|---|---|---|
| served `react.js` / `react-dom_client.js` | `react.development.js`, `react-dom-client.development.js`, "Each child in a list…" present; 2.82 MB | **only** `react.production.js` / `react-dom-client.production.js`; 1.54 MB | dev | prod |
| fiber `_debugOwner`/`_debugInfo`/`_debugStack` on a DOM node | present | **absent** (production renderer confirmed in-page) | present | absent |
| React dev-only console warnings | none | none | none | none |
| counter / client_state / ComponentState clicks, nav to 4 routes | ok | ok | ok | ok |
| first visit (client nav) `/page2` `/page3` `/about` `/long` ms | 70 / 125 / 117 / 364 | 62 / 84 / 129 / 390 | 61 / 60 / 86 / 168 | 56 / 62 / 75 / 156 |
| second visit ms | 61 / 74 / 62 / 150 | 81 / 65 / 75 / 186 | 56 / 60 / 68 / 147 | 64 / 67 / 65 / 124 |
| cold full load, fresh context (`/page2` / `/long`) ms | 907 / 894 | 925 / 943 | 874 / 899 | 916 / 894 |
| source edit → Vite frames | `update` | **`full-reload`** | `update` | `full-reload` |
| page reloads after the edit / `client_state` afterwards | 0 / kept | 1 / **reset to default** (documented) | 0 / kept | 1 / reset |
| backend counter after the edit | kept | kept (disk state) | kept | kept |
| page errors / failed requests / 4xx-5xx | 0 | 0 | 0 | 0 |

Observations:

* Warm-up does what it says on this 5-route app: the first client-side visit to an unvisited route drops
  from 60–125 ms (364 ms for `/long`) to ≈ the second-visit numbers (60–86 ms, 168 ms). Single samples on a
  shared 4-CPU box, so treat as directional; the PR's numbers were for a 68-route app.
* `prod_react` did not measurably speed up *this* tiny app (the render cost is negligible here); it is
  correctly production React (markers + fibers), events/navigation work, and an edit becomes a full page
  reload with client-only state lost, as documented. Server log shows `[vite] (client) Re-optimizing
  dependencies because vite config has changed` on the first start in a mode and the browser did one extra
  reload during the first page load (3 `[vite] connected.` vs 1 in `plain`) — Vite's normal reload after the
  dependency re-optimization; one-time.
* No new Vite / react-router warnings at startup in any mode (`logs/dev_knobs_*.log`); the only new Vite line
  is the re-optimization notice above.

## Results — Safari cache-bust plugin (#7048)

Important context discovered while testing: **reflex-base 0.9.10.post2 (uploaded 2026-09-08 15:27 UTC, five
minutes after #7048 merged) already ships the fixed plugin** — `vite-plugin-safari-cachebust.js` is
byte-identical in `$SB/envs/base0910` and `$SB/envs/smoke`. So the previous stable is not a "before" for this
fix; to prove the test can see the bug I built `$SB/envs/hmr_pre7048` with `reflex==0.9.10.post1`
(`uv pip install --python $SB/envs/hmr_pre7048/bin/python 'reflex==0.9.10.post1' 'reflex-base==0.9.10.post1'`,
run from `$SB`), whose plugin does `buffer += chunk instanceof Buffer ? chunk.toString("utf-8") : chunk`.

Dev mode renders route bodies client side (`HydrateFallback`; the served HTML is ~3.7 KB and contains no page
text), so the multibyte/chunking scenario is exercised through `rx.App(head_components=...)`: a `<title>` with
emoji/CJK and a ~70 KB `<meta name="description">` of mixed multibyte text, which React streams in several
chunks (served HTML 92.7 KB, `transfer-encoding: chunked`).

`scripts/safari_test.py` (Chromium with a Safari UA and a Chrome UA, plus raw HTTP fetches) and
`scripts/curl_safari.sh` (curl with the UAs, header dump, byte checks) results:

| server | Safari-UA `/`, `/about`, `/long` | Chrome-UA |
|---|---|---|
| 0.9.11a1 (`logs/safari_new_headmeta/`, `logs/curl_safari_new.txt`) | real HTML (`<!DOCTYPE html>…<title>HMR — café 日本語 🎉</title><meta content="Paragraph 0: café naïve …`), 92,767 B, `x-modified-by: vite-plugin-safari-cachebust`, 3 `<link rel=modulepreload>` + 3 inline-script imports rewritten (6 `__reflex_ts`), valid UTF-8, 0 U+FFFD, 561× `日本語` and 561× 🎉 intact, all 9 `?__reflex_ts=` module requests load, 0 console/page errors, app interactive, `/long` renders 700 paragraphs (82,548 chars, no U+FFFD); **identical to the Chrome-UA body after stripping the param** | plain HTML, no header, 0 rewrites |
| 0.9.10.post2 (`logs/safari_base/`, `logs/safari_base_headmeta/`) | same as above (same plugin) | same |
| 0.9.10.post1, pre-#7048 (`logs/curl_safari_pre7048.txt`, `logs/safari_pre7048/`) | **body is `60,33,68,79,67,84,89,80,69,32,104,…`** — 347,589 B of comma-separated byte values with `content-type: text/html`, 0 rewrites, no text; the browser never renders the app (`#heading` never appears) | proper HTML, 92,578 B |

Small-HTML runs without the head meta (`logs/safari_new/`, `logs/safari_base/`) gave the same verdicts on
3.7 KB pages. Server log line for the rewrite: `[vite-plugin-safari-cachebust] Rewrote 3 modulepreload links with __reflex_ts param.`

## Issues / anomalies summary (with regression status)

| # | what | severity | 0.9.10.post2 differs? | evidence |
|---|---|---|---|---|
| 1 | Two saves of the app module within the same wall-clock second with identical byte length: the second save is compiled from stale `__pycache__` bytecode and never reaches the browser until the next save (pyc mtime-second+size check; granian restarts the worker twice, the second import reuses the cached pyc) | low (dev-only, needs same-size edit inside 1 s) | no — identical on baseline → not a regression | `logs/double_probe_new.json` (lost at 0.3 s/0.5 s), `logs/double_probe_new_varylen.json` (different length → fine), `logs/double_probe_base.json`; `logs/hmr_new/report.json` step `double` (first run, compiled heading v3 vs source v4) |
| 2 | Browser logs `[vite] invalidate /utils/context.jsx: Could not Fast Refresh (consistent-components-exports)` on every context-changing compile; update propagates to `root.jsx` + 4 importers. Behaviour is nevertheless correct (providers re-render in place, 1 socket connection, client state kept) | low / informational | baseline never fast-refreshes `context.js` at all (remounts) | `logs/hmr_new2/report.json` console_all; `logs/dev_run2.log` "(client) hmr invalidate" |
| 3 | Every compiled file yields 2–3 duplicate Vite `update` frames per compile (`context.jsx` fetched 3× within 2 ms) | low | same on baseline | `logs/hmr_new2/report.json` `context_fetches`, `logs/dev_run2.log` vs `logs/dev_base.log` "(client) hmr update" counts |
| 4 | Every hot reload re-runs `bun install --frozen-lockfile` + 2× `bun add` (no-ops, ~8 ms each) and re-copies the lockfile | low | same on baseline | `logs/dev_run2.log` (11 installs/22 adds for 10 reloads), `logs/dev_base.log` (21/44 for 21) |
| 5 | Background task killed by the worker restart leaves the UI at `running`/stale ticks until the next event | low (inherent to process reload) | same on baseline | `bg_after_text_edit` in both driver reports |
| 6 | `REFLEX_DEV_PROD_REACT=1`: one extra full page reload on the first load after toggling the knob (Vite re-optimizes deps because the config changed) | informational | n/a (knob is new) | `logs/dev_knobs_prod_react.log` line 162, `logs/knobs_prod_react/report.json` console_all (3× `[vite] connected.`) |

No defect specific to 0.9.11a1 was found in this cluster. The PR #7071 verification table reproduces as a user:
the baseline crashes with `Cannot read properties of null (reading 'count_rx_state_')` under the held-context +
navigation sequence and remounts the provider tree on every context change (client state lost, `state.js`
refetched, extra socket connection); 0.9.11a1 does none of that across 8 edits, in a fresh install and in a
`.web` upgraded from 0.9.10.post2.

## Processes

Every server was started by `scripts/start_server.sh` (pid files in `logs/*.pid`, removed from the copy) and
stopped with `scripts/stop_server.sh`; the final `ps aux | grep -E 'reflex|vite|granian|bun|chrom'` check at
the end of the session showed none of this cluster's processes left (other agents' servers on other ports were
running on the shared machine).
