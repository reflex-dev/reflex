# Actual Reflex customization: pointer and keyboard session proof

This experimental app binds drag-add, reorder, resize, keyboard commands, settings,
and Save/Cancel/Reset to the real shared Python `Draft` engine through normal
Reflex events. It uses actual XY charts, the Community Grid adapter, and shared
input/button renderers with deterministic synthetic data. No browser preference
engine mirrors or replaces Python validation.

## Run in this saved cloud environment

From `experiments/customization-session`:

```bash
./run.sh compile --no-rich
./run.sh run --frontend-port 4202 --backend-port 8202 --backend-host 127.0.0.1
```

Open `http://127.0.0.1:4202` in the same cloud environment. These loopback addresses
are not remotely reachable preview links. The frozen keyboard-only baseline and
separate pointer study remain untouched on their existing branches.

`run.sh` reuses `/workspace/reflex/.venv`, `/workspace/xy-integration/python`, and
this worktree's shared component source. Override `SESSION_VENV`,
`SESSION_XY_ROOT`, or `REFLEX_DIR` for another authorized checkout. No new accounts,
credentials, dependency installation, or deployment are needed here.

Write logs and screenshots outside the app tree while it runs: Reflex watches
app files and evidence writes there can trigger hot reloads.

## Gesture and validation contract

- Enter Customize, then use a dedicated dot grip to drag a canvas widget or a
  catalog preview. Use the explicit Resize handle for width and height. Keyboard
  Move before/after, half/full width, Add and allowlisted settings remain usable.
  The focused Resize handle accepts Arrow Up/Down for one height unit and
  Left/Right for half/full width through the same versioned Python command.
  Bounds announce a no-op without staging, and accepted keyboard sizes retain
  focus on the handle.
- The actual source DOM node becomes the floating inert ghost, with a placeholder
  preserving its source position. Its real chart/grid renderer stays mounted;
  there is no chart image substitute or separately invented ghost renderer.
- Pointer movement changes only gesture feedback. A valid release sends one
  `on_command` event to `State.pointer_command`, which projects the operation's
  exact fields into `Session.pointer`. The model checks the revision, source,
  destination, types, registry and bounds before staging one complete candidate
  through the actual Python `Draft.stage`.
- The ghost remains pending until a server reply. Accepted layout changes arrive
  through Reflex state. Rejection restores the source and reports the error;
  stale or malformed commands leave preferences unchanged.
- Escape, pointer cancellation, invalid drop, and unchanged gestures send no
  staging command. Normal chart pan/wheel and grid sorting/filtering/column resize
  do not start layout gestures because only dedicated grips are intercepted.
- Width snaps to six or twelve logical columns. Height uses bounded integer
  units: trend/accounts 3–8, search 2–5. Content height maps to `72 * units + 22`
  pixels; actual chart/grid containers respond to their new dimensions.
- This remains an ordered vertical adapter. Reorder preserves logical gaps and
  resize shifts following logical Y positions by the explicit height delta.
  The DOM renders order, width and height with fixed vertical spacing. It does
  not render arbitrary authored X/Y placement or provide a general grid solver.

The catalog is nonmodal, docked and collapsible, with no backdrop. Narrow layouts
reflow it below the canvas and focus its heading when opened. Top/left navigation
stay recognizable. The visual shell remains tentative; this proof does not
approve A or B or change the shared production theme.

## Actual renderer continuity

Existing canvas instances retain their React keys and DOM nodes during gestures
and acknowledged reorders. Grid sort survives movement. For catalog drag-add,
Community presentation arrives through the wrapper's existing `on_state_changed`
event, is kept in this session's backend map, and initializes the new grid.
The catalog chart's public `xy.state()` viewport is applied to the new actual XY
renderer after the validated addition. Source and destination therefore retain
the demonstrated grid sort and chart zoom without a shared-renderer fork.

The line chart explicitly enables actual pan/navigation/zoom. Line brushing and
kernel-backed static selection are not enabled or claimed. These are presentation
interactions; no business-write callback exists in this synthetic app. Actual
applications must separately guard business-write handlers while arranging.

## Session-only storage and sources

`rx.Config` explicitly selects in-memory state management. Each client has its own
Python `Session` and backend-only `Draft`. Save synchronously confirms only this
session's view under the normal Reflex event lock. There is no asynchronous
storage await in which edit/Cancel can interleave. Failed-Save test injection
retains the draft; it is not exposed as a customer-facing control.

Server restart clears saved layouts. This is not authenticated, durable,
cross-device, or account-backed storage. A future asynchronous adapter must block
edit/Reset/Cancel while saving or use versioned persistence/reconciliation;
`confirm_save` cannot undo a completed external write. No customer records,
credentials, new permissions, production merges or deployments are involved.

Shared code starts from `reflex-dev/reflex` integration `829949fd`. The imported
`reflex_components_internal.experimental.customization.Draft` and Community Grid
remain the actual shared implementations. Community/react dependencies remain
34.3.1, with no Enterprise package or license bypass. XY is imported from the
saved `/workspace/xy-integration` checkout; its `reflex_xy.chart` builds real
observed at `2b5ac52bb0a83b2b24bc7d2b7b629a9d6e9e1084` in the final check;
payload assets and uses its matching `XYChart.jsx`/`xy/static/index.js` renderer.
The 14-point Actual/Plan lines preserve raw values without smoothing. Existing
palette provenance remains Flexgen `ab8bec5125073ca0a209b9781be3692b271a4747`,
`assets/css/palette.css` and `custom-colors.css`, with Inter/system fonts.

## Verification

```bash
UV_CACHE_DIR=/tmp/customization-uv-cache \
UV_PROJECT_ENVIRONMENT=/workspace/reflex/.venv \
PYTHONPATH=/workspace/xy-integration/python:../../packages/reflex-components-internal/src:. \
uv run --no-sync pytest test_session.py test_pointer_model.py test_pointer_events.py -q

BASE_URL=http://127.0.0.1:4202 \
EVIDENCE_DIR=/workspace/customization-pointer-evidence \
NODE_PATH=/workspace/xy-integration/node_modules node pointer-audit.cjs

BASE_URL=http://127.0.0.1:4202 \
EVIDENCE_DIR=/workspace/customization-pointer-evidence \
NODE_PATH=/workspace/xy-integration/node_modules node keyboard-audit.cjs
```

The model/event tests include real `State` calls and a spy on actual `Draft.stage`:
valid drops stage once; stale, malformed or invalid drops stage zero times.
The browser audit covers source/ghost identity, no stage before release, sort and
zoom continuity into actual destinations, snapped resize, repeated drag/Cancel,
canceled-drag/Save, and laptop layout. Fresh independent review additionally
captures actual command frames, pointercancel/invalid-drop isolation, real chart
pan/wheel and grid content gestures, and both navigation layouts at 1024 px.

Current pointer evidence is under `evidence/pointer/`; existing `evidence/` files
record the frozen keyboard baseline and must not be mistaken for pointer results.
This is focused prototype coverage, not a complete accessibility, touch-device,
large-layout performance, or chart fidelity certification. Removal/undo/redo,
arbitrary layout solving, migrations and concurrent-tab persistence remain gaps.
