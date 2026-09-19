# Release plan — what blocks reflex 0.9.12a1 → 0.9.12 vs what gets filed

**Status: IN PROGRESS** — updated as clusters and verifiers finish. Rubric (from the campaign playbook):
fix before release = confirmed regression vs 0.9.11.post1, OR security-relevant, OR significant user
impact / trivially small. Everything else is filed as an issue and fixed after. Each entry names the
arm of the rubric that put it there, so a maintainer can disagree with a specific judgment.

## Already in flight (open PRs on reflex-dev/reflex as of 2026-09-19 02:05 UTC)

| PR | Covers | Gap check |
|---|---|---|
| [#6996](https://github.com/reflex-dev/reflex/pull/6996) SPA fallback 200 for routable paths in prod static serving (closes #6983) | the `router_vars` prod anomaly: a direct load of a dynamic route returns 404 with the SPA body before rendering — so that anomaly is **pre-existing**, not #7068's | does not touch the trailing-slash rewrite (`/search?q=` → `/search/?q=`) the same anomaly noted; `build_prod_export` is baselining both |
| [#7206](https://github.com/reflex-dev/reflex/pull/7206) Reject inherited state var shadowing through mixins (closes #7190) | extends #7077's guard to `mixin=True` states | does **not** cover backend (underscore) vars — FINDING-006 stays open |
| [#7144](https://github.com/reflex-dev/reflex/pull/7144) preserve preloaded rxconfig classes | follow-up to #7075 (rxconfig reload keeps project modules) | `dev_server_cli` tests the published #7075 behavior; no finding yet |
| [#7138](https://github.com/reflex-dev/reflex/pull/7138) migrate all time env vars to timedelta | builds on #7131's `EnvVar` timedelta parsing | `vars_typing` tests the published parser; no finding yet |
| [#6757](https://github.com/reflex-dev/reflex/pull/6757) fast-path framework bookkeeping fields | touches `_FRAMEWORK_ATTR_NAMES`, the same list #7136 reserves | nothing for FINDING-001: no open PR changes the `_StateMeta` metaclass |
| [#7207](https://github.com/reflex-dev/reflex/pull/7207) move reflex-hosting-cli onto reflex-build-sdk | future coupling of the two packages probed in `orch_probes` | n/a for this train |

No open PR addresses FINDING-001, -003, -004 or -007.

## Fix before release

### Security

- **FINDING-011 — reflex-enterprise's REST `redact_router_session()` is a no-op against reflex 0.9.12a1's split
  router vars; server-generated `client_token`/`session_id` reach REST responses and event deltas** (HIGH, claimed
  by `ent_map_dnd_flow_mantine`, verification pending; currently masked by FINDING-001 because the app cannot
  start). Arm: security-relevant. Shape: decide where the redaction lives — reflex could expose the
  connection-scoped vars under a stable name the plugin can redact, or a lockstep reflex-enterprise release
  redacts `rx_router_session` — and re-verify over HTTP (`retrieve_state`, `/_reflex/event/...`) on the next alpha.

### Confirmed regressions

- **FINDING-001 — `rx.State`'s new metaclass breaks downstream `BaseStateMeta` subclasses; reflex-enterprise
  0.9.5 AuthPlugin and MCPPlugin apps cannot start on 0.9.12a1** (CRITICAL). Arm: confirmed regression
  (import sweep + framework-only repro on both versions; blast radius measured end to end by `ent_mcp_oidc`).
  Also kills the `tickets` demo (no auth configured) through `EventHandlerAPIPlugin.post_compile`.
  Shape of the fix, framework side: keep `type(rx.State) is reflex.vars.BaseStateMeta` — run #7136's
  `_validate_state_name`/`_validate_inherited_members` from `BaseStateMeta.__new__` (guarded on "a base is a
  `BaseState`") instead of introducing `reflex.istate.validation._StateMeta`; or make `_StateMeta` compose
  with sibling `BaseStateMeta` subclasses (e.g. resolve the most-derived metaclass dynamically in
  `BaseState.__init_subclass__`). Regression test: `class M(BaseStateMeta)` + `class S(rx.State, mixin=True,
  metaclass=M)` must construct (`orch_probes/metaclass_probe.py`). Add a changelog note either way. A
  lockstep reflex-enterprise release switching to `class OIDCCookieMeta(type(rx.State))` is the downstream
  half, but it does not rescue the already-published 0.9.5 against a released 0.9.12.

- **FINDING-003 — a `@rx.var(cache=False)` withheld from the delivered delta is never re-sent** (HIGH,
  regression; confirmed independently by `ent_mcp_oidc` through enterprise auth and by `event_loop` in pure reflex,
  dev and prod+redis). Arm: confirmed regression. Shape: record the "last sent" key after the delta has been
  filtered/emitted (or expose `_suppress_delta_recording()` / a post-filter hook to `get_delta` overrides), not
  while building it in `BaseState.get_delta` (`reflex/state.py` ~2385 → `ComputedVar._record_delta_value`,
  `reflex_base/vars/base.py:2689`). Regression test: `event_loop/scripts/s_filtered.py` against `elapp`.

### Trivially small / significant impact

- **FINDING-015 — #7156's advertised scenario (toast action / `call_script` callback triggering an upload handler)
  still throws `ReferenceError: filesById is not defined`** (HIGH for the scenario, pre-existing; `event_loop`,
  verification pending). Arm: significant impact on a change this release announces as fixed. Shape: propagate the
  `UploadFilesContext` hook/VarData to callback sites, or at minimum reword the #7156 changelog and the toast docs
  so nobody ships `action=` + `rx.upload_files`.

- **FINDING-012 — `rx.data_editor`'s image-preview overlay (the #7081 headline) cannot open in prod while the
  default "Built with Reflex" badge is on; the badge app-wrap swallows the `#portal` div** (HIGH impact,
  pre-existing nesting; `components_bumps`, verification pending). Arm: significant user impact on a feature this
  release advertises, and the fix (forward children in the StickyBadge wrap / keep the portal a sibling) is
  small. Minimum: document `show_built_with_reflex=False` for image cells until fixed.

- **FINDING-004 — `deps=["router"]` deprecation warning is dead code** (LOW, `router_vars`, pending
  verification). Arm: trivially small — the changelog promises the warning; the guard at
  `reflex/state.py:1205-1219` can never be true. Either emit the warning from where the string dep is
  resolved, or drop the deprecation line from the changelog.

## File as issues, fix after release

### reflex-dev/reflex

- FINDING-016 — cancelled foreground `supersedes=True` handler loses pre-cancellation writes under redis (prod)
  while dev/memory keeps them; needs a 0.9.11.post1+redis baseline before triage (`event_loop`).
- `on_load`-started self-chaining loops keep running after the client disconnects, logging one
  "Attempting to send delta to disconnected client" warning per tick (pre-existing family, `event_loop`).
- #6946 polish: every uncached var is re-sent once right after hydrate; dict key order defeats the dedupe; the
  `_UNKEYABLE_VALUE` branch is unreachable (`event_loop`).
- Missing app-package `__init__.py` → silent frontend/backend state-name mismatch, every event a no-op, only a browser
  console error (`vars_typing`; pre-existing; `reflex init` skips the file when the app dir exists).
- `rx.Var.create(x)._replace(_var_data=...)` raises `TypeError` on both versions (`vars_typing`; pre-existing).
- FINDING-013 — `rx.vars.use_id()` in an `rx.foreach` body yields one id for every item (new API, #6708):
  either derive a per-iteration id or document that `use_id` is per compiled component (`components_bumps`).
- FINDING-014 — #7124 changelog: the `reflex.components.datadisplay.code` path only works as a module import,
  not `from reflex.components.datadisplay import code` (`components_bumps`).
- `Axis.tick_formatter` accepts only a literal JS string; a `FunctionStringVar` raises `TypeError` (pre-existing,
  `components_bumps`).
- FINDING-005 — computed vars reading `self.router` depend on all five router fields; narrow `deps=` cannot
  narrow; navigation delta −47% measured vs −67% claimed (LOW, perf gap, `router_vars`).
- FINDING-006 — backend (underscore) var shadowing across substates still silently ignored (LOW,
  pre-existing gap in #7077's scope, `router_vars`).
- Pre-existing, re-observed: `uv pip install reflex-<ver>.tar.gz` fails on the workspace `tool.uv.sources`
  (issue #7088); `reflex run` keeps running and prints "Backend running at …" after the app module raised at
  import (both versions; makes FINDING-001 look like a hang).

### reflex-dev/reflex-enterprise

- Switch `OIDCCookieMeta` to derive from `type(rx.State)` (forward-compatible on both versions) and stop
  importing the OIDC state module from `MCPPlugin.post_compile`'s exemption check when `AuthPlugin` is not
  configured (would have kept MCP-only apps alive). `_override_base_method` is a private reflex helper the
  wheel depends on.
- `/_reflex/cookies/sync` answers 405 (new) / 404 (prev) with two `net::ERR_ABORTED` per browser run
  (pre-existing, previous campaign).
- Re-confirmed on 0.9.12a1 by `ent_aggrid` (all pre-existing, previous campaign's FINDING-019): `demos/ag_grid`
  stale `$/utils/components` bundle path; ModelWrapper `get_backend_url()` percent-encodes `?` so `/model*`
  datasource fetches 404; ag-grid 34.3.1 pinned with ag-charts 11.2.4 (integrated charts unusable);
  `ag_grid.column_def(**kwargs)` silently drops unknown kwargs (`checkbox_selection` → no row selection in
  `ag_grid_finance`).

## Decisions needed from a maintainer

- FINDING-002 — the #7132 changelog entry ("keep saving state … when a state defines a var named
  `_get_was_touched`") describes behavior #7136 made unreachable: the declaration now raises
  `StateValueError`. Reword/drop the entry, or fold it into #7136's breaking note.
- FINDING-007 — PR #7136's description promises `REFLEX_STATE_ALLOW_RESERVED_NAMES=1` as a temporary escape
  hatch; nothing in the published packages reads it. Ship the flag or correct the migration text.
- #7077 ships a hard `BaseVarShadowsInheritedVarError` (the PR discussion considered a warning). Intended?
  Apps that silently redeclared an inherited var on 0.9.11.post1 now fail at import with no opt-out.
- #7115 also changes `hasattr`/`getattr(var, name, default)` on a var whose computation is broken from returning
  False/the default to raising `ReflexRuntimeError` (PR body only) — add to the changelog or not? (`vars_typing`)
- #7131's changelog line reads as if an existing env var changed; nothing shipped uses `EnvVar[timedelta]` yet
  (#7138 is the follow-up). Consider rewording. (`vars_typing`)
- The metaclass change itself (FINDING-001) is unannounced; if it is kept, it needs a Breaking Changes
  entry naming `BaseStateMeta` and the `type(rx.State)` spelling.

## Suggested sequencing

1. FINDING-001 framework fix first (one PR, regression test from `orch_probes/metaclass_probe.py`), then
   re-run `orch_probes/ent_import_probe.py` and the `ent_mcp_oidc` harness without the shim.
2. FINDING-003 once the `event_loop` verifier reports (independent files: `reflex/state.py` delta path vs
   `reflex/istate/validation.py`, so it can land in parallel with 1).
3. FINDING-004 and the changelog decisions (002, 007, metaclass note) can ride one docs/changelog PR.
