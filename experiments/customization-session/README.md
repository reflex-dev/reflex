# Actual Reflex customization session proof

This bounded experimental app binds the shared Python `Draft` engine to real
Reflex event handlers. It uses actual Community Grid, actual XY charts, and the
shared input/button renderers. It is a keyboard-first integration proof; the
separate overnight UI study remains the pointer-drag reference. No pointer drag,
resize grips, drop ghost, or drag parity is claimed here.

The appearance is reversible and does not settle A versus B. Customize exposes
Move before/after, explicit half/full width, allowlisted widget settings, top/left
navigation, Add widgets, Reset, Cancel, and Save my session layout. The catalog is
nonmodal, docked and collapsible. At narrow widths it reflows below the canvas.
Opening or closing it never stages layout geometry. The toggle exposes its
expanded state and focuses the catalog heading on open, so narrow layouts
scroll to the reflowed catalog; closing restores focus to Add widgets. Widget instance keys preserve
the actual grid's sort state while reordering.

## Sources and persistence boundary

- Shared source: `reflex-dev/reflex`, integration base `3fcb0dbb`. The real
  `reflex_components_internal.experimental.customization.Draft`, Registry and
  preferences are imported, not mirrored in browser JavaScript.
- Community adapter: the integration branch's shared `CommunityGrid` renderer,
  using `ag-grid-community` and `ag-grid-react` 34.3.1. No Enterprise dependency.
- XY source: `/workspace/xy-integration`, observed revision
  `1a8f0ff6f3d4062b0871a0c56257d9d85f4dda18`. `reflex_xy.chart` compiles synthetic
  Python columns into payload assets and mounts its actual `XYChart.jsx` and
  matching `xy/static/index.js`. This proof uses the static-data adapter, not a
  screenshot, iframe, unrelated chart package, or simulated renderer. Chart
  navigation and hover remain client-side. The 14-point Actual/Plan lines retain
  raw values; no statistical smoothing is applied.
- Palette values are taken from `flexgen/assets/css/palette.css` and aliases from
  `custom-colors.css`, at `reflex-dev/flexgen`
  `ab8bec5125073ca0a209b9781be3692b271a4747`. The shared font stack uses Inter with
  system fallback. The demo adds scoped layout/edit boundaries; it does not edit
  the production theme. Actual shared components remain the renderers.

`rx.Config` explicitly selects the in-memory state manager. Each client session
owns its `Session` and backend-only Python `Draft`. Save writes only that session's
memory and synchronously calls `Draft.save()` and `Draft.confirm_save()` under
the normal Reflex event lock. No authentication, account preferences database,
file storage, customer data, credentials, or business-write handler exists. Server
restart clears these saved views. This is not durable or cross-device storage.

No asynchronous persistence is performed, so no Save awaits/yields while edits
can interleave. A future asynchronous adapter must disable edits/Reset/Cancel
while saving, or add versioned persistence/reconciliation. `confirm_save` alone
cannot undo an external write. The model's optional persistence callback exists
only for tests; the customer-facing app cannot inject save failures. Tests prove
a failed callback leaves the draft available for retry.

## Compile and run in this saved cloud environment

From `experiments/customization-session`:

```bash
./run.sh compile --no-rich
./run.sh run --frontend-port 4201 --backend-port 8201 --backend-host 127.0.0.1
```

`run.sh` reuses `/workspace/reflex/.venv`, `/workspace/xy-integration/python`, and
this worktree's shared component source. Override `SESSION_VENV`,
`SESSION_XY_ROOT`, or `REFLEX_DIR` for another authorized checkout. No dependency
installation or credentials are required in this saved environment. The app uses
its own 4201/8201 ports and does not deploy anything.

Write runtime logs and browser evidence **outside the app tree** while it runs;
Reflex watches app files and writing evidence there can trigger hot reloads.

```bash
./run.sh run --frontend-port 4201 --backend-port 8201 --backend-host 127.0.0.1 \
  > /workspace/customization-session-evidence/runtime.log 2>&1
```

## Verification

The seven focused tests call real `State` events and spy on the actual `Draft.stage`
class method. They also check invalid layout/option rejection without mutation,
failed-Save retry, Reset followed by Cancel, session isolation, explicit stable
order, size/options, and dock/search operations leaving geometry untouched.

```bash
UV_CACHE_DIR=/tmp/customization-uv-cache \
UV_PROJECT_ENVIRONMENT=/workspace/reflex/.venv \
PYTHONPATH=/workspace/xy-integration/python:../../packages/reflex-components-internal/src:. \
uv run --no-sync pytest test_session.py -q

EVIDENCE_DIR=/workspace/customization-session-evidence \
NODE_PATH=/workspace/xy-integration/node_modules node browser-audit.cjs
```

The browser audit uses Chromium at `/usr/bin/chromium`; `BASE_URL` can override
4201. It checks actual server transitions and rendered widget behavior, including
keyboard Move, retained grid DOM/sort, real search filtering/focus, registered
catalog previews, session Save, Reset/Cancel, added-instance cancellation,
left-navigation laptop width, and no geometry mutation during responsive reflow.
Committed `evidence/` contains captured results and comparable normal/edit/laptop
screenshots. This is focused browser coverage, not a complete accessibility or
performance certification. No chart fidelity matrix or broad benchmark is claimed
for this app.

## Deliberate gaps

- Pointer drag/resize and ghost continuity remain in the separate UI study; this
  proof has explicit keyboard commands and no fake drag grips.
- Logical placements form an ordered vertical MVP. Half-width cards keep a
  readable minimum width; no automatic dense packing or general layout solver.
  Logical x/y/height are validated by the engine but the demo DOM uses order,
  explicit width and fixed vertical spacing. It does not render arbitrary
  coordinate gaps or authored logical heights.
- Catalog previews use actual renderers but independent instances; preview grid
  column state is not a copy of each canvas instance. The current shared query is
  deliberately visible in both. Catalog previews omit pagination to keep the small actual grid readable.
  Full renderer context and read-only preview policy remain integration work.
- No removal/undo/redo, authenticated persistence, cross-tab conflict resolution,
  migrations, or production permissions integration. No business-write controls
  exist to guard in this synthetic fixture; real apps must separately disable
  and guard those handlers while arranging.
- This app demonstrates tentative A-style in-app boundaries only. The existing
  UI study retains reversible A/B comparisons. No visual direction is approved
  by this proof.
