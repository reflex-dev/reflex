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

## VERIFICATION (independent, adversarial — 2026-08-28)

Verified the "breaking API removals ship without shims or pointer errors" claim
from scratch in fresh PyPI-only venvs (`uv venv` py3.11; `reflex==0.9.9a1` and
`reflex==0.9.8`, no reuse of the claimant's envs). VERDICT: **CONFIRMED**.

- `rx.config.get_config(reload=True)`: 0.9.8 returns `Config` (signature there is
  `get_config(reload: bool = False)` — a public keyword); 0.9.9a1 raises bare
  `TypeError: get_config() got an unexpected keyword argument 'reload'`. The new
  `reload_config()` exists in 0.9.9a1 but the error never mentions it; no shim in
  the wheel's `reflex_base/config.py` (checked — `console.deprecate` IS used
  elsewhere in that same file, so the infra was available).
- `reflex.components.dynamic.bundled_libraries`: list on 0.9.8 (non-underscored
  module global, wildcard re-exported, no `__all__` excluding it); bare
  `AttributeError` on 0.9.9a1. No module `__getattr__` in
  `reflex_base/components/dynamic.py`.
- Downstream impact re-proven live, not just by grep: installed
  `reflex-enterprise==0.9.4` (latest; its constraint `reflex[db]>=0.9.6` admits
  0.9.9) next to reflex 0.9.9a1 and ran
  `Var.create(lambda: rx.el.div("hi"))` — `LiteralLambdaVar
  ._validate_and_extend_return_expr` (reflex_enterprise/vars.py:143,
  `set(dynamic.bundled_libraries)`) raises the AttributeError; the identical call
  succeeds on 0.9.8 + enterprise 0.9.4. Any component-returning lambda (e.g.
  AG Grid cell renderers) hits this.
- Refutations attempted: not an env quirk (pure import-level API, fresh venvs, no
  server/proxy); not misuse (both names were public surface in 0.9.8); not
  pre-existing (0.9.8 baseline works). The removal is intentional and documented
  (`packages/reflex-base/news/6382.breaking.md`), so the defect is precisely the
  ABSENCE of a fallback/pointer path, contra the repo's own CLAUDE.md deprecation
  policy ("Reflex has downstream users — don't break them. Provide a fallback
  path during deprecation."). A `reload` kwarg accepted with `console.deprecate`
  + a module `__getattr__` returning the active context's list would cover both.
- Severity medium is fair for an alpha with a breaking-news entry; note the
  enterprise runtime breakage pushes real-world impact toward the high end.

## VERIFICATION (independent adversarial re-check, 2026-08-28)

Verifier: separate agent, fresh PyPI venvs (`envs/vregctx_a1` = reflex 0.9.9a1,
`envs/vregctx_098` = reflex 0.9.8), script `verify_repro.py` (output saved as
`verify_output.txt`). Both claims REPRODUCE exactly and are 0.9.9a1 regressions,
not environment quirks:

- 0.9.9a1: second bare `rx.App()` raises `ReflexRuntimeError` from
  `reflex_base/registry.py` `_set_app` ("...call `.fork()`..."); 0.9.8 happily
  creates two distinct App instances.
- 0.9.9a1: `from reflex.page import DECORATED_PAGES` ->
  `ImportError: cannot import name 'DECORATED_PAGES' from 'PageNamespace'
  (unknown location)`; 0.9.8 returns a `defaultdict`. The 0.9.8 `page.py` ALSO
  did the `sys.modules[__name__] = PageNamespace` replacement but deliberately
  re-exported `DECORATED_PAGES = DECORATED_PAGES` on the class — i.e. the
  symbol was intentionally kept importable through the namespace until now;
  0.9.9a1 dropped it with no `__getattr__` shim or deprecation. (Nit: the
  module is replaced by the PageNamespace CLASS, not an instance.)

Repro pitfall worth recording: running `python -c "import reflex..."` with cwd
= /home/user/reflex silently imports the CHECKOUT's `reflex/` package instead
of the venv's (sys.path[0] shadowing) and gives bogus results (my first 0.9.8
run "failed" with `cannot import name 'reload_config'` for exactly this
reason). Always run from a neutral cwd.

Documentation-status check (the substance of the claim):

- `packages/reflex-base/CHANGELOG.md` v0.9.9a1 Breaking Changes (release branch
  `origin/r/pre-2026.08.27-33148999938`): only `get_config(reload=True)` ->
  `reload_config()` and the `bundled_libraries` move. Neither the one-App-per-
  context raise nor the `DECORATED_PAGES` removal appears.
- Top-level `CHANGELOG.md` v0.9.9a1 DOES carry a #6382 entry ("The current
  App, the loaded Config, @rx.page registrations, and the bundled-library
  registry are now scoped to the active RegistrationContext...") — but it is
  filed under **Features**, not Breaking Changes, never says a second bare
  `App()` now raises, and never names `DECORATED_PAGES`. So "undocumented" is
  mildly overstated for the general scoping change, but accurate for both
  concrete failure modes.
- Real-world impact of `DECORATED_PAGES` (GitHub code search):
  `"from reflex.page import DECORATED_PAGES"` -> 165 files, including
  reflex-dev's OWN `templates` repo (dashboard sidebar/navbar) and
  `reflex-dev/reflex-enterprise` `demos/flow/flow/flow.py`; the bare symbol
  appears in ~880 files. First-party templates hit the confusing ImportError
  on upgrade.

VERDICT: CONFIRMED (medium). The one-App raise is intentional design with a
good message, but both breaks ship undocumented in the Breaking Changes notes
and `DECORATED_PAGES` (used by first-party code) vanishes with no shim and a
misleading error. Fix-agent scope: add both to 6382.breaking.md / changelog,
and consider a deprecation shim (namespace-level `DECORATED_PAGES` property or
`__getattr__` raising a pointed error naming
`RegistrationContext.decorated_pages`).

## VERIFICATION 2 (independent, adversarial — 2026-08-28): reflex.testing undeclared deps

Claim: `reflex.testing` (AppHarness) requires `uvicorn`/`psutil` that the published
wheel does not declare. VERDICT: **CONFIRMED** (low severity, NOT a regression).

Reproduced from the repro steps alone in fresh PyPI-only venvs (no reuse of the
claimant's envs), under `$SB/apps/verify_registration_context_2/`:

- `uv venv v99 --python 3.11 && uv pip install --python v99/bin/python
  --prerelease=allow 'reflex==0.9.9a1'` then `v99/bin/python -c 'import
  reflex.testing'` -> `ModuleNotFoundError: No module named 'uvicorn'` at
  `reflex/testing.py:28` (top-level `import uvicorn`). Exact match with the claim.
- 0.9.8 baseline (`v98`, same steps): identical failure at the same line —
  pre-existing behavior, not a 0.9.9a1 regression, exactly as the claimant said.
- psutil half verified empirically too: after `uv pip install uvicorn` into v99,
  `import reflex.testing` succeeds (uvicorn is the only import-time blocker), and
  calling `AppHarness.stop()` raises `ModuleNotFoundError: No module named
  'psutil'` — the `import psutil` at testing.py:473 is the unconditional first
  statement of `stop()`, so EVERY harness teardown on non-Windows hits it (psutil
  is a declared dep only on `sys_platform == 'win32'`).

Refutations attempted, all failed:

- Not an env quirk: wheel METADATA (reflex-0.9.9a1.dist-info) has no uvicorn in
  Requires-Dist at all, psutil only for win32, and the only extras are `db` and
  `pydantic` — there is no `[testing]` extra a user could install. uvicorn/psutil
  live only in the repo's dev dependency-group, which never reaches the wheel.
  Nothing in the runtime dep tree pulls uvicorn transitively (granian is the
  server; empirically absent after install).
- Not API misuse: `docs/enterprise/auth/testing.md` explicitly instructs users to
  "Exercise it with `AppHarness` (from `reflex.testing`)" and lists other deps to
  install (pytest-asyncio, playwright) but never uvicorn/psutil. Caveat:
  `rx.testing.AppHarness` is commented out of the API reference page
  (docs/app/reflex_docs/pages/docs/apiref.py:18), so it is semi-public — but the
  shipped docs actively route users into it.
- Not intentional design: the very same module guards `selenium` imports with
  try/except (testing.py:52) precisely so it is importable without dev extras;
  uvicorn/psutil just lack the same treatment.

Fix directions a fix-agent could take: declare uvicorn (+ psutil without the
win32 marker) as deps of the wheel, or add a `testing` extra, or lazy-import both
with an actionable error message. Severity "low" is fair: docs-following
downstream users hit it immediately, but the workaround (pip install uvicorn
psutil) is trivial and it has been like this since at least 0.9.8.

## VERIFICATION 3 (independent, adversarial — 2026-08-28): bundle_library wipe + subpath rewrite

Claim: (1) `compile_app()` silently discards user/app-level `bundle_library()`
registrations; (2) the dynamic serializer never rewrites SUBPATH imports of a
bundled lib, emitting bare specifiers that throw in the browser.
VERDICT: **CONFIRMED** (low severity; NOT a 0.9.9a1 regression — byte-identical
on 0.9.8).

Reproduced from the repro steps alone: own app (`verify3_vdynapp.py`, written
fresh — `bundle_library("lucide-react")` at module import + a computed
`rx.Component` var containing `rx.icon("apple")`), own driver
(`verify3_drive_vdynapp.py`), fresh 0.9.8 venv (`envs/vregctx3_098`), no reuse
of the claimant's apps/venvs. Ports 3932/8932.

- Serializer-level (no server/network — `verify3_serializer_probe.py`, output in
  `verify3_serializer_output.txt`): with lucide-react registered in the active
  context, `serialize(rx.vstack(rx.icon("apple")))` emits
  `import LucideApple from "lucide-react/dist/esm/icons/apple.mjs"` — a bare
  specifier the window-rewrite loop never touches (it only substring-matches the
  exact `from "<lib>"` with closing quote; `rx.icon` uses `package_path` deep
  imports, `format_library_name()` strips only `@version`, never subpaths).
  Calling `reset_bundled_libraries()` (what `compile_app()` does at compiler.py
  ~1202 in the wheel / 1209 in the tree) drops lucide-react back to the 4
  defaults. Both verdicts True on 0.9.9a1 AND on 0.9.8 with byte-identical
  emitted import lines; wheel diff confirms the reset+plugin-only-readd and the
  `f'from "{lib}"'` loop are unchanged between 0.9.8 and 0.9.9a1.
- End-to-end (0.9.9a1, `reflex run` dev + Chromium): `window.__reflex` keys =
  4 defaults + `@radix-ui/themes` only — the import-time
  `bundle_library("lucide-react")` never reaches the frontend bundle. Server log
  (`verify3_run_dev_excerpt.log`) captured BOTH failure modes in one page load:
  (a) `TypeError: Failed to resolve module specifier
  "lucide-react/dist/esm/icons/apple.mjs"` from the eval'd data-URI module —
  the granian worker's hydrate-time serialization runs in a context that KEPT
  the user's lucide registration (backend short-circuits compile before the
  reset), so the subpath import stays bare; (b) a second exception whose data
  URI shows the compile-time pass (post-reset context) emitted
  `https://cdn.jsdelivr.net/npm/lucide-react@1.26.0/+esm/dist/esm/icons/apple.mjs`
  with radix destructured from `window.__reflex` — i.e. the two serialization
  passes disagree about what is bundled, and each is broken a different way.
- Refutations attempted: NOT an env quirk — the bare specifier can never resolve
  inside a data:-URI ES module in any browser regardless of network (the
  CDN-unreachable part of the log IS env-specific, but the claimed defect
  reproduces with zero network at the serializer level, and the hydrate-pass
  TypeError would fire on the open internet too, breaking the dynamic block
  post-hydration). NOT clearly API misuse — `bundle_library` is a public,
  non-underscored, wildcard-re-exported symbol (used downstream, e.g.
  reflex-enterprise touches this module), and even the officially-documented
  plugin path (`get_frontend_dependencies`) feeds the same rewrite loop, so any
  plugin-bundled lib with `package_path` deep imports (as reflex's own `rx.icon`
  has) hits defect (2). NOT a regression — 0.9.8 identical (my serializer runs +
  wheel source diff + claimant's 0.9.8 server logs).
- Nuance vs the claim: "compile_app() silently discards" is precisely right for
  the frontend compile pass; the backend worker actually PRESERVES the user
  registration (it returns before the reset), which is what turns the subpath
  bug from latent into a thrown TypeError. Sharpest user-facing irony: WITHOUT
  `bundle_library` the icon import goes to the CDN and works (on open internet);
  calling the API makes rendering strictly worse.

CONFIRMED with the explicit caveat: pre-existing 0.9.8 behavior faithfully
preserved, so low severity is right and it is NOT release-blocking for 0.9.9a1.
Worth fixing while #6382 reworks this plumbing: preserve non-default
registrations across `compile_app()` resets (or snapshot user registrations
before reset and re-add alongside plugin deps), and rewrite subpath imports of
bundled libs (match `from "<lib>/` too — though that requires the window bundle
to expose subpath modules, so the simpler fix may be CDN-mapping subpath
imports even when the lib is bundled). Killed all servers/browsers (verified
via ps; two leftover node processes on this host belong to the verify_routing_0
cluster, not this verification).
