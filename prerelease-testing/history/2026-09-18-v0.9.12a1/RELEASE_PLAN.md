# Release plan — what blocks reflex 0.9.12a1 → 0.9.12 vs what gets filed

**Status: FINAL (2026-09-19 06:00 UTC); re-verified READY on reflex 0.9.12a2 + reflex-enterprise 0.9.6a1 (2026-09-21)** — every
cluster and every adversarial verifier has reported; all five fix-before-release items are fixed, merged, republished and
re-verified against the published packages with the original campaign repros (FINDINGS.md, Phase 7). What is left is in
"What remains before 0.9.12 final" at the end of this file; every deferred finding the maintainer wanted tracked was
filed on 2026-09-22 ("Issues filed for the deferred findings", below). Rubric (from the campaign playbook):
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

## Tracking issues (filed 2026-09-19)

| finding | issue | fix work |
|---|---|---|
| FINDING-001 State metaclass conflict (CRITICAL, regression) | [#7211](https://github.com/reflex-dev/reflex/issues/7211) | **FIXED, reviewed** — reflex [#7215](https://github.com/reflex-dev/reflex/pull/7215) (`6ab3edbc9`, `4290548fe`, rework `fbcdb33a1`); reflex-enterprise [#232](https://github.com/reflex-dev/reflex-enterprise/pull/232) (`038c613`) |
| FINDING-003 withheld uncached var never re-sent (HIGH, regression) | [#7212](https://github.com/reflex-dev/reflex/issues/7212) | **FIXED, reviewed (after one follow-up)** — reflex [#7216](https://github.com/reflex-dev/reflex/pull/7216) (`91020caec`) |
| FINDING-011 REST session-token redaction no-op (HIGH, security, regression) | [#7214](https://github.com/reflex-dev/reflex/issues/7214) | **FIXED, reviewed** — reflex-enterprise [#232](https://github.com/reflex-dev/reflex-enterprise/pull/232) (`c0e6b5d`); reflex breaking-change note in [#7215](https://github.com/reflex-dev/reflex/pull/7215) |
| FINDING-017 supervisor socket hang in dev (MEDIUM, regression) | [#7213](https://github.com/reflex-dev/reflex/issues/7213) | **FIXED, reviewed** — reflex [#7217](https://github.com/reflex-dev/reflex/pull/7217) (`eaf3f4822`) |
| FINDING-012 data_editor portal swallowed by the badge (HIGH impact, pre-existing) | [#6143](https://github.com/reflex-dev/reflex/issues/6143) (existing issue, root cause posted as a comment) | **FIXED, reviewed** — reflex [#7218](https://github.com/reflex-dev/reflex/pull/7218) (`94554d771`) |

Fix agents (Opus, xhigh) worked in `/home/user/wt/<name>` worktrees from `origin/main`; briefs under `fixes/briefs/`,
reports, patches and evidence under `fixes/<name>/`, overview in `fixes/README.md`. All five fixes are done and passed
an independent adversarial review (f003 after one follow-up). PRs for maintainer review: reflex #7215, #7216, #7217,
#7218 and reflex-enterprise #232 (all against `main`); the reflex commits are also cherry-picked onto
`claude/upbeat-feynman-m41a1u` and every fix is exported as `fixes/<name>/patches/*.patch`. Done since (2026-09-20/21): the four
reflex PRs merged to `main` (`006543ab3`) and were republished as reflex/reflex-base 0.9.12a2 (release branch
`f223a0bff`, changelog entries #7215, #7216, #7217, #7218, #7230); reflex-enterprise #232 merged and 0.9.6a1 was built as an
offline wheel. Phase 7 re-ran every original failing repro on the published packages: 11/11 PASS, no new reflex defect
(FINDINGS.md, Phase 7). Still to do: release reflex-enterprise 0.9.6 from #232 no later than reflex 0.9.12 (see
`fixes/README.md`, "Release sequencing", and the last section of this file).

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
  dev and prod+redis, and by both clusters' adversarial verifiers — the `event_loop` verifier adds dev+redis and the
  point that rxe 0.9.5's `redeliver_protected()` relies on the re-delivery #6946 removed). Arm: confirmed regression. Shape: record the "last sent" key after the delta has been
  filtered/emitted (or expose `_suppress_delta_recording()` / a post-filter hook to `get_delta` overrides), not
  while building it in `BaseState.get_delta` (`reflex/state.py` ~2385 → `ComputedVar._record_delta_value`,
  `reflex_base/vars/base.py:2689`). Regression test: `event_loop/scripts/s_filtered.py` against `elapp`, or the
  browser-free `ent_mcp_oidc/verification/2026-09-19-adversarial/pure_delta_memo.py`.

- **FINDING-017 — with #7114 the supervisor keeps the dev backend port bound while no worker can serve, so a wedged
  shutdown or a broken app module turns immediate connection refusals into requests that hang for the client's
  timeout** (MEDIUM, dev-only, self-healing; regression CONFIRMED both ways by `dev_server_cli` explorer and verifier,
  `verification/scripts/break_reload_probe.py`). Arm: confirmed regression. Shape: keep #7114 but add a give-up path in
  `ParentBoundGranian` (`reflex/utils/exec.py:726-741`) — refuse or 503 once no worker has come back within a bound,
  and release the socket when the supervisor itself is shutting down.

### Trivially small / significant impact

- **FINDING-019 — a non-UTF-8 stateful-pages marker still wedges backend startup permanently; #7142 says corrupt
  markers are rebuilt** (LOW after verification; `build_prod_export`, CONFIRMED verbatim, not a regression — 0.9.11.post1
  had no guard at all — and lowered from MEDIUM because only external corruption produces such a marker). Arm: trivially
  small — catch
  `UnicodeDecodeError` (or `ValueError`/`OSError`) alongside `JSONDecodeError` in `_read_stateful_pages_marker()` and
  fall through to the rebuild path.

- **FINDING-015 — #7156's advertised scenario (toast action / `call_script` callback triggering an upload handler)
  still throws `ReferenceError: filesById is not defined`** (MEDIUM, pre-existing; `event_loop`, CONFIRMED by the
  verifier, who lowered it from HIGH because the documented `rx.upload` + sibling submit-button pattern works on
  0.9.12a1). Arm: significant impact on a change this release announces as fixed — the #7156 changelog line names
  exactly this case. Shape: propagate the
  `UploadFilesContext` hook/VarData to callback sites, or at minimum reword the #7156 changelog and the toast docs
  so nobody ships `action=` + `rx.upload_files`.

- **FINDING-012 — `rx.data_editor`'s image-preview overlay (the #7081 headline) cannot open in prod while the
  default "Built with Reflex" badge is on; the badge app-wrap swallows the `#portal` div** (HIGH impact,
  pre-existing nesting; `components_bumps`, CONFIRMED with an A/B). Arm: significant user impact on a feature this
  release advertises (0.9.12a1 is the version that ships the carousel CSS), and the fix is small: let
  `StickyBadge.create` accept and render children (`reflex_components_core/core/sticky.py:90-107`) or have
  `_app_root` (`reflex/app.py:1574-1590`) keep negative-priority wraps as siblings. Minimum: document
  `show_built_with_reflex=False` for image cells until fixed.

- ~~FINDING-004~~ — dropped from this list after the second verifier: the `deps=["router"]` deprecation fires for
  every shape that would break at removal (`auto_deps=False`, or a body that does not read the router; pinned by
  `tests/units/test_state.py:4184`) and is silent only in the redundant `auto_deps=True` + router-reading-body shape,
  where auto tracking already registers all five `rx_router_*` fields and an unknown string dep is silently accepted
  on both versions. Still a one-line nit if wanted — see the nits below.

## File as issues, fix after release

### reflex-dev/reflex

- FINDING-018 — `reflex run` (dev) never exits on SIGTERM/SIGINT sent to its pid alone (pre-existing on both
  versions; #6981 covers only the process-group path). `docker stop` / `kill <pid>` leave reflex, bun and node
  running. (`dev_server_cli`)
- Clean group-SIGTERM shutdown logs `[ERROR] Unexpected exit from worker-1` — granian's own message, identical on
  0.9.11.post1; a reflex-side fix would filter it in `_granian_log_dictconfig` (`exec.py:689`) (`dev_server_cli`).
  The npm-stickiness claim was refuted (`REFLEX_USE_NPM=0` switches back); document the flag if it is not already.
- FINDING-027 — the CDN fallback URL for an unbundled sub-path `@rx.dynamic` import is malformed
  (`reflex_base/components/dynamic.py:205-214` appends `package_path` after the `/+esm` terminator); pre-existing,
  identical on 0.9.11.post1, surfaced by the verifier while refuting FINDING-020 — confirm against jsdelivr, then file
  (`build_prod_export`).
- FINDING-021 (refuted as a defect; docs gap) — nothing under `docs/` mentions `frontend_path` together with assets;
  document that `rx.asset()` is what applies the prefix, so a literal `src` breaks silently (`build_prod_export`).
- FINDING-004 (nit) — make the `deps=["router"]` deprecation fire in the redundant `auto_deps=True` shape too by
  keying on the declaration-time string in `_add_static_dep` rather than the merged set in
  `_init_var_dependency_dicts`; the `router_vars` verifier's matrix script is the test (`router_vars`/`up_examples_b`).
- FINDING-022 — `frontend_lazy_bundled_libraries=True` added ~65 KB of initial JS on every page of the test app;
  confirm with wire bytes on a larger app before deciding whether the #7078 claim needs rewording (`build_prod_export`).
- FINDING-023 — the `backend_state_mismatch` latch in `state.js` (previous campaign's FINDING-036) still deadens the
  whole frontend after one delta for an unregistered substate, on both versions; a recompile is the only way out.
  Pre-existing and deliberate (commented as fatal-by-design in both versions); the verifier lowered it to MEDIUM because
  a reload does recover in the realistic cached-bundle shape (the "no recovery" result was an artifact of
  `.web/nocompile`) — what stays broken is the within-session case (mixed-version backends behind a load balancer,
  `api_url` at a different backend). Worth an issue: drop/warn on the unknown substate and apply the rest, or never
  send substates the page did not register (`render_ctx_statemgr`, verifier).
- FINDING-024 — `app.modify_state("<bare client token>")` raises `ValueError: Invalid path: ('',)` → a bare HTTP 500
  from an API route (pre-existing, CONFIRMED); `App.modify_state` still carries an un-deprecated `token: str` overload
  (`reflex/app.py:1801`), so type checkers accept the call. Default an empty state path to the root state, or raise a
  message naming the `BaseStateToken` replacement (`render_ctx_statemgr`, verifier).
- FINDING-025 — `reflex run` wipes `.states/` at startup in `--env prod` too (pre-existing, CONFIRMED by execution on
  both versions); scope widened by the verifier: `StateManagerDisk` is the default whenever no redis URL is configured,
  so every restart drops every live session's state in the default configuration. Document it, or gate
  `reset_disk_state_manager()` (`reflex/reflex.py:597`) on env (`render_ctx_statemgr`, verifier).
- FINDING-016 — a cancelled foreground `supersedes=True` handler loses ALL its writes under the redis state manager
  while the in-memory manager keeps them (pre-existing: identical on 0.9.11.post1 + redis;
  `StateManagerRedis._try_modify_state` skips the write-back on `CancelledError`). Memory vs redis, not dev vs prod.
  Upstream issue about the divergence (`event_loop`, verifier).
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

(Steps 1 and 2 were completed on 2026-09-20/21 and re-verified on the published 0.9.12a2 — see the tracking table
above and FINDINGS.md, Phase 7. Step 3 remains open as listed under "Decisions needed from a maintainer".)

1. FINDING-001 framework fix first (one PR, regression test from `orch_probes/metaclass_probe.py`), then
   re-run `orch_probes/ent_import_probe.py` and the `ent_mcp_oidc` harness without the shim.
2. FINDING-003 (both verifiers have reported; independent files: `reflex/state.py` delta path vs
   `reflex/istate/validation.py`, so it can land in parallel with 1).
3. The changelog decisions (002, 007, the metaclass note, the #7156 line behind FINDING-015) can ride one
   docs/changelog PR; the FINDING-004 one-liner is optional.

## What remains before 0.9.12 final (2026-09-21)

Re-verification verdict: **READY**. Nothing in reflex itself blocks the release; the remaining items are release
mechanics and downstream coordination.

1. **Publish reflex-enterprise 0.9.6 (from #232, the 0.9.6a1 content) no later than reflex 0.9.12.** The published
   rxe 0.9.5 has no upper bound on reflex (`Requires-Dist: reflex[db]>=0.9.6`), so a user who upgrades only reflex
   lands on the broken 0.9.12 + 0.9.5 pair (FINDING-001's metaclass conflict, FINDING-011's redaction no-op) with no
   resolver warning. Put "reflex 0.9.12 requires reflex-enterprise >= 0.9.6" in both release notes.
2. **Stock-install smoke after the finals publish**: `pip install reflex==0.9.12` with no prerelease flag, init,
   run, browser; confirm the resolved graph is all-final (the nine component packages must move from their `a1`
   versions to finals in the same batch — a bare `reflex==0.9.12a2` pin today upgrades only reflex/reflex-base).
3. Maintainer decisions carried over unchanged from the list above (FINDING-002's changelog entry, #7077's hard
   error, #7115/#7131 wording, the #7156 line behind FINDING-015). The "metaclass Breaking Changes entry" decision is
   moot: #7215 restored `type(rx.State) is BaseStateMeta`. #7215's breaking-change note about the removed
   `reflex.istate.validation` module stands.
4. reflex-enterprise follow-ups surfaced by the re-verification, neither blocking and both for that repo's tracker:
   the `TYPE_CHECKING` import of the removed `reflex.istate.validation._StateMeta` in `auth/oidc/state.py`
   (static-only) — **fixed and merged, reflex-enterprise [#235](https://github.com/reflex-dev/reflex-enterprise/pull/235)**
   (`OIDCCookieMeta` derives from the public `reflex_base.vars.BaseStateMeta`; a new unit test executes every
   `TYPE_CHECKING` import in the package; lock bumped to reflex 0.9.12a2), so it ships with 0.9.6 — and `GET /_reflex/events/openapi.yaml` answering
   500 unless `pyyaml` is installed (pre-existing in 0.9.5; declare the dependency or answer 501).

## Issues filed for the deferred findings (2026-09-22)

Filed on the maintainer's instruction before cutting 0.9.12, one issue per item unless noted; each carries the repro,
regression status and evidence links from this campaign.

| item | issue |
|---|---|
| FINDING-015 `filesById is not defined` from a toast action / `call_script` callback | [#7244](https://github.com/reflex-dev/reflex/issues/7244) |
| FINDING-019 non-UTF-8 stateful-pages marker wedges backend startup | [#7245](https://github.com/reflex-dev/reflex/issues/7245) |
| FINDING-024 `modify_state("<bare token>")` → 500, un-deprecated `str` overload | [#7246](https://github.com/reflex-dev/reflex/issues/7246) |
| FINDING-023 `backend_state_mismatch` latch deadens the frontend | [#7247](https://github.com/reflex-dev/reflex/issues/7247) |
| FINDING-016 cancelled `supersedes=True` handler loses writes under redis | [#7248](https://github.com/reflex-dev/reflex/issues/7248) |
| FINDING-027 malformed CDN fallback URL for sub-path `@rx.dynamic` imports | [#7249](https://github.com/reflex-dev/reflex/issues/7249) |
| FINDING-008 `on_click` inside `rx.dropdown_menu.trigger` never runs | [#7250](https://github.com/reflex-dev/reflex/issues/7250) |
| `on_load`-started self-chaining loop keeps running after client disconnect | [#7251](https://github.com/reflex-dev/reflex/issues/7251) |
| dev `reflex run` prints "Backend running at" after the app module failed to import | [#7252](https://github.com/reflex-dev/reflex/issues/7252) |
| #6946 polish (re-send after hydrate, dict key order, dead `_UNKEYABLE_VALUE` branch) | [#7253](https://github.com/reflex-dev/reflex/issues/7253) |
| withheld async uncached var leaves its coroutine unawaited (`RuntimeWarning`) | [#7254](https://github.com/reflex-dev/reflex/issues/7254) |
| `_app_root` nesting contract: a childless wrap swallows lower-priority wraps (f012 follow-up) | [#7255](https://github.com/reflex-dev/reflex/issues/7255) |
| `rx.Var.create(x)._replace(_var_data=...)` raises `TypeError` | [#7256](https://github.com/reflex-dev/reflex/issues/7256) |
| `Axis.tick_formatter` accepts only a literal string | [#7257](https://github.com/reflex-dev/reflex/issues/7257) |
| missing app-package `__init__.py` → silent state-name mismatch | [#7258](https://github.com/reflex-dev/reflex/issues/7258) |
| `reflex db init` without the db extra prints a raw traceback | [#7259](https://github.com/reflex-dev/reflex/issues/7259) |
| FINDING-002 + #7115 `hasattr`/`getattr` change + #7131 wording (changelog) | [#7260](https://github.com/reflex-dev/reflex/issues/7260) |
| FINDING-021 `frontend_path` + assets docs | [#7261](https://github.com/reflex-dev/reflex/issues/7261) |
| FINDING-022 `frontend_lazy_bundled_libraries` +65 KB (confirm the potential regression) | [#7262](https://github.com/reflex-dev/reflex/issues/7262) |
| #7077 hard error vs warning (maintainer decision) | [#7263](https://github.com/reflex-dev/reflex/issues/7263) |
| #7215 review follow-ups (dead test statement, typed root default, document the metaclass contract) | [#7264](https://github.com/reflex-dev/reflex/issues/7264) |
| FINDING-006 backend (underscore) var shadowing across substates | [#7265](https://github.com/reflex-dev/reflex/issues/7265) |
| granian `Unexpected exit from worker-1` on clean group SIGTERM (residual of #6981) | [#7266](https://github.com/reflex-dev/reflex/issues/7266) |

Already tracked before this batch: FINDING-018 → [#6980](https://github.com/reflex-dev/reflex/issues/6980) (PR #7209);
prod 404 status for dynamic routes → [#6983](https://github.com/reflex-dev/reflex/issues/6983) (PR #6996); sdist install →
[#7088](https://github.com/reflex-dev/reflex/issues/7088); FINDING-006's sibling (mixin route) → [#7190](https://github.com/reflex-dev/reflex/issues/7190)
(PR #7206); reflex-enterprise OpenAPI 500 without `pyyaml` → [reflex-enterprise#227](https://github.com/reflex-dev/reflex-enterprise/issues/227);
AG Grid demo breakage → [reflex-enterprise#225](https://github.com/reflex-dev/reflex-enterprise/issues/225); #6978 closed by #7115.

Deliberately not filed (maintainer decision, 2026-09-22): FINDING-025 (`.states/` wiped at startup in prod), FINDING-013
(`use_id()` in `rx.foreach`), the f003 note that a delta is recorded as sent before `emit_update` delivers it, FINDING-004
(`deps=["router"]` deprecation in the redundant shape), the `mergician` `v` prefix, the `async_db_url` docs nit, the accordion
`collapsible` warning, the `get_delta` override error message, and every reflex-enterprise item (`/_reflex/cookies/sync` 405,
client token in OIDC error log lines, the `_override_base_method` dependency, `column_def` dropping unknown kwargs).

Not filed for lack of access: the reflex-examples items (the `upload` example's never-refreshing `files` var, form-designer's
`/form/<id>` crash, the missing alembic directories in basic_crud/twitter/data_visualisation) — that tracker was not reachable
from the QA sandbox; they remain listed under "File as issues" above for a maintainer to file.
