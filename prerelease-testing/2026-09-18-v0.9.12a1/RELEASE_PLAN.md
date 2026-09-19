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
  router vars; server-generated `client_token`/`session_id` reach REST responses and event deltas** (HIGH,
  `ent_map_dnd_flow_mantine`, CONFIRMED in-process and over HTTP with the FINDING-001 metaclass shimmed —
  `verification/v_leak_http.py`). Arm: security-relevant. As soon as FINDING-001 is fixed this leak is live against
  the published rxe 0.9.5. Shape: decide where the redaction lives — reflex could expose the
  connection-scoped vars under a stable name the plugin can redact, or a lockstep reflex-enterprise release
  redacts `rx_router_session` — and re-verify over HTTP (`retrieve_state`, `/_reflex/event/...`) on the next alpha.

### Confirmed regressions

- **FINDING-001 — `rx.State`'s new metaclass breaks downstream `BaseStateMeta` subclasses; reflex-enterprise
  0.9.5 AuthPlugin and MCPPlugin apps cannot start on 0.9.12a1** (CRITICAL). Arm: confirmed regression
  (import sweep + framework-only repro on both versions; blast radius measured end to end by `ent_mcp_oidc`).
  Also kills the `tickets` demo (no auth configured) through `EventHandlerAPIPlugin.post_compile`. The verifier
  adds the deployment angle: rxe 0.9.5 pins `reflex[db]>=0.9.6` with no upper bound, so `pip install -U reflex`
  after 0.9.12 ships bricks every deployed enterprise auth/MCP/REST app — a lockstep enterprise release with an
  upper bound would be needed even if the framework fix lands.
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

- **FINDING-017 — with #7114 the supervisor keeps the dev backend port bound while no worker can serve, so a wedged
  shutdown or a broken app module turns immediate connection refusals into requests that hang for the client's
  timeout** (MEDIUM, dev-only, self-healing; regression CONFIRMED both ways by `dev_server_cli` explorer and verifier,
  `verification/scripts/break_reload_probe.py`). Arm: confirmed regression. Shape: keep #7114 but add a give-up path in
  `ParentBoundGranian` (`reflex/utils/exec.py:726-741`) — refuse or 503 once no worker has come back within a bound,
  and release the socket when the supervisor itself is shutting down.

### Trivially small / significant impact

- **FINDING-019 — a non-UTF-8 stateful-pages marker still wedges backend startup permanently; #7142 says corrupt
  markers are rebuilt** (MEDIUM, `build_prod_export`, verification pending). Arm: trivially small — catch
  `UnicodeDecodeError` (or `ValueError`/`OSError`) alongside `JSONDecodeError` in `_read_stateful_pages_marker()` and
  fall through to the rebuild path.

- **FINDING-015 — #7156's advertised scenario (toast action / `call_script` callback triggering an upload handler)
  still throws `ReferenceError: filesById is not defined`** (HIGH for the scenario, pre-existing; `event_loop`,
  verification pending). Arm: significant impact on a change this release announces as fixed. Shape: propagate the
  `UploadFilesContext` hook/VarData to callback sites, or at minimum reword the #7156 changelog and the toast docs
  so nobody ships `action=` + `rx.upload_files`.

- **FINDING-012 — `rx.data_editor`'s image-preview overlay (the #7081 headline) cannot open in prod while the
  default "Built with Reflex" badge is on; the badge app-wrap swallows the `#portal` div** (HIGH impact,
  pre-existing nesting; `components_bumps`, CONFIRMED with an A/B). Arm: significant user impact on a feature this
  release advertises (0.9.12a1 is the version that ships the carousel CSS), and the fix is small: let
  `StickyBadge.create` accept and render children (`reflex_components_core/core/sticky.py:90-107`) or have
  `_app_root` (`reflex/app.py:1574-1590`) keep negative-priority wraps as siblings. Minimum: document
  `show_built_with_reflex=False` for image cells until fixed.

- **FINDING-004 — the `deps=["router"]` deprecation warning never fires in the default case** (LOW,
  `router_vars`, CONFIRMED). Arm: trivially small — the changelog promises the warning. Emit it where the legacy
  string dep is declared (`_add_static_dep`) instead of testing the merged dep set in
  `_init_var_dependency_dicts`; the verifier's matrix script is the regression test.

## File as issues, fix after release

### reflex-dev/reflex

- FINDING-018 — `reflex run` (dev) never exits on SIGTERM/SIGINT sent to its pid alone (pre-existing on both
  versions; #6981 covers only the process-group path). `docker stop` / `kill <pid>` leave reflex, bun and node
  running. (`dev_server_cli`)
- Clean group-SIGTERM shutdown logs `[ERROR] Unexpected exit from worker-1` — granian's own message, identical on
  0.9.11.post1; a reflex-side fix would filter it in `_granian_log_dictconfig` (`exec.py:689`) (`dev_server_cli`).
  The npm-stickiness claim was refuted (`REFLEX_USE_NPM=0` switches back); document the flag if it is not already.
- FINDING-020 — `@rx.dynamic` components never re-render on state change (pre-existing; `build_prod_export`).
- FINDING-021 — literal asset `src` paths not prefixed with `frontend_path` (pre-existing; docs or compile-time prefix).
- FINDING-022 — `frontend_lazy_bundled_libraries=True` added ~65 KB of initial JS on every page of the test app;
  confirm with wire bytes on a larger app before deciding whether the #7078 claim needs rewording (`build_prod_export`).
- FINDING-023 — the `backend_state_mismatch` latch in `state.js` (previous campaign's FINDING-036) still deadens the
  whole frontend after one delta for an unregistered substate, on both versions; a recompile is the only way out.
  Pre-existing, but HIGH impact and now easier to hit with backend-only workers — worth an issue with a reset path or
  a visible error (`render_ctx_statemgr`).
- FINDING-024 — `app.modify_state("<bare client token>")` raises `ValueError: Invalid path: ('',)` (pre-existing).
- FINDING-025 — `reflex run` wipes `.states/` at startup in prod too (pre-existing; document or gate on env).
- FINDING-016 — cancelled foreground `supersedes=True` handler loses pre-cancellation writes under redis (prod)
  while dev/memory keeps them; needs a 0.9.11.post1+redis baseline before triage (`event_loop`).
- `on_load`-started self-chaining loops keep running after the client disconnects, logging one
  "Attempting to send delta to disconnected client" warning per tick (pre-existing family, `event_loop`).
- #6946 polish: every uncached var is re-sent once right after hydrate; dict key order defeats the dedupe; the
  `_UNKEYABLE_VALUE` branch is unreachable (`event_loop`).
- Generated `package.json` pins `"mergician": "v2.0.2"` (leading `v`; every other pin is bare semver) — cosmetic,
  new in #6850; literal at `packages/reflex-base/src/reflex_base/constants/installer.py:151` (`up_examples_a`, CONFIRMED).
- `reflex db init` without the db extra prints a raw click traceback instead of the guided message (pre-existing,
  `db_optional_imports`, CONFIRMED); `rx.asession()` requires `async_db_url` and nothing in the docs hints at it
  (docs nit — the failure IS surfaced as a backend-error toast).
- Missing app-package `__init__.py` → silent frontend/backend state-name mismatch, every event a no-op, only a browser
  console error (`vars_typing`; pre-existing; `reflex init` skips the file when the app dir exists).
- `rx.Var.create(x)._replace(_var_data=...)` raises `TypeError` on both versions (`vars_typing`; pre-existing).
- FINDING-013 — `rx.vars.use_id()` in an `rx.foreach` body yields one id for every item (new API, #6708; docs
  gap — the constraint is stated on `use_hook_var` but not on `use_id()` or its docs pages; `components_bumps`,
  CONFIRMED, LOW).
- `Axis.tick_formatter` accepts only a literal JS string; a `FunctionStringVar` raises `TypeError` (pre-existing,
  `components_bumps`).
- FINDING-006 — backend (underscore) var shadowing across substates still silently ignored (LOW,
  pre-existing gap in #7077's scope, `router_vars`, CONFIRMED): extend `_check_overridden_inherited_vars` to
  `inherited_backend_vars`, or narrow `news/7077.breaking.md` to base vars.
- Pre-existing, re-observed: `uv pip install reflex-<ver>.tar.gz` fails on the workspace `tool.uv.sources`
  (issue #7088); `reflex run` keeps running and prints "Backend running at …" after the app module raised at
  import (both versions; makes FINDING-001 look like a hang).

### reflex-dev/reflex-examples

- `upload`: `@rx.var def files()` reads the upload dir with no state dependency, so the rendered list never refreshes
  (`@rx.var(cache=False)` fixes it); `form-designer`: `/form/<id>` places `rx.form.message` outside `rx.form.field`
  and crashes; `basic_crud`/`twitter`/`data_visualisation` ship no alembic directory (`up_examples_a`, `up_examples_b`).

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
  `ag_grid_finance`; `ColumnDef` derives from `PropsBase` rather than the strict `NoExtrasAllowedProps`). All four
  CONFIRMED by the verifier. Also: issue reflex-dev/reflex#6978 (masked AttributeError in cached vars) can be closed —
  #7115 fixes it on 0.9.12a1.

## Decisions needed from a maintainer

- Release notes for the alpha: `pip install --pre reflex==0.9.12a1` / `uv pip install --prerelease=allow` pull the
  whole alpha train (`up_examples_c` dry run: all eleven packages move together), but `uv pip install --upgrade
  'reflex==0.9.12a1'` WITHOUT the prerelease flag resolves the explicit pin for reflex + reflex-base and leaves every
  `reflex-components-*` at its stable release (`up_examples_b` ran basic_crud in that mixed state: it worked). Worth
  one sentence telling users to pass `--pre`/`--prerelease=allow` or name the component alphas.

- FINDING-002 — the #7132 changelog entry ("keep saving state … when a state defines a var named
  `_get_was_touched`") describes behavior #7136 made unreachable: the declaration now raises
  `StateValueError`. Reword/drop the entry, or fold it into #7136's breaking note.
- (was FINDING-007, refuted) PR #7136's description promised a `REFLEX_STATE_ALLOW_RESERVED_NAMES=1` opt-in that
  was never shipped or documented; nothing published is inconsistent, but #7136 landed a breaking change with no
  opt-in contrary to its own description — worth knowing when judging FINDING-001's fix.
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
