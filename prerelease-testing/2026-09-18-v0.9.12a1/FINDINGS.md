# Findings — reflex 0.9.12a1 pre-release testing (2026-09-19)

Independent end-to-end exploration of the `r/pre-2026.09.18-35410916948` release train. All installs
PyPI-only in isolated uv venvs (never from a checkout); every sample app run for real (`reflex run`, dev
and prod) and driven in headless Chromium via Playwright with server-log / console / network / websocket
capture; claimed issues re-reproduced by independent adversarial verifier agents from the written repro
alone. Baselines against the previous stable, reflex 0.9.11.post1. Orchestrator + 15 explorer agents +
one verifier per cluster with claims (Opus 5, xhigh effort), two at a time.

**Campaign status: IN PROGRESS** — this file is updated as clusters finish. Sections marked _(pending)_
are not yet written.

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
- FINDING-001: State metaclass change breaks downstream metaclasses derived from `BaseStateMeta` — every reflex-enterprise 0.9.5 app using AuthPlugin OR MCPPlugin fails to start (CRITICAL, regression) — CONFIRMED (orchestrator + `ent_mcp_oidc` explorer; verifier pending)
- FINDING-002: the #7132 changelog entry describes behavior #7136 made unreachable — a `_get_was_touched` var is now rejected at class creation (LOW, changelog/behavior mismatch, maintainer decision)
- FINDING-003: a `@rx.var(cache=False)` withheld from a delivered delta by a downstream `get_delta` filter is never re-sent — #6946's last-sent memo is written while the delta is BUILT, not when it is delivered (HIGH, regression; reproduced in pure reflex by `event_loop` in dev and prod+redis, and through reflex-enterprise auth by `ent_mcp_oidc`) — CONFIRMED by two independent clusters; adversarial verifier pending
- FINDING-004: the documented `deps=["router"]` deprecation warning never fires — the guard in `_init_var_dependency_dicts` is dead code (LOW, new in #7068) — found independently by `router_vars` and `up_examples_b`; verification pending
- FINDING-005: any computed var reading `self.router` depends on all five router fields; a narrow `deps=[State.router.url]` cannot narrow; measured navigation delta −47% vs the PR's −67% (LOW, perf claim gap, #7068) — claimed by `router_vars`, verification pending
- FINDING-006: a substate shadowing a parent's backend (underscore) var is still silently ignored — #7077's guard covers base vars only (LOW, pre-existing gap) — claimed by `router_vars`, verification pending
- FINDING-007: PR #7136's description promises a `REFLEX_STATE_ALLOW_RESERVED_NAMES=1` escape hatch that does not exist in the published packages or the release branch (LOW, PR/migration-doc mismatch, maintainer decision) — claimed by `ent_mcp_oidc`
- FINDING-008: `rx.dropdown_menu.trigger` swallows its child button's `on_click` — the menu opens, the handler never runs; the other four Radix triggers compose correctly (MEDIUM, pre-existing, Radix pointerdown/dismissable-layer interaction) — claimed by `memo_aschild`, verification pending
- FINDING-009: `rx.cond` renders both branches eagerly, so a render-time throw in the untaken branch fails the prod build at the prerender step (`Prerender: Request failed for /boom/: 500`, exit 1); dev only shows the error boundary (MEDIUM, pre-existing shape; prod half not baselined) — claimed by `memo_aschild`, verification pending
- FINDING-010: `on_submit` form data carries id-keyed duplicates and stray entries (`the_form: banana`, `btn_submit: None`) besides the name-keyed fields (LOW, pre-existing) — claimed by `memo_aschild`, verification pending
- FINDING-012: the `rx.data_editor` overlay editor — the image-preview carousel that is the headline of #7081 — never opens in PROD when the "Built with Reflex" badge is on: the sticky-badge app-wrap nests the dataeditor's `#portal` wrap and drops it (HIGH impact on a headline feature, pre-existing nesting, trivially small to fix) — claimed by `components_bumps`, verification pending
- FINDING-013: `rx.vars.use_id()` inside an `rx.foreach` body returns one identical id for every item — duplicate DOM ids, every `html_for` label targets the first row (MEDIUM, new API in #6708, by-design limitation of hook-per-compiled-component that the docs do not warn about) — claimed by `components_bumps`, verification pending
- FINDING-014: the #7124 changelog's suggested path `reflex.components.datadisplay.code` fails in the `from reflex.components.datadisplay import code` spelling (`ImportError`); `import reflex.components.datadisplay.code` works (LOW, changelog wording) — claimed by `components_bumps`
- FINDING-015: #7156's headline scenario — a toast action or `rx.call_script` callback that triggers an upload handler — still fails: the handler slot is fixed but the payload's `filesById?.["u2"]` is only in scope inside the component that renders `rx.upload`, so the click throws `ReferenceError: filesById is not defined` and no upload starts (HIGH for the advertised scenario, pre-existing, changelog line misleading) — claimed by `event_loop`, verification pending
- FINDING-016: a cancelled foreground `@rx.event(supersedes=True)` handler loses its pre-cancellation state writes under prod+redis (dev/memory keeps them) — the `yield` before the `await` is not flushed when `CancelledError` propagates (MEDIUM, dev/prod divergence; 0.9.11.post1+redis baseline not measured) — claimed by `event_loop`, verification pending
- FINDING-011: reflex-enterprise's REST `redact_router_session()` became a silent no-op — it looks for the `router` key that #7068 removed from `state.dict()`, so server-generated `client_token`/`session_id` survive into REST responses and event deltas (HIGH, **security-relevant**, regression, cross-package; currently masked by FINDING-001) — claimed by `ent_map_dnd_flow_mantine`, verification pending

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

## FINDING-011: reflex-enterprise REST session-token redaction is a no-op after the router split (HIGH, security-relevant, regression — claimed, verification pending)

- Cluster: `ent_map_dnd_flow_mantine` | Regression vs 0.9.11.post1: yes (probe run on both) | Verifier: pending
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
- Shape of fix: make the StickyBadge wrap forward its children (or register it so the portal stays a sibling).
  At minimum the #7081 docs need the `show_built_with_reflex=False` caveat.

## FINDING-004 … FINDING-007 (LOW; claimed, details in the cluster NOTES)

- FINDING-004 (`router_vars`, ISSUE 1): `deps=["router"]` on a computed var raises no deprecation warning
  at class creation or app start; `reflex/state.py:1205-1219` guards on `dvar_set.isdisjoint(ROUTER_VARS)`,
  which is never true because the string dep is already resolved to the router Var carrying all five
  fields. Both changelog and PR promise the warning. Repro: `router_vars/scripts/deps_legacy.py`.
- FINDING-005 (`router_vars`, ISSUE 2): auto-deps through the `router` property record all five
  `rx_router_*` fields whatever the body reads, and an explicit narrow `deps=` does not suppress
  `_auto_deps`; measured whole-frame navigation delta 2535 B → 1334 B (−47%) vs the PR's −67% router-delta
  claim. Repro: `router_vars/scripts/deps_probe.py`, `logs/matrix_dev.txt`.
- FINDING-006 (`router_vars`, ISSUE 3): `class P(rx.State): _priv: int = 1` / `class C(P): _priv: str = "x"`
  raises nothing on either version; `C.backend_vars["_priv"]` is the parent's. `_check_overridden_inherited_vars`
  never sees backend vars. Repro: `router_vars/scripts/backend_shadow.py`.
- FINDING-007 (`ent_mcp_oidc`, ISSUE 3): `grep -rn ALLOW_RESERVED` over the installed 0.9.12a1 packages and
  `git grep` over the release branch find nothing, while PR #7136's description tells users to set
  `REFLEX_STATE_ALLOW_RESERVED_NAMES=1` for legacy handling until 1.0. Either ship the flag or fix the text.

## FINDING-008 … FINDING-010 (`memo_aschild`, all pre-existing on 0.9.11.post1; claimed, details in `memo_aschild/NOTES.md`)

- FINDING-008: `/triggers` page — `rx.button(on_click=TrigState.bump("dropdown"))` inside `rx.dropdown_menu.trigger`
  opens the menu but never runs the handler; dialog/popover/tooltip/hover_card triggers run both. Identical
  on 0.9.11.post1. Evidence: `memo_aschild/logs/dev_probe_evidence.log`, `shots/dev/dropdown.png`.
- FINDING-009: `rx.cond(BoomState.boom, rx.box(rx.text(rx.Var("undefined_global_thing.nope"))), rx.text("not exploded"))`
  with `boom=False` compiles to `jsx(Cond_comp_*, {}, <true>, <false>)`, both branches evaluated as arguments;
  the untaken branch throws on first render. Dev: error boundary. Prod: React Router prerender returns 500
  and `reflex run --env prod` exits 1. Evidence: `memo_aschild/logs/prod_server.trim.log`, `logs/prev_boom_probe.log`.
  A user's typo in a `rx.cond` branch that is never shown makes the whole site unbuildable — worth a maintainer's eye
  even though the shape is not new.
- FINDING-010: `/forms` submit yields the nine name-keyed fields plus one entry per element id and
  `'the_form': 'banana'` (the form's own id absorbing the select's hidden value). Byte-identical on 0.9.11.post1.

## Refuted / reclassified claims

_(pending)_

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
~500-component page 0.582 s → 0.493 s (~15%). Pre-existing defects recorded as FINDING-008/009/010. Note:
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

_(other clusters pending)_
