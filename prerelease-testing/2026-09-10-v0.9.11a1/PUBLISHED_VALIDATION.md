# Independent validation of the published remediation releases

The task is to determine whether each claim in [RELEASE_PLAN.md](./RELEASE_PLAN.md)
is observable in installed published packages. Report findings; do not patch framework
code, substitute a checkout, or treat a merged PR as a passing result. The a1 campaign's
[FINDINGS.md](./FINDINGS.md) and cluster `NOTES.md` files contain original reproductions.

## Published targets and evidence boundary

These versions had both non-yanked wheels and source distributions on PyPI when the
handoff was assembled. [REVIEW_STATUS.json](./REVIEW_STATUS.json) contains exact artifact
URLs and SHA-256 hashes; retrieve metadata again and record the time of your review.

| Package | Target | Finding(s) | Published metadata |
| --- | --- | --- | --- |
| reflex | 0.9.11a2 | 003, 022, 025, 030 | [PyPI JSON](https://pypi.org/pypi/reflex/0.9.11a2/json) |
| reflex-base | 0.9.11a2 | 005, 014, 022 | [PyPI JSON](https://pypi.org/pypi/reflex-base/0.9.11a2/json) |
| reflex-components-moment | 0.9.4a2 | 002, 033 | [PyPI JSON](https://pypi.org/pypi/reflex-components-moment/0.9.4a2/json) |
| reflex-components-radix | 0.9.9a2 | 022 plugin registration | [PyPI JSON](https://pypi.org/pypi/reflex-components-radix/0.9.9a2/json) |
| reflex-otel | 0.1.0a2 | 027 | [PyPI JSON](https://pypi.org/pypi/reflex-otel/0.1.0a2/json) |

The [GitHub a2 release](https://github.com/reflex-dev/reflex/releases/tag/v0.9.11a2)
and its component tags include the release changes. This handoff verified downloaded
wheel hashes and compared all 11 changed runtime files with tagged release source
(four in reflex, five in reflex-base, one each in Moment and Radix). OTel is a docs-only
change. It did not install/run the wheels or establish that the hosted documentation
site has deployed the changes. Those observable checks belong to this review.

#7109's release cherry-pick is `6d3c9ed9b8ad` (full ID in the snapshot). It adapts the
main-branch change to a release without `frontend_lazy_bundled_libraries`. Test the
published eager bundling behavior; do not require the unpublished lazy feature to exist.

## Isolated installation and provenance

1. Create fresh a1 and a2 virtual environments and app directories **outside every
   Reflex checkout**. Use PyPI distributions only: no editable/local/path/VCS overrides,
   `uv sync`, or copied framework modules. Disable inherited uv project configuration
   and any `PYTHONPATH` that could expose a checkout. The campaign's old absolute paths
   are examples; do not assume those environments still exist.
2. Explicitly pin the changed component packages. `reflex` pins `reflex-base` exactly
   in its published metadata but only specifies floors for components; upgrading the
   top-level package alone can leave an old Moment or Radix installed. Keep and report
   the complete resolver output for both environments.
3. Run the original repro first on the pinned a1 stack, then unchanged on a2. Use
   0.9.10.post2 when the original regression comparison needs it. Reproduce failures
   rather than relying on old screenshots. A baseline that never fails is inconclusive.
4. Build a clean frontend for each stack. Also exercise an in-place a1→a2 upgrade for
   dynamic bundling and Moment after the clean runs, preserving the app's normal assets
   and lockfiles. Record which package versions the upgraded environment actually uses.
5. Keep browser/driver dependencies separate from app dependencies. Add database/admin
   and OTel dependencies only to their respective test environments. In particular, test
   005 once on a default Reflex installation plus current Pyright, without repo extras.

Example target setup, executed from a neutral scratch directory:

```sh
REVIEW_ROOT="$(mktemp -d /tmp/reflex-published-review.XXXXXX)"
cd "$REVIEW_ROOT"
uv --no-config venv env-a2 --python 3.11
uv --no-config pip install --python env-a2/bin/python --prerelease=allow \
  'reflex==0.9.11a2' 'reflex-base==0.9.11a2' \
  'reflex-components-moment==0.9.4a2' 'reflex-components-radix==0.9.9a2'
uv --no-config pip freeze --python env-a2/bin/python > installed-a2.txt
uv --no-config pip check --python env-a2/bin/python
```

For the comparison environment use `reflex==0.9.11a1`, `reflex-base==0.9.11a1`,
`reflex-components-moment==0.9.4a1`, and `reflex-components-radix==0.9.9a1`.
For 027 add `reflex-otel==0.1.0a1` / `0.1.0a2`, the SDK, and the documented HTTP
exporter to the corresponding environments. The original campaign's other pinned
component versions are listed near the start of FINDINGS.md; retain matched versions
across A/B tests and record any necessary deviations.

Before every reproduction save `sys.executable`, Python version, `sys.path`,
`importlib.metadata.version()` for every installed Reflex distribution, and each imported
module's `__file__`. Assert those paths are under the intended environment's site-packages.
Inspect `direct_url.json` if present and reject local/editable origins. Record artifact
filenames/hashes, OS, Node, the **Bun actually used by Reflex**, browser, Pyright, Granian,
Redis, starlette-admin, and relevant npm package versions. This proves what was tested.

Run CLI entry points from the neutral app directory, for example with
`uv run --no-project --no-config --python /absolute/env-a2/bin/python reflex run ...`.
Keep telemetry disabled unless testing OTel. Use fresh ports and track/stop your own
servers and browsers. Use the original driver scripts after replacing historical paths.

## Acceptance checks for the nine claims

### 002 — documented breaking Moment callback behavior

Use `up_counter_todo_clock/verification/` and the Moment reproduction from FINDINGS.md.
Check static dates, `interval=0`, periodic updates, remount/navigation, and reload in dev
and prod. Mount callbacks are expected to remain; do not interpret their presence as a
failed fix. Confirm that the published 0.9.4a2 release notes and the accessible Moment
documentation explain mount/remount calls and possible double invocation in dev Strict
Mode. Record the exact documentation URL and observed content. If source docs changed
but hosted docs are stale, report that separately from correct package behavior.

### 003 — backend-initiated deltas across real forked workers

Use `bg_rehydrate/verification/` and the VERIFICATION section in its NOTES.md. Run a real
production app with Redis and multiple forked Granian workers (nine as in the original
repro when resources allow), plus a one-worker control. Establish which worker owns the
browser socket and demonstrate updates originating from another worker. Observe distinct
worker identities after startup and stable identity during processing.

Send repeated backend-initiated increments, including the original six-event sequence
and rehydrate/eviction path. Compare every expected sequence/value with Redis and browser
WebSocket/UI evidence. **Pass requires live cross-worker delivery without an extra click
or reload to catch up**, not just correct stored state or a mocked publish call. Record
worker count, PIDs, ownership, delivered/expected counts, and actual process start method.
If the environment cannot exercise forked workers, report that limitation explicitly.

### 005 — current Pyright and shipped typing files

Reuse `orch_probes/hp_types.py` and the hybrid-property cluster's examples. Install current
Pyright independently of the repo pin and record its version; also run 1.1.414 (the
known failing checker) and 1.1.411 (control) in isolated checker environments. Resolve types
against the installed wheel, not source or regenerated local stubs.

Class access must reveal the appropriate frontend StringVar/NumberVar/BooleanVar,
container/optional/custom frontend type; instance access must remain the Python type.
Include inherited properties and explicit `.var` return types. `Any` is a failure even
with zero diagnostics. Repeat the primary check with a default Reflex install plus the
latest checker, without loading the framework's development dependency set.

### 014 — path validation and valid-path controls

Reuse the `frontend_path_validation` probe in `orch_probes/`. Confirm early rejection of
`/a `, `/a.`, `/ .`, `//srv`, and `/a//b`, including trailing-dot/space segments before
an optional final slash. The error should identify the invalid configuration before build
output is moved. Keep existing traversal/backslash/drive-letter rejection working.
Controls: empty/root prefixes, `/docs`, `/docs/`, interior spaces, and ordinary dotted
names remain usable. Build/export a valid prefixed app with SSR disabled as well as enabled.
Wrong routing from the separate double-prefix bug (009) is not evidence that validation
014 was fixed or failed; record it separately.

### 022 — complete dynamic component trees, initial state, and fresh backends

Start with the original `bundle_library()` reproduction referenced by FINDING-022 and
#6975, then use this additional app body in a fresh initialized project:

```python
import reflex as rx
from reflex_base.components.dynamic import bundle_library


class State(rx.State):
    count: rx.Field[int] = rx.field(0)
    activated: rx.Field[bool] = rx.field(False)

    @rx.event
    def set_count(self, count: int):
        self.count = count

    @rx.event
    def toggle(self):
        self.activated = not self.activated

    @rx.var
    def counter_ui(self) -> rx.Component:
        if self.activated:
            return rx.hstack(
                rx.icon("apple", color="green", id="dynamic-icon"),
                rx.button("-", on_click=State.set_count(self.count - 1)),
                rx.text(self.count, id="count"),
                rx.button("+", on_click=State.set_count(self.count + 1)),
            )
        return rx.icon("tag", color="red", id="initial-icon")


bundle_library(rx.text())
bundle_library(rx.hstack(rx.el.div(rx.icon("apple"))))


def index() -> rx.Component:
    return rx.vstack(
        rx.icon("alert"),
        rx.button("Activate", id="activate", on_click=State.toggle),
        State.counter_ui,
    )


app = rx.App()
app.add_page(index)
```

The Apple icon occurs only as a grandchild in the registered prototype and after an
event in live state. Tag has **no explicit registration**. Do not add one or register the
whole Lucide package to make a failed test pass.

- Initial load shows Tag; Activate shows Apple and count; increment/decrement work;
  deactivation restores Tag; reactivation, navigation and reload keep working. Capture
  console errors, failed CDN/module requests, WebSocket deltas, and screenshots.
- Inspect emitted `root.jsx` and actual `window.__reflex`: both exact Lucide subpaths
  must exist before use. `lucide-react`'s broad root must not be bundled merely because
  a specific icon was registered. Inspect emitted dynamic modules for correct default
  and named bindings and original module-path keys.
- Repeat with a libraryless outer `rx.el.div`, a genuine component-valued prop containing
  a nested tree, a reactive icon name, and a specialized component whose `import_var`
  selects a subpath. Include a package used only by an initial-state component to check
  installation, not merely registry membership. The release's
  [codegen tests](https://github.com/reflex-dev/reflex/blob/v0.9.11a2/tests/units/compiler/test_dynamic_components_codegen.py)
  provide fixture examples; copying app/test logic is fine, importing checkout code is not.
- Cover a module first imported while evaluating a page, repeated compilations, duplicate
  explicit registrations, and removing compiler-only Radix usage. Explicit entries persist;
  stale compiler discoveries are cleared. Check exact subpath-string registration too.
- Check both generated alias collisions and runtime lookup with real resolvable module
  paths: local alias suffixes must not become `window.__reflex` keys. Check default,
  named, namespace, and mixed imports from a root and a subpath.
- Invalid inputs (a factory/class instead of a prototype, integer, etc.) must produce
  the documented `TypeError`, while library strings and valid component instances work.
- Run standalone dev and prod apps, then serve a prebuilt frontend with a **fresh backend
  process that skips compilation**. Verify initial-state discovery and event rendering
  there, including startup with/without the saved stateful-page marker. Confirm this does
  not trigger a second full frontend build. Do not reuse a compiler-warmed Python process
  as the only backend control.

### 025 — observable admin pages, static assets, and request context

Reuse `orch_probes/adminapp/` and `admin_isolate.py`. Install `reflex[db]==0.9.11a2`
and test starlette-admin 1.0.1, 1.0.0, and 0.17.1 in separate environments. Fetch the public
`/admin/` and model list, follow links, fetch an actual referenced static asset, and
exercise configured login behavior rather than demanding 200 for an unconfigured login
route. There must be no `NoMatchFound` 500. Include an API transformer that wraps the API
in Starlette and a normal event/request-context control. A plain-Starlette control alone
does not verify Reflex's mount.

### 027 — execute the published HTTP-exporter recipe

Copy the recipe as a user sees it from the published reflex-otel README/PyPI description
and the observability guide; save the URL/content. Install only its stated exporter and
SDK dependencies. Confirm it selects HTTP/protobuf, start a real local OTLP receiver,
and observe trace and metric requests after exercising an app. A configured provider
with no emitted telemetry is insufficient. Do not silently add a gRPC exporter.
An HTTP collector receiving the expected payloads is the observable success criterion.
Fail-fast SDK configuration behavior and initial dev compile-span loss (028) were not
part of this documentation fix; report them separately.

### 030 — accurate breaking note, unchanged values

Compare the original state-delta sample in FINDINGS.md / `event_hotpath/` as parsed JSON
across the baseline and target, checking keys and values rather than text order. Confirm
the published 0.9.11a2 notes explain potential ordering differences and recommend parsed
comparison or normalization. Reverting the order is not an acceptance criterion.

### 033 — per-component locale isolation

Reuse `components_bumps/leakapp2/` and `scripts/drive_leak.py`. In both dev and prod,
put French and default-English dates together in both component orders. Include relative
dates/title attributes, a route with only default-English moments, navigation away/back,
and reload. Explicit `locale="en"` must compile/render without a missing-module request.
Exercise a reactive locale switching between languages and empty/None/default inputs;
no sibling or subsequent route should unexpectedly change language. Include the existing
duration-format control to catch integration regressions after the #7110 conflict fix.
Count `defineLocale` warnings separately under 034 / #7099; do not claim that separate
open issue resolved merely because visible locale isolation works.

## High-impact adjacent check: 018 is not closed by assertion

[#7096](https://github.com/reflex-dev/reflex/issues/7096) remains open. #7109 changes
related initialization, so independently rerun the exact minimized example in
`ent_aggrid/verification/issue2_hydrate_delta/` with published enterprise 0.9.5, in fresh
dev and a separately started non-compiling backend serving a production build.

Click the counter to 3, reload with the same session token, then click once. Passing
delivery means the reload still shows 3 and the next click shows 4, with no serializer
failure or dropped hydrate packet. A reload showing 0 followed by a jump to 4 reproduces
the defect. Retain the Python-callable state value: removing it or adding an explicit
Radix registration changes the reproduction. Run those variants only as labeled controls.

The reviewed issue narrows the original broad wording: the trigger is an exception from
a **registered** serializer validating incomplete bundle metadata, not any arbitrary
unsupported Python value (the latter control serializes as null). The issue is not
dev-only: a separately launched non-compiling production backend was affected too.
Correct state in Redis, `is_hydrated=true`, or a compiling production process alone does
not prove packet delivery. Missing frontend dispatchers in enterprise finding 036 are
a different failure after delivery. Record partial improvement without closing either
issue or claiming general serializer-error isolation.

## Return format and evidence

Write a new `PUBLISHED_VALIDATION_RESULTS.md` alongside this handoff, with an environment
manifest and one row for each of 002, 003, 005, 014, 022, 025, 027, 030, 033, plus the
separately labeled 018 check. Use subrows for configurations so a dev pass cannot hide
a prod failure. Suggested fields:

| Finding / case | Exact versions / mode | Baseline observation | Target observation | Verdict | Evidence paths |
| --- | --- | --- | --- | --- | --- |
| 022 / nested activation | Fill from installed distributions | Actual failure or inconclusive | Actual UI/network outcome | See below | App, commands, logs, screenshot |

Verdicts: **verified fixed**, **verified documented/accepted behavior** (002/030 and
the documentation part of 027), **still reproduces**, **partially fixed**,
**not yet published**, **blocked**, or **inconclusive**. For blocked/inconclusive checks,
state the missing capability or unresolved baseline and retain evidence. Do not turn
absence of a test run into a pass.

Save exact runnable app/probe sources, install/freeze and provenance output, rerun commands,
server logs, browser console/network failures, relevant WebSocket frames and screenshots.
Link each conclusion to those artifacts. Separate source/release-note inspection from
installed-package behavior and deployed-documentation observations. End with any claimed
fixes that fail and the smallest reproduction for each; do not repair them during review.
