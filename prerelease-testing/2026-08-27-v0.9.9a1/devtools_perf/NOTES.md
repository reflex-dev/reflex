# Cluster: devtools_perf — React DevTools naming (#6945) + owner-stack perf (#6905)

reflex 0.9.9a1 + reflex-components-plotly 0.9.5a1, installed from PyPI into an
isolated venv (plus `plotly==6.9.0`). Verdict: **both features work exactly as
advertised in dev-default, dev-with-owner-stacks, and prod. 31/31 checks pass
in each dev mode, 28/28 in prod (3 checks are dev-only). No framework bugs
found.** Perf numbers below confirm the #6905 claim at the same magnitude.

## App

`devtools_app/` — blank-template app with:

- States: `AppState(rx.State)` → substates `ChartState`, `BlogState`
  (nested, so `StateContext(...)` names must show the full dotted path).
- Custom component classes: `StatCard(rx.el.Div)`, `PulseBadge(rx.el.Span)`.
- `@rx.memo` functions: `counter_panel(label, value)`, `nav_bar()`
  (annotated `rx.Var[...]` — bare `str`/`int` annotations emit the 0.9.3
  DeprecationWarning, which fired correctly when I first got it wrong).
- `rx.plotly(data=ChartState.figure)` — NoSSRComponent → `ClientSide(Plot)`.
- `rx.upload` — mounts the `UploadFilesContext` provider.
- Pages: `/`, `/charts`, `/heavy` (12 sections x 120 statically-compiled cells
  ≈ 1600 DOM nodes — the perf-navigation target), `/blog/[slug]` (dynamic
  route, `on_load=BlogState.record_view`).
- `assets/owner_probe.js` + `OwnerProbe(rx.Component)` with
  `library = "$/public/owner_probe"`: a local React component that calls
  `React.captureOwnerStack()` **during render** (the only time owner stacks are
  readable) and accumulates results in `window.__ownerStackCaptures`; also
  exposes the app's React instance as `window.__probeReact` so the driver can
  inspect `__CLIENT_INTERNALS...recentlyCreatedOwnerStacks`.

## How to rerun

```
SB=<scratchpad>
uv venv $SB/envs/devtools --python 3.11
uv pip install --python $SB/envs/devtools/bin/python --prerelease=allow 'reflex==0.9.9a1'
uv pip install --python $SB/envs/devtools/bin/python 'plotly<7'
cd devtools_app

# Run A: dev, default (owner stacks disabled)
REFLEX_TELEMETRY_ENABLED=false reflex run --frontend-port 3500 --backend-port 8500 --loglevel debug
BASE_URL=http://localhost:3500 MODE=dev-default OUT=out_dev_default python ../drive_devtools.py

# Run B: dev with owner stacks restored (restart server)
REFLEX_TELEMETRY_ENABLED=false REFLEX_REACT_OWNER_STACKS=1 reflex run --frontend-port 3500 --backend-port 8500 --loglevel debug
BASE_URL=http://localhost:3500 MODE=dev-ownerstacks OUT=out_dev_ownerstacks python ../drive_devtools.py

# Run C: prod (0.9.9: frontend and backend share one port)
REFLEX_TELEMETRY_ENABLED=false reflex run --env prod --frontend-port 8501 --backend-port 8501 --loglevel debug
BASE_URL=http://localhost:8501 MODE=prod OUT=out_prod python ../drive_devtools.py
```

Driver: playwright venv with Chromium at `/opt/pw-browsers/chromium`. Do not
override the sandbox's default `NO_PROXY` when running `reflex run` — it
already exempts localhost and registry.npmjs.org; clobbering it breaks bun
installs through the agent proxy.

## Results — #6945 displayName (runtime fiber walk + static grep)

Static (`grep -rn displayName .web/app .web/app_components .web/utils`):
pages `Component(index|charts|heavy|blog/[slug]|404)`; contexts
`ColorModeContext`, `UploadFilesContext`, `DispatchContext`,
`EventLoopContext`, `ThemeContext` (react-theme.js), and one
`StateContext(<full dotted python state path>)` per state incl. internal
states; memo components `CounterPanel`, `NavBar`; auto-memo wrappers
`MemoComponent_CounterPanel_<hash>`, `Button`, `Bare` (x5), `StyledUpload`,
`Plotly`; `ClientSide(component, name)` helper produces `ClientSide(Plot)`.

Runtime (React fiber walk from `#page-root`, `fiber_*.json` per page, all
three modes — displayNames survive prod minification):

- `Component(index)`, `Component(charts)`, `Component(heavy)`, and
  **`Component(blog/[slug])`** all observed on their pages. PASS.
- `CounterPanel`, `NavBar` (from `@rx.memo` function names), and
  `MemoComponent_CounterPanel_<hash>` wrappers named. PASS.
- The memoized plotly call site is named `Plotly` — taken from the **Python
  class name** of the wrapper component. PASS.
- `ClientSide(Plot)` present once react-plotly.js finishes its dynamic
  import. PASS.
- Context providers in the mounted tree carry displayNames:
  `StateContext(reflex___state____state)`,
  `StateContext(reflex___state____state.devtools_app___devtools_app____app_state)`,
  and the **nested** `...app_state.devtools_app___devtools_app____chart_state`
  / `...blog_state` variants, plus `ColorModeContext`, `EventLoopContext`,
  `DispatchContext`, `ThemeContext`. PASS.
- `UploadFilesContext.displayName` verified via direct
  `import('/utils/context.js')` in-page (dev): every context and all 8
  StateContexts named. PASS.
- Only 1 of 21 context objects in the tree is unnamed — third-party
  (react-error-boundary), consistent with the memo cluster's finding.

## Results — #6905 owner stacks

Behavioral, via `React.captureOwnerStack()` called during render (OwnerProbe):

| mode                                  | captureOwnerStack() during render |
|---------------------------------------|-----------------------------------|
| dev default                           | `""` — no frames, every capture (28/28) |
| dev + `REFLEX_REACT_OWNER_STACKS=1`   | real frames, e.g. `at Component (http://localhost:3500/app/routes/_index.jsx?import:21:6)` |
| prod                                  | export absent (`<no captureOwnerStack API>`) — normal for React prod builds |

Mechanism, via `React.__CLIENT_INTERNALS...recentlyCreatedOwnerStacks`:

- dev default: value `1e9`, setter is a no-op (`writable: false`) — the pin
  from `.web/utils/context.js` is active. PASS.
- dev + flag: value small and writable (e.g. 545); the pin snippet is absent
  from the recompiled `utils/context.js` (0 grep hits). PASS — the env var
  recompiles the context correctly on restart.
- prod: pin snippet absent from compiled context (never emitted in prod). PASS.

## Perf sanity (recorded, not asserted) — CDP Performance metrics

Navigation click `/` → `/heavy` (~1600 statically compiled DOM nodes), 3 navs
per mode (first nav includes route-module load; navs 1–2 are steady state).
Deltas of `TaskDuration`/`ScriptDuration` around the click, ms:

| mode            | nav0 task/script | nav1 task/script | nav2 task/script |
|-----------------|------------------|------------------|------------------|
| dev default     | 143 / 72         | 102 / 46         | 99 / 42          |
| dev ownerstacks | 412 / 347        | 352 / 295        | 324 / 277        |
| prod            | 97 / 39          | 68 / 18          | 69 / 16          |

Steady state: **dev-default ≈ 100ms task (~1.5x prod ≈ 68ms); with owner
stacks re-enabled ≈ 338ms (~5x prod)** → the suppression saves ~3.4x
main-thread CPU on this page. Matches the #6905 changelog claim
(~350ms → ~83ms, 5.6x → ~1.3x) at the same order of magnitude on this
smaller app / 4-CPU container. Raw numbers: `out_*/perf_heavy_nav.json`.

## Other checks (all modes)

- plotly 0.9.5a1 chart renders (6 bars, correct title), `shuffle` event
  redraws with new totals, hover tooltip appears. Clean console.
- Dynamic route: `/blog/hello-world` on_load records a view; client-side nav
  to `/blog/second-post` re-renders with the new slug AND re-fires on_load.
- Custom classes (`StatCard`, `PulseBadge`) render and update on events.
- Hygiene: no unexpected console errors/warnings, no failed/4xx/5xx requests,
  no server-log tracebacks, in any mode.

## Benign-but-surprising observations

1. **`rx.plotly(id="the-plot")` never reaches the DOM** — react-plotly.js only
   forwards `divId` to its container div, so the `id` prop is silently
   dropped and `#the-plot` selectors find nothing (select `.js-plotly-plot`
   instead). Almost certainly longstanding wrapper behavior, not a 0.9.9
   regression, but it silently violates the usual "id lands on the root
   element" expectation.
2. Local `$/public/...` custom components trigger a debug-level server hint
   "Instead of /public/owner_probe.js, use /owner_probe.js" — the `$/public/`
   import nevertheless resolves fine (vite alias `$` → `.web/`). Cosmetic.
3. Prod build rolldown warnings (`Invalid input options ... "jsx"`,
   `advancedChunks deprecated`) — already reported by the memo cluster, still
   present, see `prod_server.log`.
4. The `@rx.memo` bare-annotation DeprecationWarning (0.9.3) fires correctly
   with the exact parameter names and file:line — nice DX, works as intended.

## Artifacts

- `devtools_app/` — app source (no `.web/`).
- `drive_devtools.py` — the 31-check Playwright driver (writes results.json,
  fiber_*.json, owner_captures_index.json, context_module.json,
  perf_heavy_nav.json, console.log, failed_requests.log, PNGs).
- `probe_charts.py` — small standalone probe used while debugging selectors.
- `out_dev_default/`, `out_dev_ownerstacks/`, `out_prod/` — full run outputs.
- `dev_default.log`, `dev_ownerstacks.log`, `prod_server.log` — server logs.

## VERIFICATION (adversarial verifier, 2026-08-28)

Claim verified: **`rx.plotly(id=...)` never reaches the DOM — CONFIRMED as a
genuine (low-severity, longstanding) wrapper defect; NOT a 0.9.9a1 regression.**

Independent repro (fresh venv `reflex==0.9.9a1` + `plotly==6.9.0` from PyPI,
minimal blank-template app in `verification/plotid_app/`, dev mode, ports
4000/9000, driven by `verification/probe_plotid.py`):

- `rx.box(id="control-box")` → `#control-box` exists (1). Baseline id handling OK,
  so the repro is not API misuse.
- `rx.plotly(data=State.figure, id="the-plot")` → chart renders, `#the-plot`
  count 0.
- `rx.plotly(data=STATIC_FIGURE, id="static-plot")` → chart renders,
  `#static-plot` count 0 (rules out state-var interplay).
- Clean console (no errors/warnings), no failed requests. Screenshot:
  `verification/probe_999.png`.

Mechanism confirmed at both ends:

- Compiled JSX (`.web/app_components/.../plotid_app.jsx`) DOES emit the prop:
  `jsx(Plot,{id:"the-plot",ref:ref_the_plot,useResizeHandler:true,...})` —
  Reflex passes `id` through as a React prop (it is not dropped at compile time).
- react-plotly.js@4.0.0 (`dist/chunk-AIWLJUCK.mjs`) destructures
  `{ ..., divId, ...eventProps }` and renders
  `React.createElement("div", { id: divId, style, ref: setRef, className })`.
  The `id` prop falls into `...eventProps` and is silently discarded.

Refutation attempts:

- **0.9.8 baseline** (separate venv `reflex==0.9.8` from PyPI, identical app in
  `verification/plotid_app_098/`, ports 4001/9001): identical result —
  `#control-box` 1, `#the-plot` 0, `#static-plot` 0, charts render
  (`verification/probe_098.png`). 0.9.8 pins the same `react-plotly.js@4.0.0`.
  So this is pre-existing behavior, not a 0.9.9 regression — matching the
  claimant's own characterization.
- **Workaround check**: `rx.plotly(data=..., custom_attrs={"divId": "workaround-plot"})`
  → `#workaround-plot` exists with class `js-plotly-plot`
  (`verification/probe_999_workaround.png`). Confirms the drop happens inside
  react-plotly.js and that a `divId` mapping in the wrapper (`Plotly._render`)
  would fix it.

Verdict: reproduced exactly as claimed; severity "low" is right. `id` is a
universal documented Component prop in Reflex, silently violated only by this
wrapper (and note Reflex still generates `ref_the_plot` keyed to that id, so
id-based helpers like `rx.scroll_to("the-plot")` would also not find the
element). Suggested fix for a fix-agent: map `id` → `divId` in
`packages/reflex-components-plotly/src/reflex_components_plotly/plotly.py`
(`_render`), or expose a `div_id` prop + docs note.

Rerun:
```
SB=<scratchpad>
uv venv $SB/envs/verify_plotly --python 3.11
uv pip install --python $SB/envs/verify_plotly/bin/python --prerelease=allow 'reflex==0.9.9a1' 'plotly<7'
cd verification/plotid_app
REFLEX_TELEMETRY_ENABLED=false $SB/envs/verify_plotly/bin/reflex run --frontend-port 4000 --backend-port 9000
BASE_URL=http://localhost:4000 $SB/envs/driver/bin/python ../probe_plotid.py
```
