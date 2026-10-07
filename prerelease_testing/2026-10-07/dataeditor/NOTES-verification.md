# Independent dataeditor verification

Independent runtime verification on macOS, using the browser explorer's written
candidate and an independently authored minimal app, confirms the foreach defect
on both 0.10.0a2 and 0.9.12. It is **pre-existing, not a 0.10 regression**.

## Minimal foreach fixture

`verification/foreach_app` contains an independent app with three routes:

- `/`: a normal state-bound data editor, the positive control.
- `/foreach`: the same editor created directly inside `rx.foreach`.
- `/memo`: foreach editors through a memo component boundary, a scoping control.

The app uses plain string cells and no image, form, client-state, plugin, or other
component dependencies. All app packages include `__init__.py`.

Reserved ports are 3435–3437 and 8435–8437. Environments are read-only published
PyPI installs at `/private/tmp/reflex-prerelease-macos-pass2/envs/{alpha2,alpha,stable,driver}`.

For each version, copy `verification/foreach_app` into a separate neutral
`$SB/apps/dataeditor-verification/<version>` directory. With `SB` set to the root
above, `QA_ENV=alpha2`, and the app copy as the working directory:

```sh
export SB=/private/tmp/reflex-prerelease-macos-pass2
export UV_CACHE_DIR="$SB/uv-cache"
export QA_ENV=alpha2
REFLEX_TELEMETRY_ENABLED=false uv --no-config run --no-project --python "$SB/envs/$QA_ENV/bin/python" reflex run --frontend-port 3435 --backend-port 8435 --loglevel debug
```

Run the driver from a neutral directory, with an absolute path to the saved script:

```sh
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 uv --no-config run --no-project --python "$SB/envs/driver/bin/python" /absolute/path/to/verification/scripts/drive_foreach.py http://localhost:3435 /absolute/path/to/output
```

The driver records the actual browser version and user agent, browser errors with
stacks, console warnings/errors, failed requests, HTTP errors, limited websocket
frames, canvas counts, and screenshots. Its exit status indicates whether all
three routes passed. Run one server at a time and stop its process group afterward.

## VERIFICATION: foreach dataeditor scope

| Published Reflex | Published dataeditor | Direct state data | Direct foreach | Memo foreach |
| --- | --- | --- | --- | --- |
| 0.10.0a2 | 0.10.0a1 | 1 canvas, pass | 0 canvases, ReferenceError | 2 canvases, pass |
| 0.9.12 | 0.9.3.post1 | 1 canvas, pass | 0 canvases, ReferenceError | 2 canvases, pass |

Both failing pages report `ReferenceError: rows_rx_state_ is not defined`, caught
by the React error boundary and recorded in browser console errors. Therefore a
driver checking only uncaught `pageerror` events would miss the crash.

`verification/results/foreach/{alpha2,stable}/results.json` captures each route,
with screenshots alongside. `*-compiled-excerpt.txt` shows the exact scoping
problem: `getData_osizayzf` refers to `rows_rx_state_` before the `.map()` callback
that declares that argument. The memo control keeps its generated callback within
the memo argument's scope and renders correctly on both versions.

Published package root-cause location: `reflex_components_dataeditor/dataeditor.py`,
`DataEditor.add_hooks()`, lines 472–499 in the alpha2 environment. The method
embeds the textual data variable into a hook without relocating its foreach scope.
The browser evidence establishes the generated-code defect; this is not a claim
that this method alone should implement a framework fix.

Chromium 153.0.8010.12 ran in fresh contexts for every route. No unexpected failed
requests or HTTP errors occurred. Vite/React development messages and the default
SitemapPlugin warning are unrelated fixture noise. The alpha2 and stable server
process groups were terminated after their respective runs.

## Additional minimal interaction fixture

`verification/delete_app` contains `/` (default deletion), `/bound` (the same
grid with a recording `on_delete` handler), `/form-only` (Radix checkbox, switch,
and radio inside a form), and `/form-grid` (the same form plus a static dataeditor).
The driver verifies the clicked grid cell before pressing Delete or Backspace.
The form driver records actual click-event constructors and confirms each control
still changes its checked state.

Copy this fixture to separate neutral directories and launch using the same
command and reserved ports as above. Substitute `drive_delete.py` or
`drive_form_grid.py` for the foreach driver.

## VERIFICATION: deletion callback

Both versions pass the unbound-handler control with both Delete and Backspace:
the selected first text cell becomes empty and exactly one `on_cell_edited`
event runs. Both versions fail identically with `on_delete` bound: the backend
receives the correct `[0, 0]` selection, but zero edit events run, the cell remains
`alpha`, and Glide's `shiftSelection` throws
`Cannot read properties of undefined (reading 'length')`.

This is a confirmed pre-existing defect, not a regression versus 0.9.12. The
recording handler does not return or manipulate any selection. Generated code
passes Reflex's event-enqueueing callback directly as `onDelete`, while Glide
expects the callback's synchronous return to be a boolean or selection object.
The precise return-type mismatch remains a root-cause hypothesis; the bound vs
unbound browser comparison establishes its trigger.

Evidence is in `verification/results/delete/{alpha2,stable}/`, including full
JavaScript stacks, before/after values, delivered selection, edit counts, and
screenshots. `glide-delete-excerpt.txt` and `generated-handler-excerpt.txt` record
the relevant published frontend code. The first driver attempt incorrectly used
`canvas.click()` even though Glide intentionally overlays a pointer-event
scroller. That attempt was discarded; final driver uses a browser mouse click at
canvas-relative coordinates and waits for backend confirmation of cell `[0, 0]`.

## VERIFICATION: synthetic form clicks and dataeditor

Both 0.10.0a2 and 0.9.12 pass `/form-only` with zero page errors. Adding one static
dataeditor inside the form produces exactly three errors, one on each checkbox,
switch, and radio change: `Cannot read properties of undefined (reading '0')`.
All three controls still become checked, so this is an uncaught-error integration
defect rather than an observed loss of form state.

The driver records each ordinary pointer click followed by a bubbling plain
`Event` dispatched from a hidden `INPUT`. Glide listens for clicks on `window`
and treats every event that is not a `MouseEvent` as a touch event, dereferencing
`ev.changedTouches[0]`. The plain events have no `changedTouches`. This independently
confirms the parent's diagnosis and establishes that it predates 0.10.

Evidence is in `verification/results/form-grid/{alpha2,stable}/`, including per-control
stacks, event-constructor traces, and screenshots. `glide-click-excerpt.txt` and
`radix-click-excerpt.txt` preserve the relevant published frontend code. The same
minimal app/server was used for deletion and form-grid verification, so their
server logs are under `verification/results/delete/`.

## Exact local rerun setup

The installed environment bootstrap is documented in the campaign's
`scripts/bootstrap_envs.sh`. To reproduce with the prepared environments, run:

```sh
export SB=/private/tmp/reflex-prerelease-macos-pass2
export UV_CACHE_DIR="$SB/uv-cache"
export REPO=/Users/masen/.codex/worktrees/3564/reflex
export QA_ENV=alpha2
export QA_FIXTURE=delete
export QA_APP="$SB/apps/dataeditor-verification/rerun-$QA_FIXTURE-$QA_ENV"
export QA_SOURCE="$REPO/prerelease_testing/2026-10-07/dataeditor/verification"
mkdir -p "$QA_APP"
cp -R "$QA_SOURCE/${QA_FIXTURE}_app/." "$QA_APP/"
cd "$QA_APP"
REFLEX_TELEMETRY_ENABLED=false uv --no-config run --no-project --python "$SB/envs/$QA_ENV/bin/python" reflex run --frontend-port 3435 --backend-port 8435 --loglevel debug
```

In a second terminal with `SB`, `UV_CACHE_DIR`, and `QA_SOURCE` set identically:

```sh
cd "$SB"
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$QA_SOURCE/scripts/drive_delete.py" http://localhost:3435 "$SB/apps/dataeditor-verification/rerun-delete-results"
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$QA_SOURCE/scripts/drive_form_grid.py" http://localhost:3435 "$SB/apps/dataeditor-verification/rerun-form-grid-results"
```

Use `QA_ENV=stable` in a separate app copy for the baseline. For foreach, set
`QA_FIXTURE=foreach` and use `drive_foreach.py`. Run one server at a time. The
expected driver exit code is 1 because the candidate cases intentionally expose
known defects; inspect the positive-control results before accepting a finding.

No framework changes were made. Independent verification covered Chromium/dev
on alpha2 and stable; alpha1, production, and WebKit are covered separately by
the primary cluster explorers where noted in their reports.

## Namespace-package smoke anomaly: documentary triage

The reported smoke failure omitted the app package's `__init__.py`; adding the
file restored state events. The documented normal structure in
`docs/getting_started/project-structure.md` explicitly includes
`hello/__init__.py`. The advanced structure documentation also describes the
top-level package's `__init__.py`.

This is sufficient to classify the original smoke fixture as departing from the
documented generated-app layout. It does not prove namespace packages are
intentionally unsupported, and it does not establish a 0.10 regression. No
additional runtime was spent on this lower-priority anomaly.
