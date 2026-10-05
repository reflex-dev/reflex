# Cluster `up_examples_c` — upgrade regression 0.9.11.post1 -> 0.9.12a1

Batch C of the reflex-examples upgrade sweep: components, routing and custom JS.
Everything here was run against packages installed **from PyPI only** — nothing was
installed from the `/home/user/reflex` checkout, and no Python was ever run with the
checkout as its working directory.

**Result: no regressions found.** Four apps (`local-component`, `quiz`, `traversal`,
`nba`) were driven end to end in Chromium. Every flow that worked on 0.9.11.post1 still
works on 0.9.12a1, with byte-identical driver output on the app that was baselined
flow-for-flow. Three of the changelog items this batch targets were positively confirmed
working (#6850 auto-memo prop/ref transparency, #7068 router base-var rename, #6977
plotly `id` -> `divId`). Two findings are recorded below, both non-blocking: one
pre-existing React warning (present identically on the old version) and one
observation that contradicts a previous campaign's packaging note.

---

## Environment

Machine: 4 CPU / 15 GB, shared with other QA agents. Ports used: frontend 3540-3545,
backend 8540-8545 (my reserved range). No redis needed.

Venv actually used — `$SB/envs/upc`, Python 3.11.15. This venv started the session at
0.9.11.post1 and was upgraded **in place** (that is the point of the exercise):

```
$ uv pip freeze --python $SB/envs/upc/bin/python | grep -i reflex
reflex==0.9.12a1
reflex-base==0.9.12a1
reflex-components-code==0.9.6a1
reflex-components-core==0.9.10a1
reflex-components-dataeditor==0.9.3a1
reflex-components-gridjs==0.9.2a1
reflex-components-lucide==1.0.4
reflex-components-markdown==0.9.4a1
reflex-components-moment==0.9.4
reflex-components-plotly==0.9.7a1
reflex-components-radix==0.9.10a1
reflex-components-react-player==0.9.2
reflex-components-recharts==0.9.4a1
reflex-components-sonner==0.9.4a1
reflex-hosting-cli==0.1.72
```

Baseline venv: `$SB/envs/prev` (reflex 0.9.11.post1 + matching stable components),
used unmodified for the `quiz` baseline.

`SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad`

---

## How to re-run everything from scratch

```bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
mkdir -p $SB/apps/up_examples_c && cd $SB          # NEVER cd into /home/user/reflex

# 1. apps (copied out of the reflex-examples checkout, never run in place)
for app in local-component quiz traversal nba; do
  cp -r /home/user/reflex-dev/reflex-examples/$app $SB/apps/up_examples_c/$app
done
# then copy this artifact dir's apps/ over the top to pick up the nba stub patches:
#   cp -r <this dir>/apps/nba $SB/apps/up_examples_c/

# 2. BASELINE venv (no --prerelease, so it resolves the way a real user's would)
uv venv $SB/envs/upc --python 3.11
uv pip install --python $SB/envs/upc/bin/python \
    'reflex==0.9.11.post1' 'pandas==3.0.1' 'plotly==6.6.0' \
    'statsmodels==0.14.6' 'scipy==1.17.1'

# 3. run + drive at baseline (see per-app commands below)

# 4. IN-PLACE UPGRADE of the same venv, same app dirs, preserving .web/ and reflex.lock/
uv pip install --python $SB/envs/upc/bin/python --upgrade --prerelease=allow \
    'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' \
    'reflex-components-radix==0.9.10a1' 'reflex-components-code==0.9.6a1' \
    'reflex-components-dataeditor==0.9.3a1' 'reflex-components-gridjs==0.9.2a1' \
    'reflex-components-markdown==0.9.4a1' 'reflex-components-plotly==0.9.7a1' \
    'reflex-components-recharts==0.9.4a1' 'reflex-components-sonner==0.9.4a1'
```

Server launcher (`scripts/_run.sh`, backgrounds `reflex run` into a log file):

```bash
bash scripts/_run.sh <appdir> <logname> <frontend-port> <backend-port> [extra reflex args]
# prod mode takes ONE port for both flags:
bash scripts/_run.sh local-component lc_prod 3541 3541 --env prod
```

Drivers (run with the Playwright venv; the `NO_PROXY` prefix is required for localhost,
and must NOT be exported into the server's environment):

```bash
cd $SB/apps/up_examples_c
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python _scripts/drive_local_component.py http://localhost:3540/ <label> <shots_dir>
# same shape for drive_quiz.py, drive_traversal.py, drive_nba.py
```

Each driver prints one JSON blob: a `results` map of the flow assertions plus
`console_errors`, `console_warnings`, `page_errors`, `failed_requests` and
`bad_responses` (any HTTP >= 400). Screenshots land in `<shots_dir>`.

---

## What was tested, per app

### 1. `local-component` — FULL protocol (baseline / upgrade / cold / prod)

The only app taken through all four stages of the upgrade protocol, because it is the
one that exercises this train's riskiest change: a local React component
(`library = "/public/<asset>"`, `React.forwardRef`) wrapped in a Radix popover with a
form. That combination is exactly what #6850 (auto-memoized components must preserve
parent props, refs, styles and event handlers) can break.

Nine flows, all driven in the browser (`scripts/drive_local_component.py`):

1. local `Hello` component renders (`Hello world!`)
2. `id="greeting"` reaches the real DOM node through `forwardRef` + auto-memo
3. `background_color` (a `rx.color_mode_cond`) reaches the DOM
4. `title` attribute passes through
5. right-click toggles the component's own `useState` caps **and** fires the Reflex
   `rx.console_log(...).prevent_default` handler (event passthrough)
6. left-click opens the popover (`State.open` round trip)
7. typing in the popover input live-updates the greeting via `State.who`
8. form submit persists `saved_value` and closes the popover; reopening + `Escape`
   reverts to the saved value
9. `rx.scroll_to("greeting")` from a button 150vh down actually scrolls (this only
   works if the `id` survived memoization), then a full reload re-hydrates cleanly

**All four runs produced identical `results` blocks**, including the scroll numbers
(`scrollY` 1335 -> 429 every time) and the color-mode background flip
(`rgb(255,239,213)` -> `rgb(102,51,153)`). Zero console errors, zero page errors, zero
failed requests, zero 4xx/5xx in every run.

| stage | log | screenshots |
|---|---|---|
| baseline 0.9.11.post1 | `logs/lc_baseline2.tail.log` | `shots/lc_base_*.png` |
| in-place upgrade, `.web/` preserved | `logs/lc_upgrade1.tail.log` | `shots/lc_up_*.png` |
| cold (`rm -rf .web`) | `logs/lc_cold.tail.log` | `shots/lc_cold_*.png` |
| prod (`--env prod`, port 3541) | `logs/lc_prod.tail.log` | `shots/lc_prod_*.png` |

**First post-upgrade run was clean.** No migration output, no lockfile complaint, no
bun peer-dependency churn, no state-schema or hydration warning in the browser — the
frontend simply recompiled. Worth stating explicitly because the protocol flags this as
the likely failure point: this train renames the router state keys (#7068), so a `.web/`
built by 0.9.11.post1 *must* be recompiled. It was, silently and correctly. Verified
directly in the compiled output:

```
$ grep -roh "rx_router_[a-z_]*" .web/utils/ .web/app/ | sort -u
rx_router_headers_rx_state_
rx_router_page_rx_state_
rx_router_route_id_rx_state_
rx_router_session_rx_state_
rx_router_url_rx_state_
```

`.web/package.json` diff across the upgrade (`evidence/lc_package.json.{BEFORE,AFTER}`):

```
-    "@react-router/node": "8.3.1"      +    "@react-router/node": "8.4.0"
-    "react-router": "8.3.1"            +    "react-router": "8.4.0"
-    "@react-router/dev": "8.3.1"       +    "@react-router/dev": "8.4.0"
-    "@react-router/fs-routes": "8.3.1" +    "@react-router/fs-routes": "8.4.0"
                                        +    "mergician": "v2.0.2"     (NEW)
```

react-router 8.3.1 -> 8.4.0 is changelogged (#7202). `mergician` is a **new frontend
runtime dependency** that is not called out in any changelog — see observation (B).

### 2. `quiz` — 0.9.12a1 vs 0.9.11.post1, flow-for-flow

Multi-step form + cross-page routing, the natural place for the #7068 router rename to
show up. Both versions were run and driven identically (`scripts/drive_quiz.py`); the
0.9.11.post1 run used a pristine copy of the app dir (`quiz_prev`) against `$SB/envs/prev`.

Flows: `rx.code_block` renders question 2's Python snippet; answer 2 radios + 3 of 5
checkboxes; Submit -> `rx.redirect("/result")`; results page shows `100%`, a 3-row table
and the progress bar; browser **back** to `/` re-fires `on_load` and resets the answers
(0 checkboxes checked); direct load of `/result` in a fresh session renders.

**The two runs' `results` blocks are identical field for field** — same title, same
score, same table row count, same post-back reset, same direct-load behaviour. The only
console output on both versions is the same React checkbox warning, three times; see
finding (A). No errors, no failed requests, no 4xx/5xx on either version.

Logs `logs/quiz_new.tail.log` (0.9.12a1, port 3542) and `logs/quiz_prev.tail.log`
(0.9.11.post1, port 3543). Screenshots `shots/quiz_new_*.png` / `shots/quiz_prev_*.png`.

### 3. `traversal` — 0.9.12a1 only

Note for whoever wrote the brief: this app is **not** a sidebar/multi-route app. It is a
7x7 pathfinding grid — a `rx.foreach` over a 2D list, a `deque` behind a custom
`@serializer`, and an async event handler that **re-chains itself** (`return
GraphState.run_bfs`) once every 10 ms until it finds the target. That self-chaining loop
is directly relevant to #7145 (`RecursionError` in the event processor when a handler
re-chains itself many times), so it was worth running for that reason instead.

Flows (`scripts/drive_traversal.py`): initial 7x7 grid renders with 49 cells in four
colours; "Generate Graph" produces a different grid; select BFS -> Run paints 42 cells
yellow as the loop walks the grid; "Clear" restores the generated grid exactly; select
DFS -> Run repaints; reload re-renders 49 cells.

All pass. **No `RecursionError`, no console error, no page error, no failed request** —
the ~42-iteration self-chain completed and terminated cleanly, and the following
navigation/reload was clean too.

The `rx.toast.success("Path found to [i,j]")` that ends the run was confirmed
separately (`shots/trav_new_07_toast.png`, text `Path found to [2,3]`, one
`[data-sonner-toast]` node). My first driver pass reported no toast — that was my
measurement window, not the app: sonner auto-dismisses before the 9 s mark. Corrected.

Log `logs/trav_new.tail.log` (port 3544), screenshots `shots/trav_new_*.png`.

### 4. `nba` — 0.9.12a1 only, with a stub

pandas + plotly + statsmodels: `rx.data_table` (gridjs) fed a DataFrame, and two
`rx.plotly` charts computed in `@rx.var`s. Targets the on-demand pandas/plotly
serializers (#7049) and the plotly `divId` fix (#6977).

**Stub (recorded as required):** the app does `pd.read_csv("https://media.geeksforgeeks.org/
wp-content/uploads/nba.csv")` at import time, and that host is blocked by this
environment's egress proxy (`URLError: Tunnel connection failed: 403 Forbidden` — the
app cannot even start). I generated `nba/nba_local.csv`, 320 rows with the same nine
columns (Name, Team, Number, Position, Age, Height, Weight, College, Salary), and
patched `nba/views/table.py` to read that path instead. The patch is marked with a
`# QA STUB` comment and is included in `apps/nba/`. Nothing else about the app changed.

**Deliberate probe for #6977:** I added `id="scatter-chart"` to the scatter
`rx.plotly(...)` in `nba/views/stats.py` (upstream passes no id). The changelog says the
`id` prop should now be rendered as react-plotly.js's `divId`, which is the only id prop
the library forwards to its container div. Confirmed working:

```
"plot_ids": ["scatter-chart", ""],
"scatter_by_selector": 1,          # document.querySelector('#scatter-chart')
"scatter_is_plotly": true,         # that element carries .js-plotly-plot
"id_survives_filter": true,        # still there after a state-driven re-render
"scatter_id_after_reload": true
```

Other flows, all passing: gridjs renders all nine columns with "Showing 1 to 10 of 320
results"; pagination advances to a different first row; search box accepts input;
selecting position "PG" recomputes **both** charts server-side (see
`shots/nba_new_02_filter_pg.png` — the scatter drops from five position series to one,
the lowess trendline from statsmodels is recomputed, and the histogram rescales from
~470M to ~220M); reload re-renders both charts and the grid.

No console errors, no page errors, no failed requests, no 4xx/5xx.

One thing that is **not** a bug: the gridjs table keeps showing all 320 rows when a
filter is applied. That is the app's own code — `table()` binds `data=nba_data` (the
unfiltered module-level DataFrame) while only the charts read the filtered `State.df`.
Same on any version.

Ignore the `"points": 0` fields in `results` — that was a bad metric in my driver
(plotly keeps trace data in typed arrays that my expression did not reach). The
screenshots are the evidence that the charts carry data.

### 5. Not run — `github-stats`, `linkinbio`, `json-tree`, `overkey`

Out of timebox, not out of interest. They are copied into `$SB/apps/up_examples_c/` and
ready to go. Notes for whoever picks them up:

- `github-stats` needs the GitHub API, which is likely proxy-blocked the same way the
  nba CSV is — stub `github_stats/fetchers.py` and test the recharts charts (#6833 prop
  routing, the one changelog item in this batch that went untested) and the form.
- `linkinbio` declares `launchdarkly-server-sdk==9.8.0`; stub or disable the SDK. It
  uses `rx.moment`, which stayed at stable 0.9.4 this train.
- `json-tree` and `overkey` are small (custom component / keyboard handling).

---

## Findings

### (A) Pre-existing React "uncontrolled to controlled" warning on `rx.checkbox` — LOW, not a regression

`quiz` logs this browser console warning once per checkbox clicked (3 times in the run):

```
Checkbox is changing from uncontrolled to controlled. Components should not switch from
controlled to uncontrolled (or vice versa). Decide between using a controlled or
uncontrolled value for the lifetime of the component.
```

Cause is the app's own usage: `rx.checkbox(text=..., on_change=...)` with no `checked`
prop, so Radix starts uncontrolled and flips once state arrives.

**Baseline checked: yes.** 0.9.11.post1 emits the identical warning, the same number of
times, in the same place. Pre-existing, not introduced by this train. Functionality is
unaffected (the quiz still scores 100%). Recorded so nobody re-discovers it and files it
against 0.9.12a1.

Repro: run `quiz` on either version, tick any checkbox, watch the console. Evidence:
the `console_warnings` arrays in both driver runs; `shots/quiz_new_02_answered.png`.

### (B) Naive `--upgrade --prerelease=allow 'reflex==0.9.12a1'` DOES pull every component alpha — contradicts a prior campaign note

The upgrade protocol says to record what a naive upgrade would resolve, because "the
previous campaign found it leaves component packages at their stable versions." On this
train, with `--prerelease=allow`, it does not. Dry run against the 0.9.11.post1 venv:

```
$ uv pip install --python $SB/envs/upc/bin/python --upgrade --prerelease=allow \
      --dry-run 'reflex==0.9.12a1'
Would uninstall 11 packages / Would install 11 packages
 - reflex==0.9.11.post1              + reflex==0.9.12a1
 - reflex-base==0.9.11.post1         + reflex-base==0.9.12a1
 - reflex-components-code==0.9.5     + reflex-components-code==0.9.6a1
 - reflex-components-core==0.9.9     + reflex-components-core==0.9.10a1
 - reflex-components-dataeditor==0.9.2 + reflex-components-dataeditor==0.9.3a1
 - reflex-components-gridjs==0.9.1   + reflex-components-gridjs==0.9.2a1
 - reflex-components-markdown==0.9.3 + reflex-components-markdown==0.9.4a1
 - reflex-components-plotly==0.9.6   + reflex-components-plotly==0.9.7a1
 - reflex-components-radix==0.9.9    + reflex-components-radix==0.9.10a1
 - reflex-components-recharts==0.9.3 + reflex-components-recharts==0.9.4a1
 - reflex-components-sonner==0.9.3   + reflex-components-sonner==0.9.4a1
```

All eleven move together. The load-bearing flag is `--prerelease=allow`; **without** it a
user gets no alpha at all rather than a mixed set, because `reflex==0.9.12a1` itself is a
prerelease. So the mixed-version hazard the protocol warns about did not reproduce here.

Not a defect in the release — an environment/guidance observation. It matters because
the brief's standing advice to always name the component alphas explicitly is, on this
train, belt-and-braces rather than necessary. Worth reconciling with whatever the earlier
campaign actually observed before it is repeated as fact.

---

## Other observations (benign, recorded so they are not re-investigated)

- **New frontend dependency `mergician` at `"v2.0.2"`.** Added to every app's
  `.web/package.json` by this train. It is deliberate and single-sourced —
  `packages/reflex-base/src/reflex_base/constants/installer.py:150` pins it with an
  explanatory comment ("Deep prop merging in $/utils/state's mergeSlotProps. This is the
  single owner of the pin — components (e.g. plotly) import 'mergician' unversioned and
  collapse onto this version"), and `utils/state.js` imports it for the #6850 prop
  merge. The `v` prefix is unusual next to every other bare-semver pin in that dict, but
  npm/bun accept it and installs resolve cleanly. **Not changelogged**, though: a new
  runtime npm dependency in every generated app is arguably worth a line. Low value,
  zero risk; noted only because a reader diffing `package.json` will wonder.
- `SitemapPlugin` warning ("enabled by default, but not explicitly added to the config")
  is printed **five times per run**, once per compile phase, in every app and on both
  versions. Noisy but pre-existing and harmless.
- Prod mode emits far less browser console output than dev (3 messages vs 11), as
  expected — the difference is the React Router HydrateFallback / vite / DevTools lines.

## Cleanup

Every server I started was killed by PID and the ports verified free with
`python3 $SB/bin/ports.py 3540 3541 3542 3543 3544 3545 8540 8542 8543 8544 8545`
(empty output). No redis was started. No browser processes remain. The `envs/prev`
processes still visible on ports 3264/8264 at the end belong to another agent's range,
not mine, and were left alone.

`.web/` and `node_modules/` are excluded from `apps/` in this artifact dir; they remain
in the scratchpad for a follow-up agent and should be deleted when the campaign ends.

---

## VERIFICATION

Independent adversarial verification of the two findings above, run from the written
material alone (NOTES.md + `scripts/drive_quiz.py`), no access to the explorer's session.
Working dir `$SB/apps/verify_up_examples_c/`, reserved ports frontend 4040-4042 /
backend 9040-9042. Everything from PyPI; nothing installed from or run inside
`/home/user/reflex`. All processes killed and ports verified free at the end.

`SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad`

Evidence: `verification/`.

### Venvs used

| venv | contents | how made |
|---|---|---|
| `$SB/envs/shared` | reflex 0.9.12a1 + full alpha train (prebuilt, read-only) | campaign-provided |
| `$SB/envs/prev` | reflex 0.9.11.post1 + stable components (prebuilt, read-only) | campaign-provided |
| `$SB/envs/vupc_prev` | reflex 0.9.11.post1 (mine, for the resolution experiments) | `cd $SB && uv venv $SB/envs/vupc_prev --python 3.11 && uv pip install --python $SB/envs/vupc_prev/bin/python 'reflex==0.9.11.post1'` |
| `$SB/envs/vupc_mixed` | reflex 0.9.12a1 core + STABLE components (the naive-upgrade outcome) | `cd $SB && uv venv $SB/envs/vupc_mixed --python 3.11 && uv pip install --python .../bin/python 'reflex==0.9.11.post1' && uv pip install --python .../bin/python --upgrade 'reflex==0.9.12a1'` |

```
$ uv pip freeze --python $SB/envs/shared/bin/python | grep -i reflex
reflex==0.9.12a1  reflex-base==0.9.12a1  reflex-components-code==0.9.6a1
reflex-components-core==0.9.10a1  reflex-components-dataeditor==0.9.3a1
reflex-components-gridjs==0.9.2a1  reflex-components-lucide==1.0.4
reflex-components-markdown==0.9.4a1  reflex-components-moment==0.9.4
reflex-components-plotly==0.9.7a1  reflex-components-radix==0.9.10a1
reflex-components-react-player==0.9.2  reflex-components-recharts==0.9.4a1
reflex-components-sonner==0.9.4a1  reflex-hosting-cli==0.1.72

$ uv pip freeze --python $SB/envs/prev/bin/python | grep -i reflex
reflex==0.9.11.post1  reflex-base==0.9.11.post1  reflex-components-code==0.9.5
reflex-components-core==0.9.9  reflex-components-dataeditor==0.9.2
reflex-components-gridjs==0.9.1  reflex-components-lucide==1.0.4
reflex-components-markdown==0.9.3  reflex-components-moment==0.9.4
reflex-components-plotly==0.9.6  reflex-components-radix==0.9.9
reflex-components-react-player==0.9.2  reflex-components-recharts==0.9.3
reflex-components-sonner==0.9.3  reflex-hosting-cli==0.1.72

$ uv pip freeze --python $SB/envs/vupc_mixed/bin/python | grep -i reflex
reflex==0.9.12a1  reflex-base==0.9.12a1  reflex-components-code==0.9.5
reflex-components-core==0.9.9  reflex-components-dataeditor==0.9.2
reflex-components-gridjs==0.9.1  reflex-components-lucide==1.0.4
reflex-components-markdown==0.9.3  reflex-components-moment==0.9.4
reflex-components-plotly==0.9.6  reflex-components-radix==0.9.9
reflex-components-react-player==0.9.2  reflex-components-recharts==0.9.3
reflex-components-sonner==0.9.3  reflex-hosting-cli==0.1.72
```

### Commands run

```bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
D=$SB/apps/verify_up_examples_c
mkdir -p $D/_logs $D/_shots $D/_scripts
for v in new prev mixed; do cp -r /home/user/reflex-dev/reflex-examples/quiz $D/quiz_$v; done
cp <cluster>/scripts/drive_quiz.py $D/_scripts/

# three servers, one at a time, each killed before the next
cd $D/quiz_new   && REFLEX_TELEMETRY_ENABLED=false nohup $SB/envs/shared/bin/reflex     run --frontend-port 4040 --backend-port 9040 > $D/_logs/quiz_new.log   2>&1 &
cd $D/quiz_prev  && REFLEX_TELEMETRY_ENABLED=false nohup $SB/envs/prev/bin/reflex       run --frontend-port 4041 --backend-port 9041 > $D/_logs/quiz_prev.log  2>&1 &
cd $D/quiz_mixed && REFLEX_TELEMETRY_ENABLED=false nohup $SB/envs/vupc_mixed/bin/reflex run --frontend-port 4042 --backend-port 9042 > $D/_logs/quiz_mixed.log 2>&1 &

cd $D && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python $D/_scripts/drive_quiz.py http://localhost:4040 vquiz_new   $D/_shots
# ... same for 4041 -> vquiz_prev and 4042 -> vquiz_mixed
```

---

### Issue 1 — React "uncontrolled to controlled" warning on `rx.checkbox` (quiz): **CONFIRMED as written, NOT a regression, not a release defect**

The repro in finding (A) is complete and reproduced on the first attempt.

- **0.9.12a1** (`$SB/envs/shared`, port 4040): exactly 3 `console_warnings`, all the
  claimed text, one per checkbox clicked. All 13 flow assertions pass, `score_text`
  `100%`, `table_rows` 3, `checkboxes_checked_after_back` 0, zero console errors, zero
  page errors, zero failed requests, zero 4xx/5xx.
- **0.9.11.post1** (`$SB/envs/prev`, port 4041): **identical** — same 3 warnings, same
  text, same `results` block field-for-field (only the port differs in the two URL
  fields). The post-click screenshots are **byte-identical** across versions
  (md5 `ae68a21046d1217bb7073d28eef743c3`).

Evidence: `verification/drive_quiz_results.md`, `verification/vquiz_{new,prev,mixed}_02_answered.png`,
`verification/vquiz_{new,prev,mixed}.tail.log`.

Attempts to refute it as *not* pre-existing all failed, and the frontend evidence
explains why the version cannot matter:

- `.web/package.json` is identical on the two versions for everything involved:
  `@radix-ui/themes` 3.3.0, `react`/`react-dom` 19.2.8, `lucide-react` 1.26.0. The train
  did not move the component library that emits the warning.
- The warning string is not React's; it comes from the bundled
  `@radix-ui/react-use-controllable-state/dist/index.mjs:22-31`, a dev-only
  `console.warn` fired from `useControllableState` when `prop` flips from `undefined` to
  defined, with `caller = "Checkbox"`
  (`@radix-ui/react-checkbox/dist/index.mjs:33-38` passes `prop: checkedProp`,
  `caller: CHECKBOX_NAME`). It is third-party dev-mode noise, absent from a prod build.
- **Correction to the explorer's root-cause sentence.** The direction is right ("the
  app's own usage, no `checked` prop") but the mechanism as written — "flips to
  controlled the first time state flows back from the backend" — is not what the
  compiled output shows. Reflex emits *no* `checked` prop at all, on either version:

  ```
  # 0.9.12a1  .web/app_components/quiz/quiz.jsx:100
  jsx(RadixThemesCheckbox,{...mergeSlotProps(rest, ({ onCheckedChange:on_change_…, size:"2" }))},)
  # 0.9.11.post1 .web/app_components/quiz/quiz.jsx:84
  jsx(RadixThemesCheckbox,{onCheckedChange:on_change_…, size:"2"},)
  ```

  No Reflex state var is bound to `checked`, so the flip happens inside
  `@radix-ui/themes`' own Checkbox wrapper on first interaction, not on a backend delta.
  This does not change the verdict; it matters only so a fix agent does not go looking
  for a Reflex state round-trip that isn't there.

Incidental datapoint from the same diff: the generated checkbox is the clearest small
example of #6850 in the compiled output (`mergeSlotProps(rest, …)` replacing direct prop
spreading, 12 occurrences in this one file vs 0 on the previous stable), and it changed
nothing observable here.

**Verdict: confirmed as described, severity low, NOT a regression, NOT actionable for
this release.** Correctly filed as a "do not re-discover this" note. No fix agent action.

---

### Issue 2 — naive `--upgrade --prerelease=allow` pulls every component alpha: **OBSERVATION REPRODUCES, CONCLUSION AND ROOT CAUSE REFUTED**

The dry run in finding (B) reproduces exactly — with `--prerelease=allow`, all eleven
packages move to the alpha set (full output: `verification/upgrade_resolution_dryruns.txt`,
section A). That part is correct.

But the finding's *conclusion* — "the mixed-version hazard the protocol warns about did
not reproduce here", and the root cause "a user who omits `--prerelease=allow` gets no
alpha at all rather than a mixed set" — is **wrong**. The explorer only ran the command
with the flag. Running it without the flag, which is what a real user upgrading to a
named alpha types, produces precisely the mixed set the protocol warns about:

```
$ uv pip install --python $SB/envs/vupc_prev/bin/python --upgrade --dry-run 'reflex==0.9.12a1'
Resolved 40 packages in 198ms
 - reflex==0.9.11.post1        + reflex==0.9.12a1
 - reflex-base==0.9.11.post1   + reflex-base==0.9.12a1
                                 (all ten reflex-components-* stay at their STABLE versions)

$ .../bin/python -m pip install --upgrade --dry-run 'reflex==0.9.12a1'
Would install reflex-0.9.12a1 reflex-base-0.9.12a1
```

Both resolvers agree, and for the same reason: an explicit `==<prerelease>` specifier is
enough to allow that one package's prerelease (PEP 440 / pip and uv both do this), so no
`--prerelease` flag is needed to get the alpha core; but the component packages are only
reachable through reflex's **floor** pins, which the stable versions already satisfy:

```
Requires-Dist: reflex-base==0.9.12a1            <- exact, so reflex-base follows core
Requires-Dist: reflex-components-core>=0.9.6    <- satisfied by stable 0.9.9
Requires-Dist: reflex-components-radix>=0.9.9   <- satisfied by stable 0.9.9
... (all other reflex-components-* are >=0.9.0)
```

(`verification/reflex_component_pins.txt`; the pin *shape* is byte-identical in
0.9.11.post1, so this is pre-existing and unchanged by this train.)

I then built that mixed venv for real (`$SB/envs/vupc_mixed`) and ran `quiz` on it
(port 4042). It **works** — the driver's `results` block is identical to both other runs,
and the compiled output carries the new core's changes even with stable components
(`mergeSlotProps` 12x, `mergician` in `.web/package.json`, the #7068 `rx_router_*` state
keys), because those live in `reflex`/`reflex-base`, not in the component packages. So
the mixed set is silently *plausible*, which is exactly what makes it a QA hazard: an
agent or user who upgrades naively gets a half-alpha install that starts and runs, and
would attribute any component-side bug to the wrong version pair.

Corrected guidance, replacing the finding's "belt-and-braces rather than necessary":

- The brief's instruction to pass `--prerelease=allow` **and** name the component alphas
  is **necessary**, not redundant. `--prerelease=allow` is what makes the component
  alphas selectable at all; naming them is what makes the result deterministic.
- The earlier campaign's mixed-version observation is **correct and still reproduces**;
  it should not be reconciled away.
- This is still **not a defect in the release**. Floor-only component pins are
  deliberate and unchanged; on a final (non-prerelease) release `--upgrade` moves the
  components too, so the hazard is specific to installing a named prerelease.

**Verdict: not a release defect (as filed), but the finding's stated conclusion and root
cause are refuted and must not be carried into FINDINGS.md as written.** No fix agent
action on the framework; the campaign brief's advice stands as originally written.

---

### Cleanup

Servers 4040/9040, 4041/9041, 4042/9042 killed by pid;
`python3 $SB/bin/ports.py 4040 4041 4042 9040 9041 9042` returns empty. No redis, no
browser processes left. `$SB/envs/vupc_prev` and `$SB/envs/vupc_mixed` and
`$SB/apps/verify_up_examples_c/` remain in the scratchpad for re-checking and should be
deleted when the campaign ends.
