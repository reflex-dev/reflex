# Release plan — what blocks 0.10.0 after the 2026-10-07 re-verification (train r/pre-2026.10.06-37579583012)

Written at 2026-10-07 ~14:10 UTC after every cluster and all seven independent verifications completed. Rubric (from the testing skill): fix before release = confirmed regression vs 0.9.12,
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
- **N-032** (HIGH, regression since a1, CONFIRMED) — enterprise OIDC: logout in one tab leaves other tabs signed
  in (race-free form: log out in tab 2, press Back in tab 1 → still alice, 0/3 on a2 vs 3/3 on 0.9.12); a tab
  booting with a stale `latest_access_token_hash_ls` is never corrected because the single
  `hydrate_and_load` bypasses `OIDCAuthState.get_delta` (`reflex/state.py` `_apply_client_storage_vars` →
  `_clean()` → `dict()`). Regression + security-relevant arm. Decision needed on the fix side (below): either
  reflex runs the client-storage reconciliation through `get_delta` (or an explicit hook) during boot, or
  enterprise moves its reconciliation off `get_delta`.
- **N-004** (MEDIUM, regression vs a1, CONFIRMED on 10-07) — state pickled by a2 is discarded by 0.9.12 and a1
  workers: a rolling deploy or a rollback silently resets every session. Regression arm. Fix: tolerate the
  schema-version mismatch (keep the old loader for one version) or document the rollback constraint loudly.
  **Resolved 10-07 (maintainer decision):** declared a breaking change instead of a format fix: 0.9 and 0.10 instances
  cannot share a Redis or disk state store; 0.10 keeps loading 0.9 state. PR #7494 re-scoped to the `breaking` fragment
  plus a Self Hosting note (upgrade-guide section in #7496); issue #7470 closed as not planned.
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
- **N-033** (HIGH, pre-existing, CONFIRMED) — prod + Redis + default granian workers: `POST
  /_reflex/cookies/sync` 405 on every worker that has not yet built a sync (`auth/cookie.py:374-385`
  `ensure_handlers_registered` registers the route lazily per worker, only from `sync()`); ~100 % of logins lose
  their token cookies right after a start/deploy/respawn, and a second tab can then start an endless
  `update_vars_internal` → reconcile → 405 ping-pong (~115 POST/s). Register the route eagerly at app
  construction or in `AuthPlugin.post_compile`. Worth fixing in
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
   **Decided:** documented as a breaking change (#7494, #7496); no forward compatibility.
4. **N-033 severity** for the enterprise release: pre-existing, but it hits every multi-worker prod deployment.

## Suggested sequencing

1. Merge #7466 (N-001); consider the 0.9.13 backport.
2. Land the `window.__reflex`-before-first-render change (N-025) and re-run `ent_grid/verification` (one command
   per build in its NOTES.md); publish an enterprise wheel without the `formatColumnDefs` guard.
3. Decide and land the boot-time reconciliation for N-032; re-run `ent_auth/scripts/stale_hash_probe.py`,
   `xtab_probe.py` and the verifier's `ent_auth/verification/drivers/vdrv.py away|stale|xtab`.
4. N-004, N-005, N-039, N-008 and the documentation items, then cut 0.10.0a3 and re-run the 10-07 re-verification
   table (every cluster has rerun commands in its NOTES.md; the `board/` protocol lets several sessions share it).
5. File the "after release" lists as issues with the FINDINGS.md links.

## Issues filed (2026-10-07, after the campaign)

Fix-before-release items, assigned to @masenf, each with a fix branch in progress (worktrees from `main`):

| finding | issue | fix branch |
|---|---|---|
| N-025 | [reflex#7468](https://github.com/reflex-dev/reflex/issues/7468) | `claude/n025-reflex-before-render` — PR #7492 **closed by the maintainer** (16:40 UTC): fixed on the enterprise side instead, [reflex-enterprise#273](https://github.com/reflex-dev/reflex-enterprise/pull/273), because moving `window.__reflex` out of the useEffect would negate that change's benefits |
| N-032 | [reflex#7469](https://github.com/reflex-dev/reflex/issues/7469) | `claude/n032-boot-reconcile` — PR #7493 **merged** 2026-10-07 17:57 UTC |
| N-004 | [reflex#7470](https://github.com/reflex-dev/reflex/issues/7470) (closed, not planned) | `claude/n004-pickle-compat` — PR #7494 **re-scoped by the maintainer** to a breaking-change declaration (fragment + Self Hosting note), pickle-format change reverted |
| N-005 | [reflex#7471](https://github.com/reflex-dev/reflex/issues/7471) | `claude/class-assignment` |
| N-039 | [reflex#7472](https://github.com/reflex-dev/reflex/issues/7472) | `claude/class-assignment` |
| N-008 | [reflex#7473](https://github.com/reflex-dev/reflex/issues/7473) | `claude/class-assignment` |
| docs (N-002, N-007, N-009, N-024, N-040) | [reflex#7474](https://github.com/reflex-dev/reflex/issues/7474) | `claude/docs-0.10-migration` |
| N-006 | [reflex#7475](https://github.com/reflex-dev/reflex/issues/7475) | `claude/docs-0.10-migration` |
| N-001 | PR [reflex#7466](https://github.com/reflex-dev/reflex/pull/7466) | `claude/db-extra-greenlet` — **merged** 2026-10-07 18:01 UTC |

All five fix branches are pushed and have pull requests (label `on deck`, milestone v0.10.x): [#7492](https://github.com/reflex-dev/reflex/pull/7492) N-025, [#7493](https://github.com/reflex-dev/reflex/pull/7493) N-032, [#7494](https://github.com/reflex-dev/reflex/pull/7494) N-004, [#7495](https://github.com/reflex-dev/reflex/pull/7495) class assignment, [#7496](https://github.com/reflex-dev/reflex/pull/7496) docs: `claude/n025-reflex-before-render` 655b22259 (window.__reflex at
module scope; compiler unit test + Playwright test; verifier fixtures: probe NO_REFLEX→HAS_REFLEX, enterprise grid 0→2 headers),
`claude/n032-boot-reconcile` 33568493e (client-storage vars applied at boot are re-marked dirty after the guarded snapshot so the
event delta goes through `get_delta`; verifier fixtures: `away` 0/3→3/3 dev and prod, stale-hash probes 3/3), `claude/n004-pickle-compat`
2f241fa4e (re-scoped 10-07: the 378d403b7 pickle-compat change is reverted; a `breaking` fragment and a Self Hosting note declare that
0.9 and 0.10 instances cannot share a state store; `__getstate__` no longer writes the `_PREVIOUS_RELEASE_PICKLE_KEYS` entries for 0.9
workers, the `__setstate__` upgrade path stays; new issue #7491 for the Python-version hash dependence), `claude/class-assignment`
5cfb3d20f + 347d0456c + b57fd27fc + c7e62437d + 2e1b0ea79 + b05799207 (patch/restore round trip, storage wrapper kept on plain-default
assignment including a declared `default_factory` producing storage, mangled-name guard reusing `_private_prefixes`; review follow-ups
filed as #7498 (str-annotated factory field never detected as storage) and #7499 (storage-annotated var logs a type error on hydration)), `claude/docs-0.10-migration` 8c725dcde + 12f54a690 +
e46344d84 (`BackendVarFormatError` hint, #7462 fragment, "Upgrading to Reflex 0.10" guide). Each worktree ran ruff, pyright, the unit
suite (the only failures are the 232 reflex_cli version-check tests that fail on unmodified main in a shallow checkout) and the relevant
Playwright tests; the Selenium `test_client_storage.py` could not run here (no matching Chrome) and should be watched in CI for N-032.

Filed for after the release — reflex: N-020 [#7476](https://github.com/reflex-dev/reflex/issues/7476), N-017 [#7477](https://github.com/reflex-dev/reflex/issues/7477),
N-019 [#7478](https://github.com/reflex-dev/reflex/issues/7478), N-003/N-041 [#7479](https://github.com/reflex-dev/reflex/issues/7479),
N-018 [#7480](https://github.com/reflex-dev/reflex/issues/7480), N-023 [#7481](https://github.com/reflex-dev/reflex/issues/7481),
N-028 [#7482](https://github.com/reflex-dev/reflex/issues/7482), N-043 [#7483](https://github.com/reflex-dev/reflex/issues/7483),
N-015 [#7484](https://github.com/reflex-dev/reflex/issues/7484), F-007 [#7485](https://github.com/reflex-dev/reflex/issues/7485),
F-008 [#7486](https://github.com/reflex-dev/reflex/issues/7486), F-010 [#7487](https://github.com/reflex-dev/reflex/issues/7487),
F-011 [#7488](https://github.com/reflex-dev/reflex/issues/7488), F-012 [#7489](https://github.com/reflex-dev/reflex/issues/7489),
F-014 [#7490](https://github.com/reflex-dev/reflex/issues/7490); N-021/N-022 added as a comment on the existing
[#6122](https://github.com/reflex-dev/reflex/issues/6122#issuecomment-6040383717) (see also #7248 / PR #7412).
Not filed: N-016 (tracked by the existing #7253), F-019 (existing #5534 / #5394), F-013 / F-015 / F-016 (cosmetic),
F-018 (reflex-clerk only), N-040 (folded into #7474).
reflex-enterprise: N-025 enterprise side [#260](https://github.com/reflex-dev/reflex-enterprise/issues/260) and N-032 enterprise side
[#261](https://github.com/reflex-dev/reflex-enterprise/issues/261) (both assigned to @masenf), N-033 [#262](https://github.com/reflex-dev/reflex-enterprise/issues/262),
N-034 [#263](https://github.com/reflex-dev/reflex-enterprise/issues/263), N-035 [#264](https://github.com/reflex-dev/reflex-enterprise/issues/264),
N-036 [#265](https://github.com/reflex-dev/reflex-enterprise/issues/265), N-037 [#266](https://github.com/reflex-dev/reflex-enterprise/issues/266),
N-027 [#267](https://github.com/reflex-dev/reflex-enterprise/issues/267), N-029 [#268](https://github.com/reflex-dev/reflex-enterprise/issues/268),
N-026 [#269](https://github.com/reflex-dev/reflex-enterprise/issues/269), N-030 [#270](https://github.com/reflex-dev/reflex-enterprise/issues/270),
N-031 [#271](https://github.com/reflex-dev/reflex-enterprise/issues/271), N-038 [#272](https://github.com/reflex-dev/reflex-enterprise/issues/272).
reflex-chat: F-009 [#61](https://github.com/reflex-dev/reflex-chat/issues/61). Not filed (no access to the repos): reflex-clerk `set_clerk_session` Field TypeError, N-042 (monaco /
webcam / clerk prod builds).
