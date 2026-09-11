# Release plan — what blocks reflex 0.9.11a1 vs what gets filed

Triage of [FINDINGS.md](./FINDINGS.md) against the campaign rubric: fix before release if a finding
is (a) a confirmed regression against the previous stable, (b) security-relevant, or (c) high impact
or trivially small to fix. Everything else is filed and fixed after.

**Status: DRAFT — the campaign is still running.** Clusters completed at the time of writing:
smoke, packaging, hmr_runtime, hybrid_property, bg_rehydrate, event_hotpath, up_counter_todo_clock,
up_upload_traversal_quiz, ent_aggrid, ent_map_dnd_flow, orch_probes. Still outstanding:
otel (running), components_bumps, ent_mcp_oidc, config_assets_cli, memo_hash, reverify_prev,
ent_mantine_highcharts_tickets and four more reflex-examples apps.

## Bottom line so far

**Nothing found so far blocks the release.** Across eleven clusters the only confirmed regression is
one low-severity downstream behaviour change (FINDING-002), and every headline item of this train
that has been exercised works as its changelog describes, with the previous stable reproducing the
bug it claims to fix. The enterprise surface — the thing that blocked 0.9.9 — is clean: ag-grid, map,
dnd and flow all behave identically on 0.9.11a1 and 0.9.10.post2, and all four 0.9.9a1 enterprise
breakages are fixed.

## Fix before release

### Confirmed regressions
- **FINDING-002 — `rx.moment` `on_change` now fires at mount** (low, downstream,
  reflex-components-moment 0.9.4a1). The only confirmed regression in the campaign. The fix is a
  documentation decision rather than code: upstream react-moment lists this as a breaking change,
  while the 0.9.4a1 changelog files the migration under Bug Fixes with no behaviour note, and
  `docs/library/data-display/moment.md` still describes 1.2.2 semantics. Either add a behaviour note
  (changelog + docs) or restore the old semantics with a guard in the wrapper. Small either way.

### High impact and/or trivially small
- *(none identified so far — the high-severity findings below are all pre-existing, and the
  campaign's remaining clusters have not reported)*

## File as issues, fix after release

### reflex / reflex-base (this repo)
| # | Finding | Severity | Note |
|---|---|---|---|
| 003 | Prod multi-worker + redis drops backend-initiated deltas | high | Pre-existing; verified 4/6 delivered with 9 workers, 6/6 with one, 0/6 on 0.9.10.post2. Swallows this train's #7073 hydrate, so it devalues a shipped fix. Best candidate for the next release. |
| 018 | One unserializable state var drops the whole hydrate delta in dev | high | Pre-existing; reproduced in a 40-line app with no enterprise components. Blast radius is the issue: whole delta lost, state silently reverts, internal error text shown to end users. |
| 025 | `rx.AdminDash` serves 500 on every `/admin` route | medium-high | Pre-existing on both versions and every starlette-admin generation; isolated to reflex's mount, not starlette or starlette-admin. See "Decisions needed". |
| 022 | Module-scope `bundle_library()` discarded before page evaluation | medium | Three clusters found it independently. The error message tells the user to do what they already did. |
| 023 | Hook-bearing component in `rx.foreach` compiles then blanks the page | medium | Silent compile, `ReferenceError` at runtime. A compile-time diagnostic would be enough. |
| 008 | `reflex run --backend-only` leaks `.web/nocompile` | medium | Next full run silently serves a stale frontend. |
| 009 | `frontend_path` mis-routes routes whose name starts with the prefix | medium | `removeprefix` applied twice. |
| 010 | Backend var named `_get_was_touched` breaks the disk state manager | medium | State silently never persists; the PR's own test uses this name as a supported collision. |
| 013 | AttributeError in a cached var computation masked as a bogus `VarAttributeError` | medium | This is what made the 0.9.9a1 enterprise breakage undebuggable. |
| 005 | `hybrid_property` class-level typing degrades to `Any` on pyright 1.1.412+ | medium | Works at the repo-pinned 1.1.411. Forward-compat, see "Decisions needed". |
| 004 | Client-storage vars show defaults after a backend rehydrate | medium | Until a full reload. |
| 011 | State attribute names colliding with framework internals are unvalidated | low | Some crash with `'int' object is not callable`. |
| 012 | `rx.Model(table=True)` without sqlmodel gives a bare TypeError | low | No `reflex[db]` pointer. |
| 014 | `frontend_path` validation accepts Win32-trimmed segments | low | Gap in the new #7044 guard. |
| 015 | `reflex cloud regions/vmtypes --json` exit 0 after a 403 | low | Undercuts #6917's agent-usability goal. |
| 016 | `reflex run --json` stdout is not strict JSON-lines | low | Nine granian lines; `reflex cloud --json` is already clean. |
| 017 | `rx.plotly` emits `id` rather than `divId` | low | The id never reaches the DOM. |
| 021 | One `REFLEX_USE_NPM=1` run converts a project to npm permanently | low | Silent and undocumented; deleting the npm lockfile is the remedy. |
| 024 | Error boundary logs three invalid-DOM-property errors | low | Above the real exception, on every crash page. |
| 006 | uv cannot build the `reflex` sdist | low | Monorepo `[tool.uv.sources]` ships in the sdist; pip builds it fine. |

### reflex-enterprise (downstream tracker)
- **FINDING-019**: four defects in reflex-enterprise 0.9.5 that break its own demos — the stale
  bundle path that stops the ag_grid demo starting unpatched, the `ModelWrapper` datasource URL that
  percent-encodes its query separator, the ag-grid/ag-charts version mismatch that blocks integrated
  charts, and `column_def()` silently dropping unknown kwargs (which is why `ag_grid_finance` has no
  selectable rows). Also the still-unfixed use of deprecated `console.*` helpers on both licence
  gates, so a blocked user's last line is a framework DeprecationWarning.

### Release process
- **FINDING-001**: `reflex-otel 0.1.0a1` failed to publish from the release run (PyPI trusted
  publisher not configured for a brand-new project) and was published manually 17 minutes later.
  Add the pending-publisher step to the new-package checklist so the next new package does not
  repeat it.

## Decisions needed from a maintainer

1. **The AdminDash changelog entry (FINDING-025).** This train says "AdminDash now works with
   starlette-admin 1.0". The argument rename it describes is handled, but `/admin` returns 500 on
   every route, on both reflex versions and on starlette-admin 0.17.1, 1.0.0 and 1.0.1, while the
   same admin mounted on a plain Starlette app works. Either the entry needs qualifying before
   release or `/admin` needs fixing.
2. **The `rx.moment` behaviour change (FINDING-002).** Bug fix or breaking change? Upstream calls it
   breaking; our changelog does not mention the behaviour at all.
3. **The `hybrid_property` typing promise (FINDING-005).** The changelog states the class-level type
   resolves to the frontend var. True on pyright 1.1.411, `Any` from 1.1.412 onward — i.e. for every
   user who does not pin the repo's checker. Fix the overloads or qualify the claim.
4. **Enterprise prod coverage.** `reflex run --env prod` and `reflex export` could not be exercised
   for any enterprise demo: reflex-enterprise gates them behind a paid subscription that `CI=1` does
   not bypass, and the agents declined to set the app-harness flag purely to get past a licence
   check. If enterprise prod mode should be covered by this campaign, the team needs to supply a
   test licence or a sanctioned bypass.

## Suggested sequencing

1. Before release: decide (1)-(3) above; the only code change any of them might need is small.
2. First post-release batch, in this order: FINDING-003 (devalues a shipped fix), FINDING-018
   (silent state loss with a user-visible internal error), FINDING-022 and FINDING-013 (both make
   other failures hard to diagnose), FINDING-025.
3. Then the rest of the medium list, which is mostly independent and parallelisable.
4. File FINDING-019 downstream, ideally alongside the reflex-enterprise release that follows.
