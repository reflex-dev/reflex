# Findings — reflex 0.9.12a1 pre-release testing (2026-09-19)

Independent end-to-end exploration of the `r/pre-2026.09.18-35410916948` release train. All installs
PyPI-only in isolated uv venvs (never from a checkout); every sample app run for real (`reflex run`, dev
and prod) and driven in headless Chromium via Playwright with server-log / console / network / websocket
capture; claimed issues re-reproduced by independent adversarial verifier agents from the written repro
alone. Baselines against the previous stable, reflex 0.9.11.post1. Orchestrator + 15 explorer agents +
one verifier per cluster with claims (Opus 5, xhigh effort), two at a time.

**Campaign status: IN PROGRESS** — this file is updated as clusters finish. Sections marked _(pending)_
are not yet written. Process note: the fan-out was interrupted at ~03:00 UTC by the organisation's monthly
spend limit after 10 of 15 explorers had finished; every adversarial verifier and the remaining five explorers
(build_prod_export, render_ctx_statemgr, dev_server_cli, up_examples_c, db_optional_imports) died with the
limit error. Both workflows were resumed from cache at 04:38 UTC once the limit reset (completed agents replay,
the failed ones re-run), so "verification pending" below means the verifier had not yet run at the time of writing.

## Versions under test (all published on PyPI, verified with check_release_versions.py)

New in this train (alphas): reflex 0.9.12a1, reflex-base 0.9.12a1, reflex-components-code 0.9.6a1,
-core 0.9.10a1, -dataeditor 0.9.3a1, -gridjs 0.9.2a1, -markdown 0.9.4a1, -plotly 0.9.7a1, -radix 0.9.10a1,
-recharts 0.9.4a1, -sonner 0.9.4a1. Already stable, unchanged: moment 0.9.4, lucide 1.0.4, react-player
0.9.2, docgen 0.9.5, hosting-cli 0.1.72, otel 0.1.0, release 0.1.1, build-sdk 0.0.2 (first release of the
renamed SDK). Published reflex-enterprise: 0.9.5 (requires `reflex[db]>=0.9.6`).

Environment: Linux container (Ubuntu 24.04), 4 CPU / 15 GB, Node v22.22.2, reflex-managed Bun 1.4.0
(system bun 1.3.11 ignored as below the minimum), Python 3.11.15 primary (3.10/3.12/3.13/3.14 and
3.15.0rc2 via uv), Chromium via Playwright 1.63, redis-server 7.0, outbound via an egress proxy.

## Executive summary

_(pending — written when the clusters finish)_

Confirmed so far:
- **FINDING-001 (HIGH, regression, downstream-breaking, CONFIRMED by orchestrator on both versions):**
  `rx.State` gained a new metaclass (`reflex.istate.validation._StateMeta`, from #7136), so any metaclass
  derived from `reflex.vars.BaseStateMeta` — the metaclass `rx.State` had through 0.9.11.post1 — can no
  longer be applied to a State subclass. Published reflex-enterprise 0.9.5 does exactly that in
  `auth/oidc/state.py`, so `import reflex_enterprise.auth.oidc.state` raises `TypeError: metaclass
  conflict` on 0.9.12a1 and imports cleanly on 0.9.11.post1.

Verified by clusters so far (details in the cluster summaries): #7068 router split end to end (`router_vars`,
`ent_aggrid`); #6850 as_child transparency, #7176 memo app-wraps, #6708 svg memo, #7122 shared chains, #7121
compile speed-up, #7130, #7133 (`memo_aschild`); #7096/#7049 — the reflex-enterprise ag-grid demo's dev backend,
dead on 0.9.11.post1, runs on 0.9.12a1 (`ent_aggrid`); the whole MCP + OIDC surface behind the FINDING-001
shim (`ent_mcp_oidc`); #7155 otel compile spans (`orch_otel`).

Verified changelog claims (orchestrator, not findings): all 19 packages published with wheel + sdist;
122 `.pyi` stubs ship identically in wheel and sdist; the wheel pins `reflex-base==0.9.12a1` exactly and
`reflex-components-moment>=0.9.4`; blank app dev and prod are clean with react-router 8.4.0 (#7202) and
mergician 2.0.2 (#6850) in the generated `package.json`; `reflex-build-sdk` 0.0.2 exposes the renamed
clients and honors `REFLEX_BUILD_BACKEND_URL` over `REFLEX_CLOUD_BACKEND_URL` (#7201); `reflex cloud`
refuses non-interactive use without a token (0.1.72, #6917); reflex-local-auth 0.5.0 and
reflex-global-hotkey 1.2.3 import surfaces resolve on 0.9.12a1; reflex-otel 0.1.0 exports the initial dev
compile span tree that 0.9.11 lost (#7155).

Index:
- FINDING-001: State metaclass change breaks downstream metaclasses derived from `BaseStateMeta` — every reflex-enterprise 0.9.5 app using AuthPlugin, MCPPlugin or EventHandlerAPIPlugin fails to start (CRITICAL, regression) — **CONFIRMED** by the orchestrator, two explorers and the adversarial verifier
- FINDING-002: the #7132 changelog entry describes behavior #7136 made unreachable — a `_get_was_touched` var is now rejected at class creation (LOW, changelog/behavior mismatch, maintainer decision)
- FINDING-003: a `@rx.var(cache=False)` withheld from a delivered delta by a downstream `get_delta` filter is never re-sent — #6946's last-sent memo is written while the delta is BUILT, not when it is delivered (HIGH, regression; reproduced in pure reflex by `event_loop` in dev and prod+redis, through reflex-enterprise auth by `ent_mcp_oidc`, and by the verifier's own 60-line pure-reflex script) — **CONFIRMED**
- FINDING-004: the documented `deps=["router"]` deprecation warning never fires in the default case — the guard in `_init_var_dependency_dicts` tests the MERGED dep set after auto-dep detection has added the `rx_router_*` names (LOW, new in #7068) — found by `router_vars` and `up_examples_b`; **CONFIRMED** by the verifier with a corrected diagnosis
- ~~FINDING-005~~: "a narrow `deps=` cannot narrow" — **REFUTED** by the verifier (`deps=[State.router.url], auto_deps=False` registers only `rx_router_url`; `deps=` is additive by long-standing design; the −47% vs −67% gap compares whole frames with the PR's router-only measurement). Kept in the refuted list below.
- FINDING-006: a substate shadowing a parent's backend (underscore) var is still silently ignored — `_check_overridden_inherited_vars` skips every `_`-prefixed name (`reflex/state.py:1335`) (LOW, pre-existing gap) — **CONFIRMED** by the verifier on both versions, with the runtime damage characterised (child default discarded, reads/writes resolve to the parent)
- ~~FINDING-007~~: "PR #7136's documented `REFLEX_STATE_ALLOW_RESERVED_NAMES=1` escape hatch is missing" — **REFUTED as a defect** by the verifier: the flag is promised only in the PR description; the news fragment, the docs paragraph and the changelog never mention it (so nothing shipped is wrong), and it would not have helped FINDING-001 anyway. Kept as a note for the release manager: #7136 shipped a breaking change with no opt-in, contrary to its own description.
- FINDING-008: `rx.dropdown_menu.trigger` swallows its child button's `on_click` — the menu opens, the handler never runs; the other four Radix triggers compose correctly (LOW after verification: pre-existing, upstream Radix — the menu opens on pointerdown and the dismissable layer sets `pointer-events:none`, a synthetic `el.click()` runs the handler, so reflex's wiring is correct) — **CONFIRMED** by the verifier as a bug to file, not a release item
- ~~FINDING-009~~: "`rx.cond` evaluates both branches eagerly; a render-time throw in the untaken branch fails the prod build" — **REFUTED** by the verifier: an `@rx.memo` component that throws and an idiomatic `None`-deref state expression both sit unharmed in the untaken branch (dev renders, prod prerenders); only a raw `rx.Var("<js>")` literal is inlined into the parent JSX and evaluated, which is plain JS semantics through reflex's escape hatch, and the prod build fails byte-identically on 0.9.11.post1. Kept in the refuted list.
- ~~FINDING-010~~: "`on_submit` form data is polluted with id-keyed duplicates" — **reclassified** by the verifier: intentional, long-standing API (`Form._get_form_refs()` sends every ref in the form subtree so an id-only field reaches the handler; the `None`s are `getRefValue` on non-input ids); byte-identical on 0.9.11.post1. A cleanup ticket at most; kept in the refuted list.
- FINDING-012: the `rx.data_editor` overlay editor — the image-preview carousel that is the headline of #7081 — never opens in PROD when the "Built with Reflex" badge is on: the sticky-badge app-wrap nests the dataeditor's `#portal` wrap and drops it (HIGH impact on a headline feature, pre-existing nesting, trivially small to fix) — **CONFIRMED** by the verifier on a fresh 12-line app with an A/B: `show_built_with_reflex=False` restores the portal and the carousel opens
- FINDING-013: `rx.vars.use_id()` inside an `rx.foreach` body returns one identical id for every item — duplicate DOM ids, every `html_for` label targets the first row (LOW after verification — by-design limitation documented on `use_hook_var` but not on `use_id()` or its three docs pages; a docs fix) — **CONFIRMED** by the verifier
- ~~FINDING-014~~: "the #7124 changelog's `reflex.components.datadisplay.code` path fails" — **REFUTED** by the verifier: the changelog names a module path, and `import reflex.components.datadisplay.code` works on both versions; only the `from … import code` spelling fails, and it never worked. Kept in the refuted list.
- FINDING-015: #7156's headline scenario — a toast action or `rx.call_script` callback that triggers an upload handler — still fails: the handler slot is fixed but the payload's `filesById?.["u2"]` is only in scope inside the component that renders `rx.upload`, so the click throws `ReferenceError: filesById is not defined` and no upload starts (HIGH for the advertised scenario, pre-existing, changelog line misleading) — claimed by `event_loop`, verification pending
- FINDING-016: a cancelled foreground `@rx.event(supersedes=True)` handler loses its pre-cancellation state writes under prod+redis (dev/memory keeps them) — the `yield` before the `await` is not flushed when `CancelledError` propagates (MEDIUM, dev/prod divergence; 0.9.11.post1+redis baseline not measured) — claimed by `event_loop`, verification pending
- FINDING-017: after a SIGTERM that fails to stop `reflex run` (dev), or while the app module is broken, the backend port stays bound and accepts connections that are never answered — 0.9.11.post1 released the port and clients got an immediate refusal; a side effect of #7114 moving the listening socket into the granian supervisor (HIGH, regression) — claimed by `dev_server_cli`, verification pending
- FINDING-018: `reflex run` (dev) ignores SIGTERM/SIGINT delivered to its pid alone (`docker stop`, `kill <pid>` semantics) — reflex, bun and node survive and the ports stay bound; only a process-group signal (Ctrl-C) exits cleanly (MEDIUM, pre-existing on both versions; #6981's changelog line promises a clean SIGTERM exit) — claimed by `dev_server_cli`, verification pending
- FINDING-019: a stateful-pages marker containing non-UTF-8 bytes still crashes backend startup permanently — `UnicodeDecodeError` escapes `_read_stateful_pages_marker()`'s `except (FileNotFoundError, json.JSONDecodeError)` and the corrupt marker is never replaced (MEDIUM, gap in the #7142 "rebuilt when missing or corrupt" claim; same input crashes 0.9.11.post1) — claimed by `build_prod_export`, verification pending
- FINDING-020: a `@rx.dynamic` component never re-renders when the state it reads changes — the delta carries only the plain field, never the recomputed component var (MEDIUM, pre-existing, dev and prod) — claimed by `build_prod_export`, verification pending
- FINDING-021: literal asset `src` paths (`rx.image(src="/components/logo.svg")`) are not prefixed with `frontend_path`, so the image 404s while the file is served under `/app/...` (LOW, pre-existing) — claimed by `build_prod_export`
- FINDING-022: `frontend_lazy_bundled_libraries=True` INCREASED decoded initial JS bytes by ~65 KB (+3.7–5.5%) on every page of the test app, including pages that use no optional library — the #7078 "reducing JavaScript loaded by ordinary pages" claim did not hold (LOW, perf-claim gap; measured as decoded bodies on one app, needs a wire-bytes/larger-app confirmation) — claimed by `build_prod_export`
- FINDING-023: a hydrate/event delta naming a substate the compiled frontend has no dispatcher for sets `backend_state_mismatch=true` in `state.js` and every later event is discarded — zero websocket frames leave the browser until the frontend is recompiled (HIGH, pre-existing on both versions; the previous campaign's FINDING-036, re-tested because #6181 rewrote the dispatcher registry and did not change the latch) — re-confirmed by `render_ctx_statemgr`
- FINDING-024: `app.modify_state("<client token>")` with the bare token raises `ValueError: Invalid path: ('',)` from `BaseStateToken.from_legacy_token` — the deprecated string form is broken for its most obvious argument (MEDIUM, pre-existing) — claimed by `render_ctx_statemgr`, verification pending
- FINDING-025: `reflex run` deletes the whole `.states/` directory at startup in `--env prod` as well as dev, whatever `REFLEX_STATE_MANAGER_MODE` is, so disk-backed state never survives a restart (LOW, pre-existing, intentional-looking `reset_disk_state_manager()` call) — claimed by `render_ctx_statemgr`
- FINDING-026: the #7083 changelog understates the behavior change — on a bare install a plain `class Item(rx.Model)` (no `table=True`) now fails at class-definition time with the guided ImportError, where 0.9.11.post1 let it define and failed only at instantiation; intended per the PR discussion, but the entry cites only the `table=True` form (LOW, changelog wording) — claimed by `db_optional_imports`
- FINDING-011: reflex-enterprise's REST `redact_router_session()` became a silent no-op — it looks for the `router` key that #7068 removed from `state.dict()`, so server-generated `client_token`/`session_id` survive into REST responses and event deltas (HIGH, **security-relevant**, regression, cross-package) — **CONFIRMED** by the verifier in-process AND over real HTTP (`/_reflex/retrieve_state` and the event endpoint's ndjson delta return the server-side `client_token` on 0.9.12a1; blanked on 0.9.11.post1)

## FINDING-001: State metaclass change breaks downstream metaclasses derived from `BaseStateMeta` (CRITICAL, regression)

- Cluster: `orch_probes` (found by the orchestrator's enterprise import sweep before the fan-out; the
  `ent_mcp_oidc` cluster measures the user-facing blast radius) | Regression vs 0.9.11.post1: **yes** |
  Verifier: orchestrator, both versions, framework-only and enterprise repro
- Repro (framework-only, no enterprise needed) — `orch_probes/metaclass_probe.py`:
  ```
  cd $SB && uv venv envs/shared --python 3.11 && uv pip install --python envs/shared/bin/python --prerelease=allow 'reflex==0.9.12a1'
  envs/shared/bin/python metaclass_probe.py
  ```
  ```python
  from reflex.vars import BaseStateMeta
  class CookieMeta(BaseStateMeta): ...
  class S(rx.State, metaclass=CookieMeta): x: int = 0
  # 0.9.12a1: TypeError: metaclass conflict: the metaclass of a derived class must be a (non-strict)
  #           subclass of the metaclasses of all its bases
  # 0.9.11.post1: works (type(rx.State) is BaseStateMeta)
  ```
  Enterprise repro — `orch_probes/ent_import_probe.py` in a venv with the train +
  `reflex-enterprise[mcp]==0.9.5`: `import reflex_enterprise.auth.oidc.state` → the same TypeError at
  `reflex_enterprise/auth/oidc/state.py:381` (`class OIDCAuthState(ConfigMixin, rx.State, mixin=True,
  metaclass=OIDCCookieMeta)`, with `class OIDCCookieMeta(BaseStateMeta)` at line 347). 22 other enterprise
  modules import fine. `ent_import_probe_prev.py` on 0.9.11.post1: 23/23 import.
- Evidence: `orch_probes/NOTES.md` (probes 1 and 4), the two probe scripts.
- Root cause: #7136 ("Validate reserved state names before registration") made
  `reflex/state.py:629` read `class BaseState(EvenMoreBasicBaseState, metaclass=_StateMeta)` with
  `_StateMeta(BaseStateMeta)` defined in `reflex/istate/validation.py:90`. Two sibling subclasses of
  `BaseStateMeta` cannot both be the metaclass of one class. Deriving from `type(rx.State)` works on
  both versions, but no published downstream code does that today.
- Impact (measured by the `ent_mcp_oidc` explorer, `ent_mcp_oidc/NOTES.md` ISSUE-1): **total for enterprise
  auth and MCP.** An app with only `rxe.MCPPlugin()` dies at startup — `MCPPlugin.post_compile` →
  `build_event_handler_index` → `auth/enforcement.is_exempt` imports `reflex_enterprise.auth.oidc.state`
  (`logs/a2_mcpapp.log`); an app with only `rxe.AuthPlugin()` dies at `from reflex_enterprise.auth import
  AuthUserState, GenericOIDCAuthState` (`logs/a2_authonly_new.log`); the shipped `demos/oidc` cannot import.
  All three start on 0.9.11.post1. The `ent_map_dnd_flow_mantine` cluster adds a fourth victim that configures
  **no auth at all**: the `tickets` demo's backend worker exits during `EventHandlerAPIPlugin.post_compile`
  (`ent_map_dnd_flow_mantine/logs/tickets_new_dev.TRACEBACK.txt`), while the vite frontend keeps answering 200 so
  the page loads and never connects; same demo + same wheel starts cleanly on 0.9.11.post1. Their pure-reflex
  repro `ent_map_dnd_flow_mantine/scripts/repro_statemeta.py` is equivalent to `orch_probes/metaclass_probe.py`.
  With a test-only shim that forces the one class definition through
  (`scripts2/oidc_meta_shim.py`, clearly not a fix), the entire MCP + OIDC surface passes end to end, so
  the metaclass is the only #7136 incompatibility in reflex-enterprise 0.9.5. Any third-party State
  metaclass written the same way breaks. Nothing in the changelog announces the metaclass change. Also
  noted by both agents: when the app module raises at import, `reflex run` still prints "Backend running
  at ..." and keeps running (pre-existing, both versions) — which makes this failure look like a hang.
- Verifier (`ent_mcp_oidc/verification/2026-09-19-adversarial/`): reproduced the one-line import, the MCPPlugin-only
  app (`/ping` 000 on 0.9.12a1 vs 200 on 0.9.11.post1) and the byte-for-byte traceback chain on its own ports;
  hash-verified the shared venv against the wheel RECORDs (248 files, 0 mismatches). The `ent_map_dnd_flow_mantine`
  verifier adds the cleanest proof of mechanism: monkeypatching only `reflex.vars.BaseStateMeta = type(rx.State)` in
  `rxconfig.py` makes the unmodified tickets demo start cleanly on 0.9.12a1, and captured the user-visible symptom
  (page loads, "Cannot connect to server: websocket error", repeated `ERR_CONNECTION_REFUSED`). Two facts every
  refutation ran into: **reflex-enterprise 0.9.5 declares `reflex[db]>=0.9.6` with no upper bound, so a routine `pip install -U
  reflex` after 0.9.12 ships bricks every deployed enterprise auth/MCP/REST app**; and `BaseStateMeta` is exported in
  `reflex_base.vars.__all__`, so "enterprise relied on a private API" is not a defence.
- Suggested fix shape (for the maintainers, not applied here): perform the #7136 validation inside
  `BaseStateMeta.__new__` (guarded on "a base is a BaseState") so `rx.State` keeps `BaseStateMeta` as its
  metaclass, or make the validating metaclass compose with sibling `BaseStateMeta` subclasses; and add a
  changelog note either way. Enterprise can independently switch to `class OIDCCookieMeta(type(rx.State))`.

## FINDING-002: #7132's changelog entry describes behavior that #7136 made unreachable (LOW, changelog mismatch)

- Cluster: `orch_probes` | Regression vs 0.9.11.post1: behavior change (declaration now rejected instead of
  silently breaking persistence) | Verifier: orchestrator, both versions
- Repro: `orch_probes/reserved_names_probe.py` — `class S(rx.State): _get_was_touched: bool = False` raises
  `StateValueError: State name `_get_was_touched` is reserved by BaseState; use a different name instead.` on
  0.9.12a1; on 0.9.11.post1 the class is accepted (and, per #7132, disk/redis persistence silently stopped).
- Evidence: `orch_probes/reserved_names.log`.
- The root changelog's Bug Fixes say "Keep saving state to disk and Redis when a state defines a var named
  `_get_was_touched`. (#7132)" while the Breaking Changes say reserved names are rejected (#7136). The
  rejection is the better outcome, but a reader of the #7132 line will expect the declaration to work.
  Decision for the maintainers: reword/drop the #7132 entry (or fold it into #7136's). Also newly rejected
  with clear messages: base vars named `router`, `substates`, `dirty_vars`; handlers named `add_field`.

## FINDING-003: a withheld `@rx.var(cache=False)` is never re-sent once visible (HIGH, regression — CONFIRMED by two clusters)

- Clusters: `ent_mcp_oidc` (through reflex-enterprise auth) and `event_loop` (pure reflex, dev and prod+redis) |
  Regression vs 0.9.11.post1: **yes** in both | Adversarial verifier: pending
- Pure-reflex repro (`event_loop/NOTES.md` ISSUE-1, page `/filtered` of `elapp`, driver `scripts/s_filtered.py`): a
  State subclass overrides `get_delta` (the pattern the `get_delta` docstring documents for downstream code) and drops
  the uncached var's key while a flag is set; clear the flag; the client keeps the stale value until the var's value
  changes again. 0.9.11.post1 delivers it. Evidence: `event_loop/out/filtered.txt`, `out_prod/filtered.txt`,
  `out_prev/filtered.txt`, `screenshots/dev_filtered_after_show*.png`.
- Verifier: reran the browser table exactly as written (stale through login and two events, correct after reload,
  0.9.11.post1 correct immediately) and closed the gap the written repro left ("only reproducible on top of the
  FINDING-001 shim") with `verification/2026-09-19-adversarial/pure_delta_memo.py`: no enterprise, no shim, no browser
  — a filter on `rx.State.get_delta` clears and the var is delivered on 0.9.11.post1, permanently suppressed on
  0.9.12a1. Repro-quality note: the explorer's four `uncached_*.png` are byte-identical (screenshotted after the final
  reload, the one step where both versions agree).
- Mechanism (both agents agree, `event_loop` cites lines): `BaseState.get_delta` (`reflex/state.py` ~2385) calls
  `cvar._record_delta_value(self, value, token)` while building the delta, and `ComputedVar._record_delta_value`
  (`reflex_base/vars/base.py:2689`) writes `instance.__last_delta_<js_expr> = (token, key)` immediately. Nothing rolls
  it back when a wrapper removes the entry or when delivery fails. `reflex/state.py:317 _suppress_delta_recording()`
  is the existing primitive for this but is private and used only by `reflex/istate/shared.py:122`.
- Original observation:
- Repro (needs the FINDING-001 shim to run enterprise on 0.9.12a1): `ent_mcp_oidc/NOTES.md` ISSUE-2 and
  `scripts2/uncached_after_login.py` — an `@rxe.var(auth=True, cache=False)` stays at its compiled default
  through login and two further events; only a full reload shows the server value. 0.9.11.post1 shows it
  right after login. Evidence: `ent_mcp_oidc/logs/uncached_new.json`, `uncached_prev.json`, `shots/uncached_*.png`.
- Mechanism (explorer's analysis): #6946 records the last value an uncached var sent per client when the
  delta is computed, not when it is delivered; enterprise's `get_delta` override filters the protected
  entry out of the delta, so the memo says "sent" for a value the browser never received, and the next
  recomputation (same value) is deduped away. Any downstream delta filter, or any delivery failure between
  compute and emit, has the same exposure.

## FINDING-011: reflex-enterprise REST session-token redaction is a no-op after the router split (HIGH, security-relevant, regression — CONFIRMED)

- Cluster: `ent_map_dnd_flow_mantine` | Regression vs 0.9.11.post1: **yes** (probe and HTTP run on both) | Verifier:
  CONFIRMED — and, contrary to the explorer's assumption, reproducible over HTTP: with only the FINDING-001 metaclass
  shim in `rxconfig.py`, the unmodified `tickets` demo runs on 0.9.12a1 and `verification/v_leak_http.py` (anonymous
  app bearer → `POST /_reflex/retrieve_state`, `POST /_reflex/event/<state>/seed`) shows `rx_router_session.client_token
  = 95ddb344-…` in BOTH the retrieve_state body and the ndjson event delta — a server-side session identifier the
  caller never presented (not its bearer). 0.9.11.post1: the same responses carry `router` with `client_token` blanked.
  Root-state keys on 0.9.12a1 are exactly `is_hydrated` + the five `rx_router_*`; there is no `router` key for
  `redact_router_session()` (`event_handler_api.py:733`) to find, so redaction silently no-ops on the REST, MCP and
  agent-delta surfaces.
- Repro: `ent_map_dnd_flow_mantine/scripts/probe_router_redact.py` from a neutral cwd on the `ent` and `entprev`
  venvs: it builds router data exactly as `EventHandlerAPIPlugin` does (`router_data_for_token(...)`, then
  `state.router = RouterData.from_router_data(...)`), runs rxe's `redact_router_session()` over `state.dict()`
  and searches for the token. 0.9.11.post1: the root state carries `router_rx_state_ = RouterData(session=
  SessionData(client_token=''...))` — redacted. 0.9.12a1: the dict has `rx_router_session_rx_state_` with the
  real `client_token`/`session_id` and no `router` key, so nothing is redacted. Evidence: NOTES.md "ISSUE 2".
- Mechanism: #7068 made `router` a property with no backing field, so it no longer appears in `state.dict()`;
  rxe 0.9.5 `plugins/event_handler_api.py:733` redacts by looking up that key. Nothing over HTTP can be shown
  until FINDING-001 is fixed (the tickets demo cannot start), so this MUST be re-verified end to end over the REST
  surface (`/_reflex/event/<state>/<handler>`, `retrieve_state`) on the next alpha. Whether the fix lands in reflex
  (keep a redactable `router` entry / provide a hook) or in a lockstep reflex-enterprise release is a maintainer
  decision, but a released 0.9.12 against the published rxe 0.9.5 would leak the tokens.

## FINDING-015: #7156's advertised scenario still fails — `filesById is not defined` (HIGH for the scenario, pre-existing — claimed, verification pending)

- Cluster: `event_loop` | Regression vs 0.9.11.post1: no (both fail; 0.9.11.post1 fails earlier, in the handler slot)
- Repro: `event_loop/elapp` page `/callback`: `rx.toast("...", action={"label": "Upload", "on_click": CB.handle_upload(rx.upload_files(upload_id="u2"))})`
  fired from a frontend trigger, and `rx.call_script("1", callback=lambda v: CB.handle_upload(rx.upload_files(upload_id="u2")))`;
  select a file in the `u2` zone, click the action. Console: `ReferenceError: filesById is not defined`; no upload
  request; `uploaded` stays empty (`out/callback.txt` cases 6, 8, 9; `out/callback.errors.txt`).
- Mechanism: the compiled event is now `ReflexEvent("...cb.handle_upload", {...}, {}, "uploadFiles")` — the #7156
  ordering fix is real — but the payload emits `files: filesById?.["u2"]`, and `const [filesById, setFilesById] =
  useContext(UploadFilesContext)` is hoisted only into the component that renders `rx.upload`; a toast action or a
  `call_script` callback runs outside it. Either propagate the hook/VarData to the callback site or reword the
  changelog line ("handlers like `uploadFiles` never ran") — as shipped, the headline case does not work end to end.

## FINDING-016: cancelled foreground `supersedes=True` handler loses pre-cancellation writes under redis (MEDIUM — claimed, verification pending)

- Cluster: `event_loop` | Regression: unknown (dev/memory matches on both versions; a 0.9.11.post1 prod+redis run
  was not done) | Repro: `elapp` page `/supersede`, handler `frefresh` (foreground, appends `F{tag}:start`, `yield`,
  `await asyncio.sleep(2)`, appends `:done`); fire A then B within 2 s. Dev/memory: `["FA:start","FA:CANCELLED",
  "FB:start","FB:done"]`. Prod + redis (9 workers): `["FB:start","FB:done"]` — `FA:start` never reaches the client or
  redis despite the `yield` before the sleep (`out/supersede.txt` vs `out_prod/supersede.txt`, two consecutive runs).
  The background variant and non-cancelled foreground handlers keep their writes.
- Mechanism guess: with redis the state is written back when the event's `modify_state` context exits normally; a
  foreground handler cancelled mid-`await` (CancelledError propagates) does not flush, so the pre-cancellation
  mutation and its emitted delta are lost together.

## FINDING-017: backend port stays bound and swallows connections when the worker cannot serve (HIGH, regression — claimed, verification pending)

- Cluster: `dev_server_cli` | Regression vs 0.9.11.post1: **yes**, baselined in both directions
- Repro: `dev_server_cli/scripts/sigterm_port_probe.py <venv> <dsc dir> <FP> <BP> <tag> <logdir>` on both venvs. After
  `kill -TERM <reflex pid>` (which neither version acts on — FINDING-018), 0.9.12a1: `/ping` → `TIMEOUT_NO_REPLY_6s` at
  +8 s and +18 s (`logs/portprobe_new.json`); 0.9.11.post1: `CONNECTION_REFUSED` immediately (`logs/portprobe_prev.json`).
  Second route to the same state: a module that raises at page-evaluation time during dev — `/ping` blocks for the
  full client timeout instead of refusing (`shots/reloaderr_new_events.json`), then 200 after the fix.
- Mechanism: #7114 moved the listening socket into the granian supervisor so it stays bound while a worker is
  replaced (which works as designed: 623 pings at 20 Hz across a live hot reload, 0 refused, max 166 ms). When the
  supervisor is wedged or the worker cannot come back, the accept queue swallows connections with no worker to
  serve them. Suggested shape: a give-up/timeout path in the supervisor (refuse or 503 after N seconds without a
  worker) rather than reverting #7114. This is also what made the `ent_map_dnd_flow_mantine` "hot reload does not
  recover" lead look real: the worker DOES recover after the source is fixed; the server merely looked dead because
  requests hung instead of failing fast.

## FINDING-018: `reflex run` ignores SIGTERM/SIGINT sent to its pid alone (MEDIUM, pre-existing — claimed)

- Cluster: `dev_server_cli` | Both versions: `exit_code=TIMEOUT_30s`, survivors reflex+bun+node, ports bound
  (`logs/sigres_N1_new_dev_TERM_proc.json`, `logs/sigres_P1_prev_dev_TERM_proc.json`); the process-GROUP signal exits 0
  in 0.2 s on 0.9.12a1 with no "exit code 143" line (#6981 verified for that path) but logs `[ERROR] Unexpected exit
  from worker-1` on the clean stop. Repro: `scripts/signal_test.py <venv> <dsc dir> L TERM proc <logdir> <FP> <BP>`
  (the `.sh` version in the same dir is superseded — it signalled the `setsid` wrapper).
- Impact: `docker stop`, systemd and `kill <pid>` never terminate a dev server; combined with FINDING-017 the port
  then hangs instead of refusing. Prod-mode signal handling was not exercised (out of timebox).

## FINDING-019 … FINDING-022 (`build_prod_export`; claimed, details in `build_prod_export/NOTES.md`)

- FINDING-019: `head -c 64 /dev/urandom > .web/backend/stateful_pages.json`, then `reflex run --env prod --backend-only`:
  `UnicodeDecodeError` traceback (`logs/be_s3_garbage.log`), `Unexpected exit from worker-1`, nothing binds the port,
  and every later start fails the same way because the marker is left in place. Truncated JSON, a missing marker and
  a 4-worker cold start all rebuild cleanly, and `reflex compile --dry` leaves markers byte-identical — the fix works
  except for this input. Root cause: `Path.read_text()` decodes before `json` sees anything;
  `reflex/compiler/compiler.py::_read_stateful_pages_marker()` catches `JSONDecodeError` but not `UnicodeDecodeError`.
  One-line fix (catch `ValueError`/`OSError`, or read bytes).
- FINDING-020: `@rx.dynamic def widget(state: DynState)` rendering `rx.icon(tag=state.tag)`; flipping `tag` updates a
  plain `rx.text(DynState.tag)` and the websocket delta carries `tag_rx_state_`, but the dynamic component keeps
  rendering the old icon in dev, backend-only prod and on 0.9.11.post1 (`out/backend_only_0912a1.json`).
- FINDING-021: `rx.image(src="/components/logo.svg")` under `frontend_path="/app"` requests `/components/logo.svg`
  (404) while `/app/components/logo.svg` serves 200; identical on both versions. Either prefix root-relative literal
  asset paths at compile time or document that `rx.asset()` is required with `frontend_path`.
- FINDING-022: `/app/` 1 177 996 → 1 243 249 B (+65 253), `/app/about` +3.7%, `/app/components` +5.4% decoded JS with
  the flag on: fewer requests (17 → 14 files) but a single `esm-*.js` module ~65 KB larger than the shiki/icon chunks
  it displaces. Direction consistent across all three pages; caveat: Playwright `response.body()` bytes on one app.

## FINDING-023 … FINDING-025 (`render_ctx_statemgr`; all pre-existing, details in `render_ctx_statemgr/NOTES.md`)

- FINDING-023 (standing HIGH from the previous campaign): `renderapp` with `RENDERAPP_EXTRA_STATE=1` defines a backend
  state class the compiled frontend does not know about; the hydrate delta names it, `.web/utils/state.js` sets
  `backend_state_mismatch = true`, and both the socket `event` handler and `processEvent()` return early forever:
  `A_after_load='0'`, `sent_frames_from_clicks=0`, same after reload (`out/mismatch_new_result.json`,
  `out/mismatch_prev_result.json`). A one-way latch with no reset path; #6181 moved dispatcher registration into a
  `useLayoutEffect` with `delete` on unmount but left the latch. Realistic trigger: a stale `.web/` after adding a
  State class with the frontend compile skipped (backend-only workers, `nocompile`).
- FINDING-024: `_split_substate_key` partitions the legacy token on `_`; a bare UUID yields an empty state path and
  `get_class_substate` rejects `['']`. The deprecation warning fired just before names the right format, but the API
  route gets a bare 500 (`evidence/modify_state_legacy_token_traceback.txt`).
- FINDING-025: `reflex/reflex.py::_run` calls `reset_disk_state_manager()` unconditionally before the app starts;
  after a clean SIGTERM flush wrote six pickles, the next `reflex run --env prod` left `.states/` empty
  (`logs/disk_verify.log`). Reasonable in dev (stale schema), surprising for prod disk-backed state.

## FINDING-012: `rx.data_editor` image-preview overlay dead in prod with the default badge (HIGH impact, pre-existing — claimed, verification pending)

- Cluster: `components_bumps` | Regression vs 0.9.11.post1: no (identical `root.jsx` nesting on 0.9.11.post1) |
  Newly relevant: #7081 advertises native image cells and PR #7081 "opens Glide Data Grid's built-in image
  preview", and that preview cannot open in production for any app that has not set `show_built_with_reflex=False`.
- Repro: `components_bumps/gallery` page with a `type="image"` column, `reflex run --env prod --frontend-port 3301
  --backend-port 3301`; click an image cell. Console: `Cannot open Data Grid overlay editor, because portal not
  found. Please add <div id="portal" /> as the last child of your <body>.`; `document.getElementById("portal")` is
  null. Dev (no badge): the carousel opens (`shots/dev-editor-overlay.png` vs `shots/prod-editor-overlay.png`).
- Mechanism (explorer): `reflex_components_dataeditor/dataeditor.py` registers `{(-1, "DataEditorPortal"):
  Portal.create(id="portal")}` as an app wrap; `reflex/compiler/compiler.py:1356` adds `app_wraps[0, "StickyBadge"]`
  in prod when `show_built_with_reflex` is on; the badge wrap ends up the parent of the portal wrap and does not
  render its children, so the portal div never reaches the DOM. Setting `show_built_with_reflex=False` restores it.
- Verifier (independent fresh app, `components_bumps/verification/`): prod default → `portal_exists=false`, badge
  present, double-click yields no overlay and the quoted console error; same prod build with
  `show_built_with_reflex=False` → `#portal` exists and the carousel opens ("1 of 2", arrows, dots). A real
  0.9.11.post1 prod server fails identically with byte-identical `root.jsx` nesting, so not a regression — but
  0.9.12a1 is the version that ships the carousel CSS (40 rules vs 0), i.e. #7081 ships styling for an overlay
  production cannot open. Blast radius: every data_editor overlay cell editor in every default-config prod app;
  `(-1, "DataEditorPortal")` is the only negative-priority app wrap in the train.
- Root cause (verifier): `reflex/app.py:1574-1590` (`_app_root` sorts wraps descending and appends each
  lower-priority wrap as a CHILD of the previous one) + `reflex/app.py:1639-1649` (`_setup_sticky_badge` registers
  `app_wraps[0, "StickyBadge"]`) + `reflex/compiler/compiler.py:1347-1356` (badge added in prod when
  `show_built_with_reflex` defaults True) + `reflex_components_core/core/sticky.py:90-107` (`StickyBadge.create`
  accepts no `*children` and the compiled `memo(({}) => …)` never reads `props.children`).
- Shape of fix: make the StickyBadge wrap forward its children (or register the portal so it stays a sibling).
  At minimum the #7081 docs need the `show_built_with_reflex=False` caveat.

## FINDING-004, FINDING-006 (LOW; CONFIRMED by the verifier, details in the cluster NOTES)

- FINDING-004 (`router_vars`, ISSUE 1; CONFIRMED, diagnosis corrected by the verifier): `@rx.var(deps=["router"])`
  with a body that reads `self.router` (the default `auto_deps=True` case) raises no deprecation warning; the
  guard at `reflex/state.py:1205-1221` tests `dvar_set.isdisjoint(ROUTER_VARS)` on the dep set that
  `ComputedVar._deps()` returns, and `reflex_base/vars/base.py:2876-2895` seeds the dependency tracker with the
  very set objects from `_static_deps`, so the auto-detected `rx_router_*` names are merged in place and the
  legacy string becomes indistinguishable from the Var form. The guard DOES fire for `auto_deps=False`, and for
  bodies that do not read the router (`router_vars/verification/scripts/v_deps_legacy_matrix.py`). Fix at
  declaration time (`_add_static_dep`), not after `_deps()`. Repro: `router_vars/scripts/deps_legacy.py`.
- FINDING-006 (`router_vars`, ISSUE 3; CONFIRMED, pre-existing): `class P(rx.State): _priv: int = 1` /
  `class C(P): _priv: str = "x"` raises nothing on either version; `C.backend_vars["_priv"]` is the parent's
  and in a real state tree the child's default is discarded and writes go to the parent
  (`verification/scripts/v_backend_shadow_tree.py`). `_check_overridden_inherited_vars` skips `_`-prefixed
  names at `reflex/state.py:1335`; a fix must restrict itself to `inherited_backend_vars`.
- (FINDING-007 refuted — see the refuted list.)

## FINDING-008 (`memo_aschild`; CONFIRMED low, pre-existing; FINDING-009/010 refuted — see the refuted list)

- FINDING-008: `/triggers` page — `rx.button(on_click=TrigState.bump("dropdown"))` inside `rx.dropdown_menu.trigger`
  opens the menu but never runs the handler; dialog/popover/tooltip/hover_card triggers run both. Identical
  on 0.9.11.post1. Evidence: `memo_aschild/logs/dev_probe_evidence.log`, `shots/dev/dropdown.png`.
- (FINDING-009 and FINDING-010 refuted/reclassified — see the refuted list.)

## Refuted / reclassified claims

- **FINDING-005 — "any computed var reading the router is invalidated by all five fields; a narrow `deps=` cannot
  narrow" (`router_vars`)**: refuted by the verifier. The measurement is accurate (auto-deps through the composed
  `State.router` Var record all five fields, by design), but `@rx.var(deps=[State.router.url], auto_deps=False)`
  registers only `rx_router_url` (`router_vars/verification/scripts/v_narrow_deps.py`); `deps=` has always been
  additive unless `auto_deps=False`; the 0.9.11.post1 baseline was strictly coarser (everything depended on the
  single `router` var); and the −47% (whole websocket frame) vs −67% (router-only delta) numbers measure different
  things. Not a defect; at most a future optimisation of auto-dep tracking through composite Vars.
- **FINDING-014 — "#7124's suggested import path fails" (`components_bumps`)**: refuted by the verifier. The
  changelog says `reflex.components.datadisplay.code`, a module path; `import reflex.components.datadisplay.code`
  (and `from reflex.components.datadisplay.code import CodeBlock`) work on both versions. The `from
  reflex.components.datadisplay import code` spelling fails identically on 0.9.11.post1 because the lazy loader
  lists attributes, not submodule names — optional loader polish, not a release item.
- **FINDING-007 — "#7136's documented `REFLEX_STATE_ALLOW_RESERVED_NAMES` escape hatch is missing" (`ent_mcp_oidc`)**:
  refuted as a defect by the verifier. The greps are right (the name exists nowhere in the wheels or on the release
  branch), but the flag is promised only in PR #7136's description; the merged PR's user-facing text
  (`news/+reserved-state-names.breaking.md`, the `docs/state/overview.md` paragraph) and the changelog never mention
  it, so nothing shipped is inconsistent — and the metaclass is installed unconditionally, so the flag would not have
  rescued FINDING-001. Note for the release manager only.
- **FINDING-009 — "`rx.cond` evaluates both branches eagerly; a throwing untaken branch fails the prod build"
  (`memo_aschild`)**: refuted by the verifier with a minimal app (`memo_aschild/verification/app_boomy`): an
  `@rx.memo` component containing the throwing Var and an idiomatic `rx.text(S.user["name"])` with `user=None` both
  render "not exploded" with zero console errors in the untaken branch; only a raw `rx.Var("undefined_global_thing.nope")`
  literal is inlined verbatim into the parent JSX (`jsx(RadixThemesText, {as:"p"}, undefined_global_thing.nope)`),
  so it is evaluated as any JS argument would be. The prod prerender failure is byte-identical on 0.9.11.post1.
- **FINDING-010 — "`on_submit` form data carries id-keyed duplicates and `None` entries" (`memo_aschild`)**:
  reclassified as intentional API. `Form._get_form_refs()` (`reflex_components_core/el/elements/forms.py:359-380`,
  "Send all the input refs to the handler") emits `getRefValue(ref_<id>)` for every ref in the form subtree and
  merges them over the real `FormData`; identical on 0.9.11.post1. Only apps that put `id=` on non-field elements
  inside a form see the extra keys. Cleanup ticket at most.

## Cluster summaries

### `smoke` (pass 6, anomaly 0, fail 0)
Blank app on the published train: `reflex init` clean; dev server 200 in 10 s with reflex's own Bun 1.4.0;
prod build served in 4 s; zero console/page/network anomalies in both modes; generated `package.json`
carries react-router 8.4.0, mergician v2.0.2, isbot 5.2.2, lucide-react 1.26.0. `smoke/NOTES.md`.

### `packaging` (pass 6, anomaly 1, fail 0)
19/19 packages published; 122 stubs identical in wheel and sdist; pins match the changelog
(`reflex-base==0.9.12a1`, `moment>=0.9.4`); identical all-alpha resolution on Python 3.10–3.14;
third-party import surfaces resolve. Anomaly (pre-existing, issue #7088): the reflex sdist cannot be
built by uv because it still carries the workspace `[tool.uv.sources]`; pip installs it fine.
`packaging/NOTES.md`.

### `orch_probes`
Enterprise import sweep (FINDING-001), framework-only metaclass repro, build-sdk rename/URL precedence,
hosting-cli non-interactive defaults. `orch_probes/NOTES.md`.

### `orch_pymatrix` (pass 3, anomaly 0, fail 0)
The train on Python 3.10, 3.14 and 3.15.0rc2: install, import, `reflex init`, dev server and a Chromium page load all
clean; the lazy loader's native PEP 810 path is active on 3.15 (#6930 provisional support holds); 3.10 prints its
deprecation notice. `orch_pymatrix/NOTES.md`.

### `orch_startup` (pass 1, anomaly 0, fail 0)
#7049 relative baseline on the `dev_server_cli` probe app, backend-only, three cold starts each: time to `/ping`
0.67/0.45/0.46 s on BOTH versions, RSS 109–123 MB on both. No difference — but that app has no optional heavy
libraries installed for #7049 to defer; `db_optional_imports` measured the intended scenario (heavy libraries
installed but unused) and found the claimed savings. `orch_startup/NOTES.md`.

### `orch_otel` (pass 4, anomaly 0, fail 0)
reflex-otel 0.1.0 on 0.9.12a1: the initial dev compile worker now exports the complete `reflex.compile`
`trigger=initial` tree (3 stage children, 0 orphans) on a first and a second run; `hot_reload` and `export`
trees complete as well. #7155 verified; the previous campaign's FINDING-028 (issue #7095) is fixed.
`orch_otel/NOTES.md`.

### `router_vars` (pass 17, anomaly 3, fail 2, skipped 2) — #7068 verified, 3 low issues
`routerlab`: 5 pages, every router dependency form, substate/ComponentState/memo/client_state consumers,
24-step Playwright matrix with websocket-frame capture in dev, prod, memory/redis/disk state managers, two
tabs and two contexts. The navigation-delta matrix matches PR #7068's table exactly in dev and prod; the
URL persists once in redis and disk pickles; a 0.9.11.post1 → 0.9.12a1 redis upgrade discards old pickles
with no traceback; whole-frame navigation delta −47%. #7077/#7136 negatives raise clear errors where
0.9.11.post1 was silent or crashed with `KeyError: '__module__'`. Issues: FINDING-004/005/006. Unverified
rows: reconnect → session-only delta (socket.io ping timeout too long to force a reconnect), custom headers
(Playwright cannot inject websocket-handshake headers). Prod anomalies (dynamic-route direct-load 404 +
trailing-slash rewrite; "Page X is being redefined" warnings) handed to `build_prod_export` for baselining.

### `ent_mcp_oidc` (pass 6, anomaly 6, fail 7, skipped 2) — FINDING-001 is a total enterprise break
Reused the previous campaign's harness (mcpapp, authapp, fake OIDC IdP with PKCE/refresh/logout, MCP
drivers) on 0.9.12a1 + rxe 0.9.5 vs 0.9.11.post1. Root-caused FINDING-001 and measured its blast radius
(MCPPlugin-only, AuthPlugin-only and `demos/oidc` all die at startup). With a test-only shim the whole MCP +
OIDC surface passes end to end (anonymous token, 401/WWW-Authenticate, initialize/tools/resources,
queue_event into root/sibling/nested/background handlers, every `reflex://` resource, OAuth 2.1 metadata,
browser login/reload/second tab/logout) with no page errors or 4xx/5xx. Found FINDING-003 (withheld
uncached var never re-sent) and FINDING-007. Behavior changes recorded as not-bugs: the MCP resource
surface now lists `rx_router_*` as separate vars; MCP-originated events carry a real client token
(improvement); uncached vars of untouched substates no longer ride along (the intended half of #6946).

### `memo_aschild` (pass 29, anomaly 5, fail 0, skipped 1) — all seven changes verified, no regression
Seven-page app (`memoaschild`), four Playwright drivers, a compile-timing harness; dev, prod and 0.9.11.post1
baselines. #6850: Slot props/refs/class/style reach auto-memoized inputs under `rx.form.control(as_child=True)`
and submitted form data now carries them (baseline drops `name`/`aria-describedby` and the values). #7176: a
`@rx.memo` containing `rx.upload` crashes the WHOLE page on 0.9.11.post1 (`TypeError: useContext is not a
function`, default error boundary takes over) and works on 0.9.12a1 in all three variants (memo, memo-in-memo,
memo under a ComponentState) with real file delivery. #7130: no `Invalid DOM property` errors from the error
boundary's SVG. #7133: no `force_match` without `match`. #6708: svg `defs`/gradients paint at top level, in
`rx.foreach` and in a memo. #7122: 200 call sites sharing handlers dispatch the right args; throttle/debounce/
stop_propagation do not leak; one handler on two triggers works. #7121: median python-side compile of a
~500-component page 0.582 s → 0.493 s (~15%). Pre-existing defects recorded as FINDING-008 (confirmed) and two claims the verifier refuted (009, 010). Note:
`rx.form.control` only accepts TextFieldRoot/DebounceInput children (both versions), so the other controls
were exercised as direct field children.

### `ent_aggrid` (pass 16, anomaly 2, fail 6, skipped 2) — NO regression; 0.9.12a1 fixes a 0.9.11.post1 dev outage
reflex-enterprise 0.9.5 ag_grid demo (17 routes, the previous campaign's patched copy) and reflex-examples
`ag_grid_finance` on 0.9.12a1 dev + prod and on 0.9.11.post1, driven route by route with the previous
campaign's Playwright drivers plus a new router-navigation driver with websocket capture. **On the current
stable 0.9.11.post1 the demo has no backend at all**: the granian dev worker dies in `_compile_initial_state`
serializing `FormatterState.cols_defs` (rxe `LiteralLambdaVar` → "Library @radix-ui/themes is not bundled"),
while `reflex run` still prints "App running at" — 10/17 routes show 0 rows and `/editable` toasts a websocket
error (`ent_aggrid/artifacts/prev_0911post1_worker_crash.txt`). On 0.9.12a1 the worker starts, the 17-route
sweep logs 0 backend exceptions, all routes render data, the `@rx.memo` row counter survives a reload, and the
prod sweep diffs to zero against the previous campaign's prod run (#7096/#7049 fix confirmed). The #7068 router
split works through the demo's `State.router.page.path`-bound nav select (direct load, redirect, link nav,
back/forward; 527-byte navigation delta vs a 20 162-byte first event); #6850's `mergeSlotProps` in every
ag-grid wrapper caused no render/ref/gridApi breakage; `ag_grid_finance` is byte-identical on both versions.
The six "fail" rows are all pre-existing and downstream: the shipped demo's stale `$/utils/components` bundle
path, the ModelWrapper datasource URL percent-encoding `?` (every `/model*` fetch 404s — that code path has
never loaded a row in any campaign), ag-grid 34.3.1 vs ag-charts 11.2.4, `column_def()` silently dropping
unknown kwargs (kills row selection in `ag_grid_finance`), and the `CachedVarOperation` AttributeError still
masked as `VarAttributeError` with no `__cause__` (reflex-dev/reflex#6978). Caveat carried from the agent: the
dev route-by-route A/B against 0.9.11.post1 is not possible because the baseline backend never comes up; the
no-regression call rests on the prod A/B (valid, diff zero) and on the previous campaign's 0.9.11a1 dev sweep.
Process note: this agent ran `pkill -f "reflex run"` once around 01:50 UTC before switching to pid-scoped kills;
`memo_aschild` and `ent_map_dnd_flow_mantine` were running at the time and reported no unexplained server death.

### `ent_map_dnd_flow_mantine` (pass 10, anomaly 6, fail 3, skipped 3) — FINDING-001 widened, FINDING-011 found
Six rxe 0.9.5 demos on 0.9.12a1 vs 0.9.11.post1. An offline compiled-JS differ (`scripts/compile_dump.py`,
compiles any app in-process on either version without bun or the licence gate) diffed all 12 builds: no dropped
or duplicated hooks/imports (the #7015/#7198 risk). Browser drives: dnd 18/18, flow 11/11 + 9/9, map 13/13,
mantine `/dates` 52/52 — 0 page errors, 0 non-benign console messages, 0 4xx/5xx. A purpose-built mantine
`/qa-slot` page combining #6850 and #7068 with State vars, `client_state`, `@rx.memo`, `rx.foreach`/`rx.cond`,
an event chain, a background task, SPA navigation and hard reload: 13/13. Failures: the tickets demo cannot
start (FINDING-001 via `EventHandlerAPIPlugin.post_compile`), the pure-reflex metaclass repro, and the
redaction no-op (FINDING-011). Skipped: highcharts browser drive (compiled-JS diff only), tickets REST/OpenAPI
(blocked), and prod for every demo — `reflex run --env prod`/`export` are refused by rxe's paid-tier gate for an
anonymous tier and the agent declined to bypass it with reflex's `APP_HARNESS_FLAG` (the previous campaign did;
a policy call for the team). Anomalies worth a line: dev hot reload did not recover after an app-module error
(worker exited permanently; handed to `dev_server_cli` to baseline); `rx.form.control` rejects non-Radix
children so #6850 cannot be exercised with third-party widgets through it; OSM tile requests blocked by the
sandbox proxy (environmental).

### `components_bumps` (pass 31, anomaly 7, fail 2, skipped 1) — component train verified; FINDING-012/013/014
Nine-page gallery on a dedicated venv (train + plotly/pandas/httpx), driven in dev and prod with console/
network/screenshot capture, 0.9.11.post1 baselines where a fix is claimed. Verified: `sankey_chart` (static,
State-driven, custom node/link renderers with per-link `use_id` gradients, in `rx.foreach` and `@rx.memo`);
`use_chart_width` (undefined outside a chart, reacts to viewport resize); plotly `divId` (literal, State var,
foreach); sonner toast action/cancel callbacks from frontend triggers, memo, ComponentState, foreach, backend
yield and background tasks (no `queueEvents` ReferenceError anywhere); code-block copy button (`aria-label`
"Copy code", `type="button"`, clipboard works, the enclosing form's counter unaffected, readable code in prod
SSR HTML); badge `aria-label` at 360 px; controlled 400s on unknown/missing upload handlers; the tightened
`datadisplay` namespace. #6833 confirmed at the render level: 0.9.11.post1 emits `wrapperStyle:{strokeDasharray}`
/ `wrapperStyle:{tickFormatter}`, 0.9.12a1 emits the real props, and the browser shows dashed reference lines and
formatted ticks. Issues: FINDING-012 (portal swallowed by the badge wrap in prod), FINDING-013 (`use_id` in
foreach), FINDING-014 (changelog import path). Anomalies: `Axis.tick_formatter` accepts only a literal string
(a function Var raises `TypeError`); prod redirects extensionless routes 307 → trailing slash; `rx.el.svg`
presentation props (`stroke`, `text-anchor`) become emotion styles rather than attributes; the error boundary's
SVG attribute casing changed to camelCase between core 0.9.9 and 0.9.10a1 without a changelog line; one
unreproducible 404 console error in a single prod run.

### `event_loop` (pass 26, anomaly 5, fail 2, skipped 1) — #6946/#7168/#7145/#7157/#7187 verified; FINDING-003 confirmed, 015, 016
Six-page `elapp` plus a websocket-frame-capturing Playwright harness (`scripts/wsdrive.py` + per-scenario drivers),
run in dev, in prod with redis and 9 granian workers, and as a full 0.9.11.post1 baseline. #6946 dedupes
constant/derived/alternating/NaN/list/async/substate uncached vars, is per-client-token correct across browser
contexts, survives hard reload (hydrate uses `dict()`) and redis multi-worker, and cuts inbound websocket bytes
26 059 → 15 274 (~42%) on the same click sequence; events that change nothing send no frame. #7168 passes all
eight supersession shapes while the baseline fails three (cross-chain child cancellation, poll-loop restart,
stale-late-enqueue). #7145: 3000 self-chained ticks, zero RecursionError in dev, prod and baseline logs. #7157 fixes
every frontend-fired toast action/cancel shape (plain, `@rx.memo`, `ComponentState`) that threw `queueEvents is
not defined` on 0.9.11.post1. #7187: one redis connection per worker, flat over 600 `/_health` probes. Issues:
FINDING-003 (confirmed, pure reflex), FINDING-015, FINDING-016. Anomalies worth a line: an `on_load`-started
self-chaining loop is not cancelled on client disconnect and logs `Attempting to send delta to disconnected client`
once per tick (44×; pre-existing family) — and those undelivered deltas ARE recorded as sent by #6946's memo, safe
only because reconnect re-hydrates via `dict()`; the `_UNKEYABLE_VALUE` branch of `_delta_value_key` is dead
(reflex's `json_dumps` never raises, unserializable values become `null` and key identically); dict KEY ORDER
defeats the dedupe (digest of the JSON text); every uncached var is re-sent once right after hydrate (`hydrate`
emits `dict()` without recording, so the following `on_load_internal` frame carries all of them).

### `vars_typing` (pass 24, anomaly 6, fail 0, skipped 2) — all eight changes verified, no defects
Five-page `vtapp` plus seven repro scripts on a dedicated venv (train + pydantic 2.13.5 + pyright 1.1.414), dev and
prod in Chromium, six of eight changes baselined on 0.9.11.post1. #7015: the same-value/different-metadata
f-string case silently drops a hook+import on 0.9.11.post1 and keeps both on 0.9.12a1. #7189: an `Annotated`
pydantic discriminated-union state var cannot even be class-defined on 0.9.11.post1; on 0.9.12a1 it renders,
`rx.match`es and switches Cat↔Dog at runtime in dev and prod. #7198: 40 000 var operations leave 80 006 stale
`_global_vars` entries and ~78 MB RSS on 0.9.11.post1 vs 0 on 0.9.12a1; the touched operations are 1.53×–3.77×
faster and the untouched ones ~1.0×. #7115: a serializer typo surfaces as a chained `ReflexRuntimeError` naming the
user's frame (prev: `VarAttributeError` / `TypeError` / `RecursionError`). #7131: `EnvVar[timedelta]` parses every
documented form and rejects bad input with a useful message — but no shipped env var uses it yet (the open PR #7138
migrates them), so the changelog line reads as if an existing variable changed. #6930: lazy attribute access 20×
faster (0.049 s vs 0.986 s per 1e6). #7080: the markdown union props type-check under pyright where prev errors.
#6923: State-var page titles/descriptions update live in dev and prod and are carried in the prerendered HTML (no
0.9.11.post1 baseline). Skipped: Python 3.10/3.14/3.15 runs (closed by the orchestrator's `orch_pymatrix` probe).
Anomalies worth tickets, all pre-existing: a missing app-package `__init__.py` makes the compiler emit
`vtapp___vtapp____state` while the backend emits `vtapp____state`, so every event silently no-ops with only a
browser console error and no server signal; `rx.Var.create(5)._replace(_var_data=...)` raises `TypeError:
dataclasses.replace() got multiple values` on both versions; prod logs "Page X is being redefined with the same
component" once per page (same code on both versions — the third cluster to see it); the blank template's
`og:image` points at a `favicon.ico` that does not ship (prod 404). Changelog note: #7115 also changes
`hasattr`/`getattr(var, name, default)` on a broken var from returning False/the default to raising (in the PR body,
not the changelog). Environment: `--prerelease=allow` pulls pydantic 2.14.0b2 — pin `pydantic<2.14` in test venvs.

### `up_examples_b` (pass 17, anomaly 3, fail 1, skipped 3) — no upgrade regression on the db/auth/third-party apps
form-designer (`reflex[db]` + reflex-local-auth 0.5.0), twitter (`reflex[db]`), basic_crud (`reflex[db]` + mounted
FastAPI), reflexle (reflex-global-hotkey 1.2.3) and data_visualisation (pandas → sqlite) baselined end to end on
0.9.11.post1 (register/login/create form, signup/tweet, CRUD via UI and API, keyboard Wordle, table load), then the
SAME venv upgraded in place with sqlite DBs, `.web/` and `reflex.lock/` preserved and re-driven: every flow still
works, rows survive, no new console/page errors or 4xx/5xx, and the preserved 0.9.11 `.web/` recompiled cleanly
despite the #7068 state-key rename. #6946 verified from websocket frames (an unchanged uncached var re-sent on
0.9.11.post1, omitted on 0.9.12a1); #7068/#7077/#7136 declaration errors fire as documented. Added a reusable
`/pandas` probe page to data_visualisation (DataFrame through a literal, a State-driven computed var, an `@rx.memo`
prop, a `ComponentState`, `rx.foreach` over sqlmodel rows). Issues: FINDING-004 (independently), and prod 404s for
dynamic routes (pre-existing on both, issue #6983 / PR #6996). Notes: a naive `uv pip install --upgrade
'reflex==0.9.12a1'` without `--prerelease=allow` upgrades only reflex/reflex-base and leaves every component
package at its stable release — it happened to work, but the release notes should tell users to name the
component alphas; form-designer's `/form/<id>` page crashes on both versions (an app bug in the example:
`rx.form.message` outside `rx.form.field`); three examples ship no alembic dir so `reflex db init/makemigrations/
migrate` is needed on both versions. Skipped for time: cold `.web` rebuilds for four apps, prod for three, redis.

### `up_examples_a` (pass 20, anomaly 5, fail 1, skipped 1) — no upgrade regression on the core-interaction apps
counter, todo, clock, upload, lorem-stream, snakegame: baseline on 0.9.11.post1, in-place `--upgrade` of the same
venv with `.web/` + `reflex.lock/` preserved, cold run, prod run — 24 app runs, each driven in Chromium, zero console
errors, page errors or ≥400 responses everywhere. Counter arithmetic + reload persistence, todo add/finish/reload,
clock's background tick with a timezone change mid-run and its `rx.Cookie` surviving reload, a two-file upload with
served bytes matching disk, three concurrent lorem-stream background streams surviving client-side navigation, and
snakegame's `GlobalKeyWatcher` (arrows/hjkl/Escape) all identical across phases. The first post-upgrade run recompiled
the 0.9.11-built `.web/` cleanly with no state/schema mismatch despite the #7068 key split; the lockfile migrated to
react-router 8.4.0; `reflex init` on snakegame exited 0 with no migration warnings. An added `/extras` page on counter
confirmed #6946 from the websocket frames, `rx.upload` inside `@rx.memo` (#7176), `client_state`, two
`ComponentState`s, an event chain into a background task, `rx.foreach`/`rx.cond`. Issues (both pre-existing or
cosmetic): the `upload` example's `@rx.var` file list never refreshes (cached var with no deps — an example bug on
both versions — verifier confirmed with a fresh-context control and validated the `cache=False` fix); the generated
`package.json` pins `"mergician": "v2.0.2"` with a leading `v` unlike every other dependency (new in this train —
verifier traced it to the literal at `reflex_base/constants/installer.py:151`; the string is only rendered into
`bun add mergician@v2.0.2`, bun resolves 2.0.2 with a recorded sha512 and the lockfile stays frozen-consistent, so
cosmetic; note the entry is written by the first run's install pass, not by `reflex init`). Notes: a cached `@rx.var` twin is still re-sent on every
delta when its dependency changes even if its value did not — matches #6946's `cache=False`-only wording but is
easy to misread; killing `reflex run` orphans the react-router dev process and keeps the frontend port bound (both
versions), which silently served a previous app in the agent's first pass — `scripts/run_app.sh` now sweeps ports.

### `up_examples_c` (pass 13, anomaly 5, fail 0, skipped 1) — no upgrade regression on the component/routing/custom-JS apps
local-component (full protocol: 0.9.11.post1 baseline, in-place upgrade with `.web/` preserved, cold rebuild, prod —
nine flows field-for-field identical across all four runs, zero console/page/network errors), quiz (baselined flow
for flow, identical incl. a pre-existing React checkbox warning), traversal (a 7×7 pathfinding grid with a
self-chaining async handler — ~42 iterations, no RecursionError, #7145) and nba (gridjs DataFrame table + two plotly
charts recompute under filtering, #7049; its upstream CSV host is proxy-blocked, stubbed with a same-shape local
file). Confirmed in the browser: #6850 (the id survives auto-memoization so `rx.scroll_to` works, identical scroll
offsets on both versions), the #7068 rename across an in-place upgrade (the preserved 0.9.11 `.web/` recompiles
silently to `rx_router_*`, no hydration/schema warning a user would see), #6977 (`id="scatter-chart"` reaches the DOM
as the `.js-plotly-plot` element and survives re-render and reload). Skipped for time: github-stats, linkinbio,
json-tree, overkey — the #6833 item this batch was to cover through github-stats is verified by `components_bumps`.
Upgrade-command nuance (settled by the verifier, who ran the no-flag control the explorer had only reasoned about —
`up_examples_c/verification/upgrade_resolution_dryruns.txt`): `uv pip install --upgrade --prerelease=allow
'reflex==0.9.12a1'` pulls the whole alpha train; WITHOUT `--prerelease=allow` the explicit `==0.9.12a1` pin still
resolves reflex and reflex-base (exact pin) but every component package stays at its stable release — the mixed
state `up_examples_b` observed. The explorer's "no alpha at all" conclusion was refuted; the checkbox warning claim
was confirmed as third-party dev-only noise (`@radix-ui/react-use-controllable-state`, identical on both versions, no
`checked` prop is emitted by either).
Anomalies (pre-existing): `SitemapPlugin ... enabled by default, but not explicitly added to the config` printed
five times per run on both versions; the quiz checkbox warning (app usage, no `checked` prop).

### `dev_server_cli` (pass 17, anomaly 5, fail 2, skipped 4) — CLI/dev-server changes verified; FINDING-017 (regression), 018
Probe app `dsc` (State, event chain, background task, `client_state`, `@rx.memo`, `ComponentState`, foreach/cond,
three pages incl. a dynamic route, a `modules_report` var exposing the worker's pid/`sys.modules`/RSS), an
`rxconfig.py` importing a sibling `settings.py` (#7075), `hrapp` wrapping a real local React package by directory
AND tarball (#7117), a blank app for the node-less test. Verified: #7089 (no `nocompile` after backend-only; an edit
between runs recompiles), #7114 (623 pings at 20 Hz across a live hot reload, 0 refused, max 166 ms), #7117 (both
specifiers intact and rendering; 0.9.11.post1 reproduces the `@masenf/hello-react@..` truncation), #7129 (`lockfile
had changes` gone across bun↔npm switches), #7202 (init + run with node/npm/bun stripped from PATH, no
`restartWithMergedOptions`; react-router family at 8.4.0), #7193 (every granian lifecycle line a JSON record — the
previous campaign's FINDING-016 is fixed; the only non-JSON lines are the app's own stdlib `logging` calls), #7152
(deprecations via `reflex.deprecation`, once per process), #7075 (sibling module imported once, no duplicate
registration), #7049 absolute numbers (backend-only `/ping` 200 in 0.85 s, 55–59 MB RSS, only `reflex.compiler` of
the probed heavy modules imported — relative baseline closed by the orchestrator's `orch_startup` probe). Issues:
FINDING-017, FINDING-018; plus (low) a clean group-SIGTERM stop logs `[ERROR] Unexpected exit from worker-1`, and one
`REFLEX_USE_NPM=1` run sticks the project on npm until `package-lock.json` is deleted from `.web/` and `reflex.lock/`
(re-grade of the previous campaign's FINDING-021: the failure is gone, the stickiness remains, undocumented).
Anomaly: `reflex cloud ... --json` emits its error path as plain text (hosting-cli 0.1.72, almost certainly
pre-existing). Not covered: prod-mode signal handling, `reflex export/init --json`, #7166 logging under `reflex run`.

### `build_prod_export` (pass 16, anomaly 5, fail 3, skipped 2) — #7153/#7078/#7165/#7112/#7096/#7142/#7139 verified; FINDING-019..022
One `frontend_path="/app"` app (routes `/`, `/apple`, `/app`, `/about`, `/components`, `/assets`, `/items/[id]`, `/dyn`;
asset dirs colliding with route names; markdown + shiki, memo cards, ComponentState, cond, dynamic `rx.icon`, an upload
handler setting inf/-inf/nan, background task, client_state, a `sys.modules` probe, a `@rx.dynamic` component-valued
var referencing a bundled lucide icon) driven across `reflex export`, `reflex run --env prod`, prod + lazy bundled
libraries, backend-only prod against a statically served export, dev, and a 0.9.11.post1 baseline. Verified: #7153
(`/app/apple`, `/app/components`, `/app/assets` are 200 prerendered pages; 404 on 0.9.11.post1); #7078 prerender/asset
coexistence, gzip sidecars (no `.br` because the default format list is `["gzip"]`), CSS preload link, sitemap namespace
with `/app`-prefixed URLs, rxconfig isolation from an empty dir; #7165 (no core-js in the export; inf/-inf/nan render as
Infinity/-Infinity/NaN with zero console errors); #7112 (backend worker `sys.modules` has no httpx/json5/sqlalchemy/
pandas); #7096 (`.web/backend/bundled_libraries.json` written with the bundled icon — absent on 0.9.11.post1 — and a
component-valued var hydrates in backend-only mode); #7142 (truncated/missing markers and a 4-worker cold start
rebuild with no leftover `.tmp`; `reflex compile --dry` leaves markers identical); #7139 (double `StarletteIntegration`
sentry init starts and runs). Baselined the `router_vars` leads: the prod 404 on a direct dynamic-route load, the
trailing-slash rewrite and the "Page X is being redefined" warnings (7 for 7 routes, even with only `@rx.page`) are all
identical on 0.9.11.post1 → pre-existing. Issues: FINDING-019/020/021/022. Not covered: the vite RSS half of #7112
(another agent's server shared the box), brotli/zstd compression formats, lazy-library load-failure retry. Tester
trap: `uv pip install --prerelease=allow sentry-sdk` resolves 3.0.0a7, which crashes in `sentry_sdk.init()` against
opentelemetry-api 1.44.0 before any reflex code runs — pin `sentry-sdk<3`.

### `render_ctx_statemgr` (pass 21, anomaly 8, fail 4, skipped 3) — #6181 and #7159 verified; #6180 not observable; FINDING-023..025
Render-count probe app (10 substates, memo sections, two ComponentStates, foreach over 300 rows, colour-mode and
event-loop consumers, LocalStorage/Cookie/SessionStorage, client_state, background tasks, event chains, a second page
and a dynamic route), a byte-identical 0.9.11.post1 copy, and a StateManagerDisk probe app with Starlette routes
exposing the manager's disk contents, cache and write queue. #6181: per-substate providers are real in the compiled
output and halve the on_load render count for the two substates an on_load touches (A/B/dual 2 vs 4 in dev); every
other scenario was already isolated on 0.9.11.post1 and is unchanged; prod replays the suite with exactly half the
dev counts (StrictMode). #7159: a debounced write flushes the LATEST of two different instances; a state never obtained
from `get_state` is persisted; `modify_state` from an API route pushes live and persists; state survives a hot reload;
the shutdown flush wrote at the SIGTERM second with a 30 s debounce. #6180: not contradicted but not observable — the
colour-mode and event-loop probes recorded 0 extra renders on 0.9.11.post1 too because they sit behind memo boundaries;
do not count #6180 as verified. #7132: FINDING-002 confirmed in one line (both a var and a computed var named
`_get_was_touched` raise; both allowed on 0.9.11.post1). Issues: FINDING-023/024/025. Anomalies: `BaseStateToken` vs
`StateToken` have different `cache_key`/`token_path()` shapes and using the wrong one silently writes a parallel state
tree; `REFLEX_API_URL` did not reach the compiled bundle for `reflex run --frontend-only` (which also rejects
`--backend-port`); SIGTERM to `reflex run` did not exit and SIGKILL orphaned the react-router process (FINDING-018);
the vite dev server was SIGKILLed at startup twice (`exit code -9`) under concurrent load — environmental. Skipped:
0.9.11.post1 prod baseline; redis half of #7132 (unreachable).

### `db_optional_imports` (pass 22, anomaly 3, fail 0, skipped 1) — #7049 and #7083 verified with numbers, no defects
Three apps on PyPI-only venvs: a SQLModel relationship app (Author 1-N Book, Book N-N Tag via a link table, sync
`rx.session` + async `rx.asession` with `selectinload`, relationship-bearing state vars, ObjectVar access through
relationships in `rx.foreach`, background tasks, event chains, dynamic model classes, custom serializers), a
pandas/Plotly/Pillow app (`rx.data_table`/`rx.plotly`/`rx.image` over DataFrame/Figure/Image state vars with
`@rx.memo`, `ComponentState`, `rx.cond`, and a background task performing the FIRST serialization), and a bare app for
db-extra-less CLI behavior. #7083: the guided "pip install reflex[db]" ImportError covers both the `table=True` and
plain-subclass paths (baseline: bare `TypeError`). #7049: with pandas/Pillow/Plotly/SQLModel/SQLAlchemy/alembic all
INSTALLED but unused, building the app loads NONE of them on 0.9.12a1 vs all seven on 0.9.11.post1 — `sys.modules`
1509 → 645, max RSS 133.0 → 46.5 MB, build 0.78 → 0.24 s (medians of 3; `scripts/startup_measure.py`) — this is the
scenario the changelog line describes, and it supersedes the orchestrator's `orch_startup` probe, whose app had no
heavy libraries installed to defer. Relationship payloads semantically identical to the baseline; database usage
accounting still counts direct-SQLModel apps without importing `reflex.model`; prod with 4 forked granian workers
served 20 concurrent browser contexts doing DB reads 20/20 with no hangs or registry tracebacks. Bonus fix confirmed:
on 0.9.11.post1 a later `import reflex.model` silently replaced a user's custom `@rx.serializer` for `SQLModel`;
0.9.12a1 preserves it (`scripts/serializer_override.py`). Issues: FINDING-026 (changelog wording); pre-existing lows:
`reflex db init` without the extra prints a raw ~20-line click traceback instead of the guided message;
`rx.asession()` with only `db_url` set raises `No async database url configured`, invisible client-side inside a
background task. Latent fragility noted: optional-library serializers are matched by identity against hard-coded
module paths (`pandas.core.frame`, `plotly.graph_objs._figure`, `PIL.Image`, `sqlmodel.main`) — a library reorg would
disable serialization silently. Skipped: reflex-local-auth (covered by `up_examples_b`).

_(other clusters pending)_
