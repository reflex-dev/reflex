# Release plan — what blocks 0.10.0 (from the 2026-10-06 gap validation) vs what gets filed

Interim plan, written at the pause point (2026-10-06 21:45 UTC) before the next round of pre-releases.
Rubric (from the testing skill): fix before release = confirmed regression vs 0.9.12, security-relevant,
significant user impact, or trivially small to fix. Each entry names the rubric arm that put it there.
See [FINDINGS.md](./FINDINGS.md) for repros and evidence; the previous campaign's open items (enterprise
#245 security hold, etc.) are tracked in [../2026-10-05/FINDINGS.md](../2026-10-05/FINDINGS.md) and are not repeated here.

## Already in flight

None known for these findings. (reflex-enterprise 0.9.7a3/a4 already shipped `_compat` shims and
`ClassVar` statics for the class-level backend-var change, but missed `__data_source_params_class__`.)

## Fix before release

### Confirmed regressions
- **FINDING-001** (HIGH) — class-level read of a backend State var returns the `Field` descriptor
  (`reflex_base/vars/base.py:4273-4274`, `:4737-4738`). Regression arm, plus downstream impact: the published
  reflex-enterprise 0.9.7a4 AG Grid **model wrapper** fails every data request on 0.10.0a1
  (`reflex_enterprise/components/ag_grid/wrapper.py:153`). Shape of the fix: make class access of a backend
  field return `default_value()` (optionally with a deprecation warning) — or, if the new behavior is intended,
  document it as a breaking change with the `ClassVar` migration AND ship an enterprise fix for
  `__data_source_params_class__` (and audit enterprise for other class-level reads) before 0.10.0.
  FINDING-004 (class-level assignment replaces the descriptor; `BaseStateMeta` has no `__setattr__`) is the
  write-side of the same change and should be decided together (update the Field default, or raise clearly).
- **FINDING-002** (HIGH) — first page load writes client-storage defaults into the browser
  (`reflex/state.py:2497-2509` drops root `is_hydrated_rx_state_` from the diffed boot delta;
  `state.js:1045-1090` then writes storage). Regression arm; user-visible (stale defaults for returning
  visitors, cookies set without user action, values persist even after a fix). Trivially small: keep
  `is_hydrated_rx_state_: false` in the root of the diffed boot delta (or skip storage writes for the boot delta).
- **FINDING-003** (MEDIUM) — client-storage value rewritten by a computed var during hydration never reaches
  the browser (`hydrate_and_load` snapshots, then `_clean()`s; `dict()` reads base vars before computed vars).
  Partial regression arm (alpha makes a seed-dependent 0.9.12 failure deterministic) and it breaks a published
  package (reflex-google-auth token cleanup). Fix with FINDING-002: flush vars dirtied during `dict()` in a
  follow-up delta that is not marked not-hydrated, or decide and document that computed vars must not write state.
- **FINDING-005** (MEDIUM) — `sqlmodel<0.0.45` cap (`pyproject.toml` `[db]` extra, #7424). Regression arm for
  every `reflex[db]==0.9.12` environment resolved fresh after 2026-09-21 (0.9.12-generated migrations reference
  `sqlmodel.sql.sqltypes.UTCDateTime()` and fail on a fresh database; `AwareDatetime`/`NaiveDatetime` fields
  stop importing; datetime reads flip aware→naive on SQLite). Either lift the cap and handle `UTCDateTime`
  compatibility, or keep it and (a) re-file the fragment as **breaking**, (b) correct "preserves existing
  datetime storage behavior", (c) publish the migration recipe (replace `UTCDateTime()` with
  `sa.DateTime(timezone=True)`; `sa_type=` for Aware/Naive fields; or drop `[db]` and pin sqlmodel directly).

### High impact and/or trivially small
- **FINDING-011** (LOW, regression) — forward-reference annotation error became a cryptic `ForwardRef`
  TypeError; small: let the `NameError` surface (or name the state and field) in `resolve_annotations`.
- **FINDING-012** (LOW) — re-raise `LookupError` from `BaseContext.get()` with the old friendly sentence (one line).
- **FINDING-013** (LOW) — add pydantic/sqlmodel to `_exclude_paths_from_frame_info` so the `rx.Model`
  deprecation warning names the user's file, as #7138 promises (one line).
- **FINDING-014** (LOW) — make `reflex component ...` print the migration pointer (component template / wrapping
  docs) instead of click's generic "Did you mean 'compile'?" (a few lines).

## File as issues, fix after release

### reflex
- FINDING-007 — `reflex run` under npm hangs on SIGTERM without a TTY (pre-existing; #7328's claim does not
  hold on the npm path that #7093 now auto-selects). Verify, then fix the npm process-group handling.
- FINDING-008 — >1 MB client-storage value → endless reconnect storm with no backoff and no UI error (pre-existing).
- FINDING-010 — pre-connect navigation runs the left page's on_load (pre-existing race; a function-valued
  socket.io `auth` plus dropping the queued navigation `on_load_internal` before the first connect).
- FINDING-015 — duplicate "Preferring npm" notice.
- FINDING-016 — ty 0-arg handler as `Callable[[], Any]`; 5-arg fully applied calls under pyright and ty
  (`EventCallback.__call__` overloads stop at four).
- FINDING-017 — Redis prod restart token loss after a granian/pyo3 shutdown panic (1/9; needs a reproduction).
- FINDING-018 — React 19.3 "script tag while rendering" console error when a route module fails to load.
- FINDING-019 — no user-visible signal for a stale frontend after an upgrade (pre-existing).
- FINDING-020 — not actionable (worker forked from the old process); at most a "restart the server" hint.
- Partial-cluster leads to confirm first (see FINDINGS.md "Partial clusters"): data editors inside
  `rx.foreach` rendering nothing; dropped characters on the first fast cell edit; `rx.select` value absent from
  the #7227 form payload and a dialog form submit reaching the outer form; a cancelled superseded handler's
  unflushed mutation becoming visible; a handler returning a nested event list raising `TypeError`; the
  chained-handler-raise partial delta arriving with the next event.

### reflex-enterprise
- FINDING-001's enterprise half — `ag_grid/wrapper.py:153` class-level read (blocking above; the fix lands in
  enterprise if core keeps the new semantics).
- Partial-cluster leads: SSRM/infinite datasource filter count mismatches and the "add dialog" not inserting
  (also seen on the mixed graph, so probably pre-existing or a driver assumption); prod-only
  master-detail/clipboard/memo-grid-from-foreach failures (unverified, possibly timing under load).

### third-party packages
- FINDING-009 — reflex-chat mutable `initial_messages` default shared across sessions (package bug; framework
  question whether mutable defaults should be copied per session).
- reflex-clerk / reflex-dynoselect: already broken on 0.9.12 for other reasons; FINDING-001/004 add new
  failure modes (`ClassVar` migration).

## Decisions needed from a maintainer

1. Is class-level access of a backend var returning the `Field` the intended design of #7312? Nothing documents
   it, and enterprise had to ship a private shim. If intended: breaking-change entry + `ClassVar` guidance +
   enterprise fix; if not: FINDING-001/004 are bugs.
2. The `sqlmodel<0.0.45` cap: lift, or keep as a documented breaking change with a recipe (FINDING-005)?
3. Component package floors (FINDING-006): reflex 0.10.0a1 still floors components at 0.9.x, so
   `pip install -U reflex` (and any in-place upgrade) never pulls the component fixes that reflex's own changelog
   advertises (#7227, #6675, #7226, #7366, react-dropzone 17). Raise the floors (the repo's sibling-floor rule
   would say `>=0.10.0.dev0`) or move those changelog entries and document `reflex[all]`-style upgrades.
4. Are computed vars allowed to write state (FINDING-003)? The docs are silent, a published package relies on it,
   and 0.9.12 honored it on roughly half of all hash seeds.
5. #7328's SIGTERM promise vs the npm path (FINDING-007): in scope for 0.10.0 or a follow-up?

## Suggested sequencing

1. Decide (1) and land FINDING-001/004 together (core and/or enterprise); re-run
   `thirdparty/verification/classattr/` and the enterprise `ag_grid` demo `/model` page.
2. Land FINDING-002 and FINDING-003 together in `hydrate_and_load`/`_diff_against_initial_state` + `state.js`
   (same files; one PR); re-run `hydration/verification/f1-client-storage-defaults/` and
   `thirdparty/verification/clientstorage-hydrate/`.
3. Decide (2) and (3); they are metadata/changelog-only and can land in parallel with 1–2.
4. The four small polish items (FINDING-011..014) can land in parallel, each independent.
5. Re-verify on the next alpha: every repro named above plus a stock-install smoke, then finish the four
   interrupted clusters and `statemgr_perf`.
