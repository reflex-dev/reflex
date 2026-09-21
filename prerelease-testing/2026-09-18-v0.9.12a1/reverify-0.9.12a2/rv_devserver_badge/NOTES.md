# rv_devserver_badge — Phase 7 re-verification of reflex 0.9.12a2

Scope: Phase-1 smoke, **FINDING-017 / #7213** (dev supervisor socket), **FINDING-012 / #6143**
(data_editor `#portal` swallowed by the sticky badge) and the dev-server surface touched by
**#7217**. Everything ran against packages installed from PyPI only; nothing was installed from
`/home/user/reflex`, and no python was ever run with a checkout as cwd.

Ports used: frontend 3220-3231, backend 8220-8228 (reserved 3220-3239 / 8220-8239). No redis.
All servers were killed by pgid; `$SB/bin/ports.py` reports nothing bound on the whole range
(see **Cleanup**).

## Environments

```
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
$SB/envs/a2      reflex 0.9.12a2  (the tree under test)
$SB/envs/shared  reflex 0.9.12a1  (= "a1", the alpha the campaign tested)
$SB/envs/prev    reflex 0.9.11.post1 (previous stable baseline)
$SB/envs/driver  playwright 1.63, chromium /opt/pw-browsers/chromium
$SB/reverify/rv_devserver_badge/venv   my own venv: a2 + plotly/pandas/httpx (for the gallery app)
```

`uv pip freeze --python $SB/envs/a2/bin/python | grep -i reflex`:

```
reflex==0.9.12a2  reflex-base==0.9.12a2
reflex-components-code==0.9.6a1   reflex-components-core==0.9.10a1
reflex-components-dataeditor==0.9.3a1  reflex-components-gridjs==0.9.2a1
reflex-components-lucide==1.0.4   reflex-components-markdown==0.9.4a1
reflex-components-moment==0.9.4   reflex-components-plotly==0.9.7a1
reflex-components-radix==0.9.10a1 reflex-components-react-player==0.9.2
reflex-components-recharts==0.9.4a1 reflex-components-sonner==0.9.4a1
reflex-hosting-cli==0.1.72
```

My own venv (needed because the gallery app imports plotly/pandas), created from `$SB`, never
from a checkout, with every component alpha named explicitly:

```bash
cd $SB && uv venv $SB/reverify/rv_devserver_badge/venv --python 3.11
uv pip install --python $SB/reverify/rv_devserver_badge/venv/bin/python --prerelease=allow \
  'reflex==0.9.12a2' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
  'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
  'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
  'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
  'reflex-components-sonner==0.9.4a1' 'reflex-components-lucide' plotly pandas httpx
# resolves: reflex 0.9.12a2, reflex-base 0.9.12a2, the alphas above, plotly 7.1.0, pandas 3.0.6
```

## Result table

| # | check | a2 | a1 | prev | evidence |
|---|---|---|---|---|---|
| 1 | Smoke — `reflex init --template blank`, dev run + Chromium | **PASS** clean | (campaign) | — | `logs/smoke_run.txt`, `logs/smoke_dev_report.json`, `shots/smoke_dev_index.png` |
| 1b | Smoke — `reflex run --env prod` single port + Chromium | **PASS** clean, badge renders | (campaign) | — | `logs/smoke_prod_report.json`, `shots/smoke_prod_index.png` |
| 1c | `.web/package.json` vs the campaign's `smoke/logs/web_package.json` | **PASS** byte-identical (`diff` exit 0) | — | — | `logs/web_package_a2.json` |
| 2a | FINDING-017 `break_reload_probe.py` (broken app module, no signals) | **PASS** `CONNECTION_REFUSED` 0.00 s at +10 s and +24 s, `200` after the fix | **FAIL** `TIMEOUT_NO_REPLY_6s` twice | `CONNECTION_REFUSED` | `logs/breakreload_{a2,a1,prev}.json` |
| 2b | #7114 intact — 20 Hz `/ping` across two hot reloads | **PASS** 806 pings, 0 refused, 0 errors, max 0.202 s | — | — | `logs/hotreload_a2.json`, `logs/hotreload_a2.tsv` |
| 2c | `sigterm_port_probe.py` (SIGTERM to the pid alone) | **PASS** `CONNECTION_REFUSED` at +8 s/+18 s, like prev | (`TIMEOUT_NO_REPLY_6s`) | `CONNECTION_REFUSED` | `logs/portprobe_a2.json` |
| 2d | FINDING-018 unchanged (`reflex run` ignores SIGTERM to its own pid) | unchanged: `still_alive=true` | — | same | `logs/portprobe_a2.json` |
| 2e | SIGINT to the process group of a normal dev session | **PASS** exit 0 in 1.03 s, no listener left | — | — | `logs/sigint_run.txt`, `logs/sigint_a2.trimmed.log` |
| 3a | FINDING-012 — `vapp` prod, DEFAULT badge | **PASS** `#portal` exists, badge present, carousel opens, no "portal not found" | **FAIL** `portal_exists=false`, 2x "portal not found" | (campaign: fails) | `out/editor_a2.json`, `out/editor_a1.json`, `shots/a2-editor.png` |
| 3b | compiled `root.jsx` nesting | **PASS** badge and `#portal` are siblings in a `Fragment` | badge is the **parent** of `#portal` | — | `out/root_a2.jsx` vs `out/root_a1.jsx` |
| 3c | wider gallery surface in prod (data_editor / recharts / plotly / sonner / code / misc) | **PASS** identical to the campaign's a1 prod run except the overlay now opens; 0 page errors / 0 failed requests / 0 responses >= 400 | (campaign `components_bumps/shots/prod-results.json`) | — | `out/gprod-results.json`, `shots/gprod-*.png` |
| 4a | hot reload end to end in a held-open browser | **PASS** new heading in 1.0 s, backend answered `200` throughout, state events still work | — | — | `out/hr_a2.json`, `shots/hr-{before,after}.png` |
| 4b | `--backend-only` then `--frontend-only` pairing | **PASS** events flow, 0 console errors; `.web/nocompile` absent (#7089 intact) | — | — | `out/split_a2.json`, `logs/split_{backend,frontend}.log` |
| 4c | `reflex run --json` (#7193) still JSON | **PASS** 247/270 lines JSON, 26 `_granian*` records | — | — | `logs/devsurface_a2.log` |
| 4d | syntax error saved mid-run, then fixed | **PASS** `CONNECTION_REFUSED` (fast) at +12 s/+20 s, back to `200` 2.0 s after the fix | — | — | `out/hr_a2.json` |

## What each check ran

```bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/reverify/rv_devserver_badge
export REFLEX_TELEMETRY_ENABLED=false

# 1  smoke (init + dev 3220/8220 + prod 3221, driven by the skill's drive_app.py)
bash $W/scripts/run_smoke_a2.sh

# 2a FINDING-017, the campaign verifier's own probe, unchanged
python3 $W/scripts/break_reload_probe.py $SB/envs/a2     $W/apps/dsc_a2   3222 8222 a2   $W/logs
python3 $W/scripts/break_reload_probe.py $SB/envs/shared $W/apps/dsc_a1   3223 8223 a1   $W/logs
python3 $W/scripts/break_reload_probe.py $SB/envs/prev   $W/apps/dsc_prev 3224 8224 prev $W/logs

# 2b #7114 intact: 20 Hz /ping for 42 s with a HEADING edit at +8 s and +24 s
python3 $W/scripts/hotreload_ping_a2.py $SB/envs/a2 $W/apps/dsc_a2 3225 8225 a2 $W/logs

# 2c/2d SIGTERM to the pid alone
python3 $W/scripts/sigterm_port_probe.py $SB/envs/a2 $W/apps/dsc_a2 3226 8226 a2 $W/logs

# 2e + 4a/4c/4d  dev surface: --json run on 3227/8227, held-open browser, SIGINT to the group
bash $W/scripts/devsurface_a2.sh          # runs scripts/hr_browser.py in the driver venv

# 4b split run
bash $W/scripts/split_run_a2.sh           # backend-only 8228, then frontend-only 3228

# 3a/3b FINDING-012 (vapp, default badge, prod on ONE port)
bash $W/scripts/vapp_prod.sh $SB/envs/a2     $W/apps/vapp    3229 a2
bash $W/scripts/vapp_prod.sh $SB/envs/shared $W/apps/vapp_a1 3230 a1

# 3c gallery in prod on my own a2 venv
bash $W/scripts/gallery_prod_a2.sh        # prod 3231 + drive.py + portal_probe.py
```

Apps: `apps/dsc_*` are copies of `dev_server_cli/{dsc,dsc_prev}`; `apps/vapp*` a copy of
`components_bumps/verification/vapp`; `apps/gallery` a copy of `components_bumps/gallery`.

> Two artifact-copy gaps to know about before re-running 3a/3c (neither is a reflex defect):
> the archived `components_bumps/verification/vapp/` has no `vapp/__init__.py`, so the first prod
> run dies with `AttributeError: module 'vapp' has no attribute 'app'` — `touch
> vapp/vapp/__init__.py` first; and `components_bumps/gallery/gallery/gallery.py` line 10 asserts
> `"/envs/cb/" in rx.__file__`, the explorer's venv, so point it at your own venv (I replaced it
> with `"/reverify/rv_devserver_badge/venv/"`).

## FINDING-017 / #7217 — fixed

`break_reload_probe.py` appends `raise RuntimeError("BOOM injected by verifier")` to the running
app module — the ordinary "developer saved a broken file" case, no signals involved.

| | before break | +10 s | +24 s | after the file is restored |
|---|---|---|---|---|
| **0.9.12a2** | `200` / 0.00 s | **`CONNECTION_REFUSED` / 0.00 s** | **`CONNECTION_REFUSED` / 0.00 s** | `200` / 0.03 s |
| 0.9.12a1 | `200` / 0.00 s | `TIMEOUT_NO_REPLY_6s` / 6.01 s | `TIMEOUT_NO_REPLY_6s` / 6.00 s | `200` / 0.02 s |
| 0.9.11.post1 | `200` / 0.00 s | `CONNECTION_REFUSED` / 0.00 s | `CONNECTION_REFUSED` / 0.00 s | `200` / 0.02 s |

a2 now behaves exactly like the previous stable: fail fast while no worker can serve, recover
on its own once the module imports again (`supervisor_alive_end: true` in all three runs).

**#7114 is intact.** 42 s of `/ping` at 20 Hz across two `HEADING` edits: **806 requests, 0
refused, 0 errors**, slowest two responses 0.202 s and 0.179 s — and those two land at t=8.17 s
and t=24.14 s, i.e. exactly on the two edits, which is the socket staying bound while the worker
is replaced. Five distinct worker pids logged `APP_MODULE_IMPORT` during the window
(`logs/hotreload_a2.log`), so the reloads really happened. Final `/ping` 200.

**FINDING-018 is unchanged** (pre-existing, as expected): SIGTERM to the `reflex run` pid alone
still does not stop the dev server (`still_alive: true`). What changed is only the port: a2 now
answers `CONNECTION_REFUSED` at +8 s and +18 s where a1 answered `TIMEOUT_NO_REPLY_6s`.

A normal dev session **does** stop on SIGINT to the process group: `exit_code=0` after 1.03 s,
and `ports.py` reports nothing bound afterwards — measured twice, once at the end of the
`--json` dev-surface run on 3227/8227 and once in a dedicated run on 3232/8232
(`bash $W/scripts/sigint_group_a2.sh`, `logs/sigint_run.txt`). The log tail is
`App running at … / Backend running at … / [ERROR] Unexpected exit from worker-1 / Info: Reflex
app stopped.` — that ERROR line is granian's own cosmetic message, present identically on
0.9.11.post1 and on a1 (campaign issue 3), so it is unchanged, not new.

Client-visible consequence of the fix, worth knowing but correct: while the app module is broken
the browser logs `WebSocket connection to 'ws://…/_event/…' failed: … ERR_CONNECTION_REFUSED`
(15 of them in `out/hr_a2.json`, all inside the deliberate break window, the first one
`ERR_CONNECTION_RESET` as the socket closes). On a1 those attempts hung instead. 0.9.11.post1
refuses the same way, so this is the restored baseline, not a new problem.

## FINDING-012 / #7218 — fixed

`vapp` in prod on ONE port with the **default** badge setting (`show_built_with_reflex` unset):

| | `#portal` | badge | carousel opens | console |
|---|---|---|---|---|
| **0.9.12a2** | **true** (parent `DIV`) | **true** | **yes** — `.carousel-root` with control dots, imgs `/green.png`,`/red.png` | only the pre-existing 404 |
| 0.9.12a1 | false | true | no | 2x `Cannot open Data Grid overlay editor, because portal not found.` |

`carousel_css_rules: 40` in both. The single `Failed to load resource: … 404` line appears in
every campaign run too, including 0.9.11.post1 and the `show_built_with_reflex=False` A/B
(`components_bumps/verification/logs/prod_nobadge_results.json`) — pre-existing, not new.

The compiled `root.jsx` shows the fix directly:

```jsx
// 0.9.12a1 — the portal is a CHILD of a component that renders no children
jsx(Fragment,{},children,jsx(MemoizedBadge_04c36749,{},jsx("div",{...,id:"portal"},)))

// 0.9.12a2 — badge and portal are SIBLINGS
jsx(Fragment,{},children,jsx(Fragment,{},jsx(MemoizedBadge_04c36749,{},),jsx("div",{...,id:"portal"},)))
```

### Wider gallery surface in prod (check 3c)

The campaign's 9-page `components_bumps/gallery` app, prod on one port (3231), driven by the
cluster's own `drive.py` and `portal_probe.py`. I diffed my `gprod-results.json` against the
campaign's a1 `components_bumps/shots/prod-results.json` section by section:

* `code`, `misc`, `plotly`, `props`, `sankey`, `toast` — **zero differing keys**.
* `editor` — the only difference, and it is the fix: `overlay_imgs` `[]` → `['/green.png',
  '/red.png','/green.png','/red.png']`, `overlay_present` 4 → 11.
* `nav` — differs only in the port in the recorded URL.
* console: a1 had the 404 plus **three** `Cannot open Data Grid overlay editor …` errors; a2 has
  **only** the pre-existing 404 (on `/sankey/`). `pageerrors`, `failed_requests`,
  `bad_responses` are all empty on both.
* `portal_probe.py` on a2 prod: `carousel_root` present with control dots, 8 `.carousel` CSS
  rules matched, overlay images loaded.

So the badge fix changed exactly what it was meant to and nothing else in that surface.

## Dev-server surface (#7217's blast radius)

* **Hot reload, browser held open** (`out/hr_a2.json`): heading `dsc v5-reload` → `dsc
  v6-HOTRELOAD` visible **1.0 s** after the save without a manual reload; both `/ping` probes
  taken during the reload returned `200` in 0.02 s; after the reload a click on `#inc` still
  increments (1 → 2) and the `@rx.memo` child follows, so the socket, the websocket and the state
  survived. 0 page errors, 0 failed requests, 0 responses >= 400.
* **Syntax error mid-run**: `def broken(:` saved into the running module → `/ping`
  `CONNECTION_REFUSED` in 0.00 s at +12 s and +20 s (a1 would hang for the client timeout);
  restoring the file brings `/ping` back to `200` in **2.0 s** and the page renders again.
* **`--json` (#7193)**: 270 non-blank lines, **247 valid JSON**, 26 records from `_granian` /
  `_granian.serve` (`Starting granian`, `Listening at`, `Spawning worker-1`, `Changes detected,
  reloading workers..`, `Stopping/Stopped worker-1`, `Shutting down granian`, …). Of the 23
  non-JSON lines, 5 are the test app's own stdlib `logging` output (the known, documented
  a1 anomaly — user `logging` is not routed through the JSON pipeline) and 18 are the Python
  traceback of the SyntaxError I injected on purpose. No regression.
* **`--backend-only` + `--frontend-only`**: backend answered `/ping` 200 in 1 s, `.web/nocompile`
  absent (#7089 intact); `reflex run --frontend-only --frontend-port 3228` with
  `REFLEX_API_URL=http://localhost:8228` served 200 in 2 s and the page's events reached the
  separate backend (`inc` → 1, `chained@1`, `add` → `item-1`), clean report.
  Usage note: `--frontend-only` together with `--backend-port` exits with
  `Cannot specify --backend-port when not running backend.` — an explicit CLI guard, same shape
  as the prod split-port guard; not a defect.

## Smoke

`reflex init --template blank` exit 0 (only the known npmmirror fallback noise). Dev: frontend
200 after 20 s including the bun install; Chromium report `clean` — 0 console messages, 0 page
errors, 0 failed requests, 0 4xx/5xx; `/ping` → `"pong"`, `/_health` → 200. Prod: 200 after 5 s,
`clean`, the "Built with Reflex" badge renders. Bun 1.4.0, Node 22.22.2.
`.web/package.json` is **byte-identical** to the campaign's a1 copy (`diff` exit 0), so the
`"mergician": "v2.0.2"` leading-`v` nit is unchanged and nothing else moved.
`Debug: error: script "dev" exited with code 143` on shutdown is bun's own debug line, present
in the campaign's a1 smoke too.

## Benign noise seen (not findings)

* `[ERROR] Unexpected exit from worker-1` after the deliberately broken module — granian's own
  message, pre-existing on 0.9.11.post1 (campaign issue 3).
* The `SitemapPlugin` "enabled by default" warning, the `@rx.memo` annotation deprecation and the
  implicit-Radix-Themes deprecation in the test apps' logs — all pre-existing.
* One `Failed to load resource: … 404` on the vapp/gallery pages — present on every version
  including 0.9.11.post1.
* vite `hot updated: …` debug lines and the React DevTools info line in the browser console.

## Cleanup

Every server was killed by pid/pgid (never a pattern kill). Final check:
`uv run --no-project python $SB/bin/ports.py $(seq 3220 3239) $(seq 8220 8239)` → empty.
