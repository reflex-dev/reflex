# Release plan — what blocks 0.9.9 final vs. what gets filed for later

Triage of the 29 confirmed findings in [FINDINGS.md](./FINDINGS.md) against the release
criteria: **confirmed regression**, **significant user impact or very simple to fix**, or
**security-related** → fix before release. Everything else → GitHub issue, fix after
release. Nothing here has been fixed by us; this is the review plan.

## Already in flight (verify, then check off)

| PR | Covers | Gap check |
|---|---|---|
| [#6967](https://github.com/reflex-dev/reflex/pull/6967) bundled_libraries shims | FINDING-001/021/022 (critical: rxe 0.9.4 ag-grid python-callable renderers/formatters crash compile; dnd LambdaVar surface) and the `bundled_libraries` half of FINDING-008 | Shim restores module-level reads with deprecation — rxe `vars.py:143` does `set(dynamic.bundled_libraries)`, so this should unbreak it. Re-verify with the minimal trigger in `ent_aggrid/` (one lambda `cell_renderer`) once the next alpha is published. Does NOT cover `get_config(reload=True)` (FINDING-008 other half) or `DECORATED_PAGES` (FINDING-023). |
| [#6959](https://github.com/reflex-dev/reflex/pull/6959) vite plugin import extension + resolveId filter | FINDING-028 (configLoader:'native' warning on every dev start) | Does NOT cover the other new vite 8.2 warnings — `build.rollupOptions.jsx` invalid input option and `advancedChunks` deprecation (FINDING-012/015/019) — those come from different template options. |

## Fix before release

### Security

1. **FINDING-007 — upload sanitizer returns `..` for all-dots filenames** (MEDIUM).
   `_sanitize_upload_filename` (reflex-components-core, #6753) maps `"..."`-style names to
   the traversal token `..`, escaping the upload dir and 500ing. Path traversal in a
   network-facing handler; the fix is a small guard in one function.
2. **FINDING-004 — `client_error` handler unhandled TypeError on no-arg emit** (MEDIUM).
   `App.on_client_error(self, sid, data)` has no default for `data`; a bare
   `emit("client_error")` from any client raises before every anti-abuse guard
   (sanitization, bounding, rate limits) runs. One-line default + early type check.

### Confirmed regressions vs 0.9.8

3. **FINDING-023 — `reflex.page.DECORATED_PAGES` removed with no shim** (HIGH). Breaks
   published reflex-enterprise (flow demo) at import with a confusing error; not mentioned
   in the #6382 breaking-change note. Same shim pattern as #6967 (`__getattr__` resolving
   against the active RegistrationContext + deprecation). Fold in FINDING-009's
   documentation duty: changelog the second-bare-`rx.App()` ReflexRuntimeError (or decide
   to allow it) and the DECORATED_PAGES move.
4. **FINDING-003 — background-task `on_load` cancelled on navigation** (MEDIUM). #6593's
   supersedes cancellation now kills `@rx.event(background=True)` on_load chains that
   survived navigation on 0.9.8 (button-started background tasks still survive). Decision
   needed: if intended, add a breaking-change/changelog note (and consider an opt-out);
   if not, exempt background children from chain cancellation.
5. **FINDING-005 — `REFLEX_ENABLE_FULL_LOGGING` drops granian worker records** (MEDIUM).
   Worker's file handler is closed post-fork (granian's `dictConfig` runs with
   `disable_existing_loggers`); worker records silently vanish from the log file and
   legacy console file-writes leak to stdout, breaking `--json` purity. Regression in the
   new logging pipeline. If the post-fork re-init fix is too involved for the release,
   minimum bar: document the limitation.
6. **FINDING-012/015/019 — vite 8.2 prod-build warnings from template options** (LOW,
   one fix). Generated `.web/vite.config.js` passes `build.rollupOptions.jsx: {}`
   (rejected by rolldown) and deprecated `advancedChunks` placement — two warnings on
   every `reflex export`/prod build. Template tweak; pairs naturally with #6959.
7. **FINDING-027 — console warnings print `dict\[str, ...]` backslashes** (LOW). Rich
   markup escaping leaking into terminal text in the new logging sink; cosmetic, trivial,
   and very visible (every compile-time arg-mismatch warning).

### Significant user impact and/or very simple

8. **FINDING-002 + FINDING-006 — PEP 695 aliases compile but cannot be mutated** (HIGH +
   MEDIUM, one fix). #6944 wired `resolve_type_alias()` only into `Var.guess_type`;
   `_isinstance` (State.`__setattr__` validation) and `typehint_issubclass` don't resolve
   `TypeAliasType`, so every mutating handler on an alias-annotated var raises TypeError,
   and an uncalled alias-annotated handler crashes page compile. The headline typing
   feature of this release is unusable for mutable vars without this; root cause and both
   call sites are already identified in FINDINGS.md.
9. **FINDING-010 — `library="react-router-dom"` fails silently/cryptically** (MEDIUM).
   The one migration the changelog demands from custom-component authors: dev silently
   installs unpinned react-router-dom@7 (works by accident, RR7/RR8 duals loaded), prod
   fails cryptically. A targeted error/warning naming the `react-router` migration makes
   the documented breaking change self-explaining. Small guard in package collection.
10. **FINDING-011 — `reflex run` hangs after fatal node-version error** (MEDIUM).
    `SystemExit` from `validate_frontend_dependencies` dies inside the ThreadPoolExecutor
    and the CLI waits forever. Users hitting the new Node 22.22 floor (raised by this
    release) get a hang instead of the error. Simple exception propagation fix.
11. **FINDING-008 (remaining half) — `get_config(reload=True)` bare TypeError** (MEDIUM).
    #6967 covers `bundled_libraries`; give `get_config` the same courtesy — accept and
    deprecate the `reload` kwarg (delegating to `reload_config()`) or raise a pointered
    error. Trivial alongside #6967.

## File as GitHub issues, fix after release

### reflex-dev/reflex

- **FINDING-013** — `reflex run --json --loglevel debug`: granian's own startup/shutdown
  lines are plain text on stdout, breaking strict JSON-lines parsing.
- **FINDING-014** — `rx.Model` subclass with `table=True` on a bare install: bare
  TypeError instead of "install reflex[db]" guidance.
- **FINDING-016** — `reflex.testing` (AppHarness) imports uvicorn/psutil the wheel does
  not declare (downstream test suites).
- **FINDING-017** — `compile_app()` discards user/app-level `bundle_library()`
  registrations; dynamic serializer never rewrites subpath imports (pre-existing).
- **FINDING-018** — failed `REFLEX_USE_NPM` run persists inconsistent `reflex.lock`
  (npm↔bun switch breaks subsequent runs).
- **FINDING-020** — `rx.plotly` silently drops `id=` (react-plotly.js wants `divId`).
- **FINDING-024** — reflex-base `CachedVarOperation.__getattr__` masks AttributeErrors
  from cached var computations as unchained `VarAttributeError: _cached_get_all_var_data
  not found` (this is what made the enterprise breakage nearly undiagnosable).
- Anomalies worth their own issues (recorded in cluster NOTES.md, not numbered findings):
  - `rx.script(id=...)` inside `App(head_components=...)` crashes compile (`components/`).
  - react-helmet `UNSAFE_componentWillMount` console error on pages with `rx.script`
    (`components/`).
  - Backgrounded/no-TTY `reflex run` ignores SIGTERM/SIGINT — needs SIGKILL of the process
    group (`up_upload_clock/`); granian also logs a spurious ERROR line on normal SIGTERM
    shutdown (`state_concurrency/`, `logging_cli/`).
  - A background handler that never enters `async with self` and then raises gets no
    compatibility delta flush (`state_concurrency/`).
  - Prod mode serves HTTP 404 status for direct loads of dynamic-route URLs (pre-existing;
    SPA-fallback body with 404 code) — document as known behavior or fix status code.

### reflex-dev/reflex-enterprise

- **Coordinated rxe release** adopting the RegistrationContext APIs (the #6967 shims are
  deprecated, removal 1.0): replace `dynamic.bundled_libraries` read (vars.py:143) and any
  `DECORATED_PAGES` uses; then verify ag_grid `/formatters` + flow demo against 0.9.9.
- **FINDING-025** — shipped ag_grid demo broken on reflex ≥ 0.9.8 regardless:
  `bundle_library('$/utils/components')` is a stale pre-0.9.8 memo path.
- **FINDING-026** — `HTTPCookie.sync()`: `/_reflex/cookies/sync` 404s (route registration
  never reaches the serving backend worker); broken on 0.9.8 too.
- **FINDING-029** — rxe error paths call deprecated `console.*` → DeprecationWarning noise
  on 0.9.9a1 (login gate, prod gate).
- ModelWrapper infinite-row endpoint 404 (`get_backend_url` percent-encodes `?`) — broken
  on 0.9.8 and 0.9.9a1 (`ent_aggrid/` NOTES).

## Suggested sequencing

1. Land #6967 and #6959 (in flight).
2. One PR: DECORATED_PAGES shim + `get_config(reload=)` handling + breaking-change notes
   (FINDING-023/008/009 docs) — same shape as #6967.
3. One PR: PEP 695 `TypeAliasType` resolution in `_isinstance` + `typehint_issubclass`
   (FINDING-002/006).
4. Two one-liners: upload sanitizer all-dots guard (007), `client_error` default arg (004).
5. Small PRs: react-router-dom guard (010), node-error SystemExit propagation (011),
   vite template options (012/015/019), warning-text escaping (027).
6. Decide FINDING-003 (background on_load cancellation): changelog note vs. behavior fix.
7. Decide FINDING-005 (full-logging worker handler): fix now or document limitation.
8. Cut next alpha; re-run `ent_aggrid`/`ent_misc` minimal triggers and the affected
   cluster drivers against it (repro commands in each NOTES.md).
9. File the post-release issue list above; coordinate the reflex-enterprise release.
