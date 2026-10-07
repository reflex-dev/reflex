# Release plan — what blocks 0.10.0 after the 2026-10-07 re-verification (train r/pre-2026.10.06-37579583012)

Written at 2026-10-07 ~14:00 UTC with one independent verification (N-032 / N-033) still running; its verdict is
folded in when it lands. Rubric (from the testing skill): fix before release = confirmed regression vs 0.9.12,
security-relevant, significant user impact, or trivially small. Each entry names the rubric arm that put it there.
Repros and evidence: [FINDINGS.md](./FINDINGS.md). The 10-06 plan is superseded by this one; items it listed that
the new train fixed (F-001 enterprise half, F-002, F-003, F-004, F-005, F-006) are not repeated.

## Already in flight

- **N-001** (HIGH, environment drift) — `reflex[db]` resolves SQLAlchemy 2.1.3 without greenlet; `rx.Model` and
  `reflex db *` crash on every fresh install, 0.9.12 included. Fix PR
  [reflex-dev/reflex#7466](https://github.com/reflex-dev/reflex/pull/7466) (`greenlet >=3.3` in the `db` extra) is
  green and waiting on review. Worth a 0.9.13 backport because stable users hit it today.

## Fix before release

### Confirmed regressions (vs 0.9.12 with the same enterprise wheel)

- **N-025** (HIGH, regression since a1, CONFIRMED) — prod, prerendered route: an enterprise AG Grid with Var-valued
  `column_defs` or `detail_cell_renderer_params` renders no columns on full load / reload; nothing is logged.
  Cause: #7064's boot delta carries only changed substates, so a component that reads `window.__reflex` at render
  time never re-renders (`reflex/state.py:2377` → `_diff_against_initial_state` `:2539`; `window.__reflex` is
  assigned in a `useEffect`, `reflex_base/compiler/templates.py:214`, unchanged since 0.9.12). Fix in reflex:
  make `window.__reflex` available before the first render in the default path, exactly as the lazy-libraries
  path already does (`templates.py:226-231`). Do **not** re-send every substate at boot (gives up #7064's gain and
  only hides the ordering). Separately, reflex-enterprise can drop the `typeof __reflex` guard in
  `formatColumnDefs` (`aggrid.py:2286-2290`) so already-shipped wheels stop depending on boot order. Regression
  arm + significant user impact (documented pattern, prod).
- **N-032** (HIGH, regression since a1, verification pending) — enterprise OIDC: logout in one tab leaves other
  tabs signed in; a tab booting with a stale `latest_access_token_hash_ls` is never corrected because the single
  `hydrate_and_load` bypasses `OIDCAuthState.get_delta` (`reflex/state.py` `_apply_client_storage_vars` →
  `_clean()` → `dict()`). Regression + security-relevant arm. Decision needed on the fix side (below): either
  reflex runs the client-storage reconciliation through `get_delta` (or an explicit hook) during boot, or
  enterprise moves its reconciliation off `get_delta`.
- **N-004** (MEDIUM, regression vs a1, CONFIRMED on 10-07) — state pickled by a2 is discarded by 0.9.12 and a1
  workers: a rolling deploy or a rollback silently resets every session. Regression arm. Fix: tolerate the
  schema-version mismatch (keep the old loader for one version) or document the rollback constraint loudly.
- **N-005** (MEDIUM, side effect of #7461, CONFIRMED on 10-07) — `cls.value = initial` on a LocalStorage/Cookie
  var (the documented ComponentState pattern) silently drops browser persistence. Regression arm for the
  documented pattern. Fix: preserve the `ClientStorageBase` wrapper when a plain default is assigned, or raise.
- **N-039** (MEDIUM, side effect of #7461, CONFIRMED) — `monkeypatch.setattr` / `mock.patch.object` of a State var
  default cannot be undone: teardown raises `TypeError: A Field cannot overwrite another field` and the patched
  default leaks into later tests (`reflex_base/vars/base.py:4764-4817` mutates the shared Field in place;
  `_accepts_default` 4676-4701 rejects re-assigning it). Low prevalence but loud and non-local. Fix: accept
  re-assignment of the class's own Field/Var object as a restore (copy the default back) and stop mutating the
  shared Field in place, or add a `BaseStateMeta.__delattr__` that restores the declared default. Trivially small
  arm.
- **N-008** (LOW, regression) — the dev `SetUndefinedStateVarError` guard now accepts any undeclared `_x__y` name
  (fallout of #7465's dunder rule). Trivially small: only exempt true dunders (`__x__`), not mangled names.

### Documentation to ship with 0.10.0 (trivially small)

- **N-024** — calling another handler as a method from a background task outside `async with self` now raises
  `ImmutableStateError`; `type(self)` is `StateProxy` inside. Add to the breaking-changes list.
- **N-002** — no changelog fragment for #7462 (sqlmodel cap lifted); a1 → a2 upgraders of naive-datetime apps
  silently change semantics. Add the fragment and the `UTCDateTime` note.
- **N-007 / N-009** — `State._x.default_value()` is not portable to 0.9.x and class-default assignment scope is
  undocumented; fold both into the 0.10 migration notes (recommend `ClassVar[...]` for shared objects, N-040).
- **N-006** — `BackendVarFormatError` should name the var and page and point at `default_value()` / `ClassVar`.

## File as issues, fix after release

### reflex
- N-020 (MEDIUM, since 0.9.0) raising foreground handler's state changes reach the page only with the next
  event, unbounded — `_handle_backend_exception` calls `chain_updates` without `root_state`
  (`reflex_base/event/processor/base_state_processor.py:569-590`).
- N-021 (MEDIUM) default-config Redis rolls back a failed/superseded event's already-delivered changes
  (`istate/manager/redis.py:535-537`); relates to upstream #6122 and #7248 / PR #7412. N-022 is the disk-side twin.
- N-017 (MEDIUM) `dict.values()`/`items()` mutations bypass dirty tracking (`istate/proxy.py` wraps only
  `get`/`setdefault`/`__getitem__`).
- N-015 / N-016 computed-var writes during events and uncached-var display after hydration (narrowed by a
  read-only control: not a general freshness problem).
- N-019 background completion after session expiry sends only the root delta.
- N-003 / N-041 AppHarness: same multi-module app cannot be restarted; a second app sharing a package's states
  loses its handlers.
- N-018 npm source-only reload reinstalls (`devDependencies: {}` vs absent key).
- N-023 UTF-16 string Var semantics; React #418 in prod on a split surrogate pair.
- N-028 `window.onerror` throws on error events without an Error object.
- N-043 Python 3.14 ignores `state_auto_setters` from rxconfig in the worker (deprecated option).
- Unchanged from 10-06: F-007 (npm SIGTERM hang, Linux only; macOS clean), F-008 (>1 MB storage reconnect storm),
  F-010 (pre-connect navigation on_load), F-011 (forward-ref `TypeError`), F-012 (bare `LookupError`), F-013
  (`rx.Model` deprecation location), F-014 (`reflex component` message gap), F-015 (duplicate npm notice),
  F-016 (ty arity), F-018 (React 19.3 console error on reflex-clerk), F-019 (stale frontend gets no signal).

### reflex-enterprise
- **N-033** (HIGH, pre-existing, verification pending) — prod + Redis + default granian workers: `POST
  /_reflex/cookies/sync` 405 on most workers (`auth/cookie.py` `ensure_handlers_registered` registers the route
  lazily per worker); token cookies lost in ~3/4 logins. Register the route at app construction. Worth fixing in
  the enterprise release that accompanies 0.10.0 because every multi-worker prod deployment hits it.
- N-034 background-task deltas on protected states withheld; N-035 JWKS not refreshed on key rotation;
  N-036 expired/revoked tokens keep authorizing (1800 s userinfo cache); N-037 scope-denied MCP handler returns
  success.
- N-027 `openapi.yaml` 500 without PyYAML (declare it or guard); N-029 malformed JSON → 500, handler errors → 200.
- N-026 React Flow controlled edits reverted by prod reload (mount-time `set_nodes` from prerendered defaults).
- N-030 SSRM/infinite filter placeholders and datetime add dialog; N-031 `autocomplete` has no `on_change`;
  N-038 maps `LayersControl` classes and `on_layeradd`.
- `formatColumnDefs` `typeof __reflex` guard (see N-025).

### third-party packages
- F-009 reflex-chat `initial_messages` cross-session leak (mutable `Field.default` list shared by every instance).
- reflex-clerk: `set_clerk_session` raises `TypeError: 'Field' object is not iterable` on 0.10 (class-level read
  of a backend var; needs the `default_value()` / `ClassVar` migration) — package is unusable in the browser on
  every version anyway (N-042, F-018).
- N-042 prod builds fail with reflex-monaco / reflex-webcam / reflex-clerk pages (old packages).

## Decisions needed from a maintainer

1. **Boot-sequence contract for third-party code (N-025, N-032).** #7064 changed two things downstream code relied
   on: every substate arriving in the first delta (so render-time readers of `window.__reflex` re-rendered) and
   the separate `update_vars_internal` / reconcile events (so `get_delta` overrides saw client-storage values).
   Decide whether reflex guarantees (a) `window.__reflex` before first render and (b) a boot-time hook for
   client-storage reconciliation, or whether enterprise/third-party code must stop depending on both. (a) is a
   small reflex change with no downside; (b) needs a design.
2. **Class-assignment semantics (N-005, N-039, N-040).** #7461 made class assignment update the Field default in
   place and reject Field/Var re-assignment. Decide whether patch/restore round trips are supported (recommended:
   accept the class's own Field/Var as a restore) and whether assigning a plain default to a client-storage var
   should keep or drop persistence.
3. **Rollback compatibility (N-004).** Whether 0.10.0 must read 0.9.12-pickled state (it does) *and* 0.9.12 must
   tolerate 0.10-pickled state (it does not). If not, document that a rollback resets sessions.
4. **N-033 severity** for the enterprise release: pre-existing, but it hits every multi-worker prod deployment.

## Suggested sequencing

1. Merge #7466 (N-001); consider the 0.9.13 backport.
2. Land the `window.__reflex`-before-first-render change (N-025) and re-run `ent_grid/verification` (one command
   per build in its NOTES.md); publish an enterprise wheel without the `formatColumnDefs` guard.
3. Decide and land the boot-time reconciliation for N-032 once its verification lands; re-run
   `ent_auth/scripts/stale_hash_probe.py` and `xtab_probe.py` (and the verifier's fixture).
4. N-004, N-005, N-039, N-008 and the documentation items, then cut 0.10.0a3 and re-run the 10-07 re-verification
   table (every cluster has rerun commands in its NOTES.md; the `board/` protocol lets several sessions share it).
5. File the "after release" lists as issues with the FINDINGS.md links.
