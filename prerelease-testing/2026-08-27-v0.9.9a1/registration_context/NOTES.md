# registration_context cluster — reflex 0.9.9a1 (PR #6382)

Cluster: RegistrationContext multi-app isolation + breaking API moves
(`get_config(reload=True)` -> `reload_config()`, module-level `bundled_libraries`
-> context attribute, App/Config/decorated-pages scoped to the active context).

Tested against `reflex==0.9.9a1` from PyPI (isolated venvs), baselined against
`reflex==0.9.8` from PyPI. Date: 2026-08-28.

## How to rerun

Venvs (all installed from PyPI, `--prerelease=allow`):

- `envs/smoke` — prebuilt shared 0.9.9a1 venv (used for probes + `reflex run`).
- `envs/rcx` — own venv: `reflex==0.9.9a1 playwright==1.62.0 pytest psutil uvicorn`
  (uvicorn/psutil are REQUIRED to import/use `reflex.testing` but are NOT declared
  deps of reflex — see Observations).
- `envs/rc098` — baseline: `reflex==0.9.8` + same test deps.
- `envs/driver` — playwright driver for `reflex run` apps.
  Chromium at `/opt/pw-browsers/chromium`.

Commands (from this directory):

```
# (a) breaking-API surface, run on both versions and diff:
REFLEX_TELEMETRY_ENABLED=false <venv>/bin/python test_api_surface.py
#   -> saved outputs: api_surface_099a1.txt, api_surface_098.txt

# (b1) two rx.App in one process via fork(), no servers:
REFLEX_TELEMETRY_ENABLED=false <smoke>/bin/python test_multiapp_isolation.py
#   -> saved output: multiapp_isolation_099a1.txt (11/11 PASS)

# (b2)+(d) AppHarness twice in ONE pytest process — sequential AND simultaneous,
# different app sources, driven end-to-end in Chromium:
REFLEX_TELEMETRY_ENABLED=false <rcx>/bin/python -m pytest test_appharness_multi.py -x -s -q
#   -> logs: seq_test.log, sim_test.log (both PASS)
# IMPORTANT: do NOT override NO_PROXY in this environment — the inherited value
# whitelists registry.npmjs.org for direct access; clobbering it makes `bun add`
# fail with ConnectionClosed (that was a self-inflicted env mistake, not a bug).

# (c) dynamic components + bundle_library, real `reflex run`:
cd dynapp && REFLEX_TELEMETRY_ENABLED=false <smoke>/bin/reflex run \
    --frontend-port 3420 --backend-port 8420 --loglevel debug > run_dev.log 2>&1 &
<driver>/bin/python ../drive_dynapp.py http://localhost:3420
# prod mode (single port required, see Observations):
cd dynapp && <smoke>/bin/reflex run --env prod --frontend-port 8422 --backend-port 8422
# 0.9.8 baseline: init a copy with rc098's reflex, drop in the same dynapp.py
# (dynapp098/ here), run on 3421/8421 (dev) or 8423 (prod), drive the same script.

# (c addendum) dynamic component under AppHarness (in-process backend):
REFLEX_TELEMETRY_ENABLED=false <rcx>/bin/python -m pytest test_appharness_dynamic.py -x -s -q
#   -> logs: dynharness_test.log (0.9.9a1), dynharness_098.log (0.9.8)

# double-App probe used for the behavior-change finding:
#   (inline in NOTES; also covered by test_multiapp_isolation.py check 2)
```

## Results

### (a) Breaking-API surface (0.9.9a1 vs 0.9.8)

| call | 0.9.8 | 0.9.9a1 |
|---|---|---|
| `get_config()` | Config | Config (signature now `() -> Config`) |
| `get_config(reload=True)` | worked | `TypeError: get_config() got an unexpected keyword argument 'reload'` |
| `get_config(True)` | worked | `TypeError: get_config() takes 0 positional arguments but 1 was given` |
| `reflex.config.reload_config()` | ImportError | works (returns fresh Config) |
| `reflex.components.dynamic.bundled_libraries` | list | `AttributeError: module 'reflex.components.dynamic' has no attribute 'bundled_libraries'` |
| `reflex_base.components.dynamic.bundled_libraries` | list | AttributeError (same) |
| `bundle_library()` / `reset_bundled_libraries()` | work (module global) | work (write the active RegistrationContext) |
| `reflex.page.DECORATED_PAGES` | `defaultdict(list)` | GONE — `from reflex.page import DECORATED_PAGES` -> `ImportError: cannot import name 'DECORATED_PAGES' from 'PageNamespace' (unknown location)` |
| `rx.App(); rx.App()` (same process, no fork) | second App OK | `ReflexRuntimeError: A RegistrationContext can only be associated with a single App instance. To create another App, call .fork() ...` |

Notes for downstream libraries (reflex-enterprise etc.):

- No deprecation shims anywhere: `get_config(reload=True)` dies with a bare
  TypeError that never mentions `reload_config()`; `bundled_libraries` dies with
  a bare AttributeError (this one is already FINDING-001 — reflex-enterprise
  0.9.4 reads it in `LiteralLambdaVar`). A module `__getattr__` shim or
  `console.deprecate` path would soften both.
- `reflex.page.DECORATED_PAGES` removal is NOT mentioned in
  `packages/reflex-base/news/6382.breaking.md`, and the ImportError text is
  confusing ("from 'PageNamespace' (unknown location)") because `reflex.page`
  the module is replaced by a PageNamespace instance in `sys.modules`.
- The new one-App-per-context rule is likewise not in the breaking notes. The
  error message itself is good (tells you to fork()), but code that re-runs
  `app = rx.App()` in one process (notebook cell re-execution, doc generators,
  test suites without AppHarness) breaks where 0.9.8 silently worked.

### (b1) Two apps in one process via fork() — 11/11 PASS

`test_multiapp_isolation.py` (0.9.9a1): second bare `App()` raises with fork
guidance; after `ctx.fork()` + `RegistrationContext.set()` a second App works;
`ctx.app`/`ctx.config` resolve per-context; `@rx.page` registered BEFORE the fork
carries into the fork (documented fork semantics); `@rx.page` registered in the
fork does NOT leak back; `add_page` routes don't bleed; states registered while
the fork is active land only on the fork; `get_config()` caches per-context
(distinct Config instances); `bundle_library()` in the fork leaves the original
context untouched.

### (b2)+(d) AppHarness twice in one pytest process — PASS, no cross-talk

`test_appharness_multi.py`, real Chromium, two DIFFERENT app sources (AppOne:
counter += 1, unique route `/one-only`; AppTwo: counter += 10, unique `/two-only`;
same State class name in both):

- sequential: both harnesses serve their own index marker, counters increment
  with the correct per-app delta (so event handlers hit the right State class),
  each app 404s the other's unique route. PASS (seq_test.log).
- simultaneous (two dev servers + two backends in ONE process, interleaved
  clicks): all the same checks pass, no event cross-talk, no page bleed.
  PASS (sim_test.log). This is the motivating case of #6382 and it works.
- Browser console in all runs: only the known-benign lines (HydrateFallback dev
  log, vite connecting/connected, React DevTools info).

### (c) dynamic components + bundle_library end-to-end

App `dynapp/`: static `rx.icon`, a plain `rx.Component` state var (radix button
swapped by an event), a computed `rx.Component` var containing a lucide icon +
state label + event button, and a user-level `bundle_library("lucide-react")` at
module import time.

Result matrix (0.9.9a1 === 0.9.8 EXACTLY, dev and prod — no regression):

- `window.__reflex` after compile: defaults + `@radix-ui/themes` (plugin) in
  both versions/modes. The user's import-time `bundle_library("lucide-react")`
  NEVER lands in `window.__reflex`: `compile_app()` calls
  `reset_bundled_libraries()` then re-adds only plugin deps, wiping import-time
  registrations (same code path in 0.9.8, compiler.py ~1202/1209).
- dev `reflex run`: runtime re-serialization of Component vars happens in the
  granian worker whose context/list lacks the plugin libs, so the emitted JS
  imports `@radix-ui/themes@3.3.0/+esm` and lucide from cdn.jsdelivr.net. In
  this proxied env the CDN is unreachable -> computed dynamic block does not
  render and the event-swapped button fails (identical 4/8 checks and identical
  CDN URLs on 0.9.8 — see baseline098/).
- Additionally the first serialization pass (context WITH lucide) emits a BARE
  specifier `import ... from "lucide-react/dist/esm/icons/apple.mjs"` inside the
  eval'd data-URI module -> `TypeError: Failed to resolve module specifier` in
  the browser: the window-rewrite in the dynamic serializer only matches exact
  `from "<lib>"` imports, so SUBPATH imports of a bundled lib are never
  rewritten. Present in 0.9.8's log too (2 occurrences each). Pre-existing
  sharp edge for library authors, faithfully preserved.
- prod `reflex run --env prod`: BETTER than dev — radix resolves from
  `window.__reflex` (no CDN request for it; event-driven swap works), only the
  wiped user lib goes to CDN. Identical on 0.9.8 (5/8 checks both).
- AppHarness (in-process backend, copied contextvars): computed dynamic
  component renders with ZERO CDN requests and its event handler works
  (`test_appharness_dynamic.py` PASS on both versions) — the RegistrationContext
  bundled-library plumbing is correct when the context is actually shared.

### Observations / anomalies (recorded, mostly pre-existing)

1. `reflex.testing` (AppHarness) requires `uvicorn` and `psutil` at import/stop
   time but neither is a dependency of the published reflex 0.9.9a1 wheel —
   downstream users following the AppHarness testing docs hit
   `ModuleNotFoundError: No module named 'uvicorn'`. (Same in 0.9.8.)
2. AppHarness + disk state manager: persisting a state whose computed
   `rx.Component` var is cached raises
   `StateSerializationError ... Can't pickle <function ...relabel>: it's not the
   same object as <module>.<State>.relabel` in the backend thread (state still
   works via websocket; only disk persistence is skipped). Present on 0.9.8 too
   (dynharness_098.log). Benign-but-noisy warning in every AppHarness run using
   dynamic components.
3. Prod mode now enforces "frontend and backend must run on the same port" —
   `reflex run --env prod --frontend-port 3422 --backend-port 8422` exits with
   that message. Not part of this PR (prod serves frontend from the backend),
   just something to know when scripting prod runs.
4. The vite `configLoader: 'native'` warning and the npmmirror probe failures are
   already on the shared ledger; nothing new seen beyond them.

### Screenshots

- `dynapp_initial.png`, `dynapp_after_clicks.png` — dev 0.9.9a1 (dyn block missing
  due to CDN-blocked env).
- `baseline098/dynapp_initial.png`, `baseline098/dynapp_after_clicks.png` — dev 0.9.8
  (identical rendering).
- `prod_run/dynapp_*.png`, `prod_run098/dynapp_*.png` — prod, both versions
  (swap works, dyn block still needs CDN for lucide).
- `dynharness.png` — AppHarness dynamic component fully rendered, no CDN.
