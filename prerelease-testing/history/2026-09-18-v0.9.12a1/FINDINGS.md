# Findings — reflex 0.9.12a1 pre-release testing (2026-09-19)

Independent end-to-end exploration of the `r/pre-2026.09.18-35410916948` release train. All installs
PyPI-only in isolated uv venvs (never from a checkout); every sample app run for real (`reflex run`, dev
and prod) and driven in headless Chromium via Playwright with server-log / console / network / websocket
capture; claimed issues re-reproduced by independent adversarial verifier agents from the written repro
alone. Baselines against the previous stable, reflex 0.9.11.post1. Orchestrator + 15 explorer agents +
one verifier per cluster with claims (Opus 5, xhigh effort), two at a time.

**Campaign status: COMPLETE (2026-09-19 06:00 UTC)** — 15/15 explorer clusters finished, all 14 clusters that raised
claims were re-run by an independent adversarial verifier from the written repro alone (`vars_typing` raised none),
and every numbered finding below carries its verifier's verdict. Process note: the fan-out was interrupted at
~03:00 UTC by the organisation's monthly spend limit after 10 of 15 explorers had finished; every adversarial
verifier and the remaining five explorers (build_prod_export, render_ctx_statemgr, dev_server_cli, up_examples_c,
db_optional_imports) died with the limit error. Both workflows were resumed from cache at 04:38 UTC once the limit
reset (completed agents replay, the failed ones re-run) and finished at 05:57 UTC.

**Re-verification status (2026-09-21): READY.** The fixes for FINDING-001/003/011/012/017 shipped as reflex 0.9.12a2 + reflex-enterprise 0.9.6a1; every original failing repro and a regression sweep were re-run against the published packages (96 pass / 0 fail / 2 skipped). Every deferred finding the maintainer wanted tracked was filed on
2026-09-22 as reflex #7244–#7266 (table in RELEASE_PLAN.md, "Issues filed for the deferred findings"). Verdict, table and
release conditions in
[Phase 7](#phase-7--re-verification-on-reflex-0912a2--reflex-enterprise-096a1-2026-09-21) at the end of this file.

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

> **Update 2026-09-21:** superseded. All four regressions and FINDING-012 are fixed in reflex 0.9.12a2 /
> reflex-enterprise 0.9.6a1 and re-verified end to end against the published packages (Phase 7, end of file).
> The recommendation is now **READY to release 0.9.12**, subject to publishing reflex-enterprise 0.9.6 no later
> than reflex 0.9.12 and a stock-install smoke after the finals publish. The text below is the 0.9.12a1
> assessment as written on 2026-09-19.

**Recommendation: do not release 0.9.12 from this train as-is.** Four regressions against 0.9.11.post1 were
confirmed by independent verifiers; two of them break the published reflex-enterprise 0.9.5 outright and one of
those is security-relevant. Everything else the train ships was exercised end to end and works, several items
measurably better than the previous stable.

What blocks (each confirmed by an adversarial verifier from the written repro alone):

- **FINDING-001 (CRITICAL, regression)** — `rx.State`'s new metaclass (`_StateMeta`, #7136) makes any metaclass derived
  from the public `reflex.vars.BaseStateMeta` unusable on a State subclass. reflex-enterprise 0.9.5 derives one for
  its OIDC state, so **every enterprise app using `AuthPlugin`, `MCPPlugin` or `EventHandlerAPIPlugin` dies at
  startup** (the MCP and REST plugins import the OIDC module from `post_compile`), the shipped `demos/oidc` and
  `demos/tickets` included. rxe 0.9.5 pins `reflex[db]>=0.9.6` with no upper bound, so a routine `pip install -U
  reflex` after release bricks deployed apps. Nothing in the changelog announces the metaclass change.
- **FINDING-011 (HIGH, security, regression)** — with #7068's router split there is no `router` key in `state.dict()`
  for reflex-enterprise's REST `redact_router_session()` to find, so `/_reflex/retrieve_state` and the event
  endpoint's ndjson deltas return the server-side `client_token`/`session_id` (confirmed over HTTP with the
  metaclass shimmed; blanked on 0.9.11.post1). Live the moment FINDING-001 is fixed against the published rxe 0.9.5.
- **FINDING-003 (HIGH, regression)** — #6946 records an uncached var as "sent" while the delta is built, so a var a
  downstream `get_delta` filter withholds is never re-sent: the client stays stale until the value changes again.
  Reproduced three ways (enterprise auth, pure reflex in dev and prod+redis, the verifier's own 60-line script).
- **FINDING-017 (MEDIUM, regression, dev-only)** — #7114's supervisor-owned socket keeps the dev backend port
  accepting connections while no worker can serve (a broken file saved mid-run, a wedged shutdown); requests hang
  for the client timeout where 0.9.11.post1 refused instantly. Self-healing, but it turns fast failures into hangs.

Worth fixing before release on the impact/trivial arm: FINDING-012 (the `rx.data_editor` image-preview overlay
that #7081 advertises cannot open in prod with the default badge — the badge app-wrap swallows the `#portal` div;
pre-existing nesting, small fix), FINDING-015 (#7156's headline scenario still throws `filesById is not defined`;
confirmed pre-existing, MEDIUM — the documented upload-button pattern works, so at minimum reword the changelog
line), FINDING-019 (a non-UTF-8 marker still wedges startup despite #7142; one-line catch;
confirmed, not a regression — the verifier lowered it to LOW because only external corruption produces that marker).
FINDING-004 (the `deps=["router"]` deprecation is silent in the default `auto_deps=True` shape) drops off this list:
the `up_examples_b` verifier showed the warning fires for every shape that would break at removal and is silent only
where auto-deps already cover the router — a one-line nit, not a release item; the `router_vars` verifier still calls
it a (LOW) defect.

What works — every headline changelog item was exercised on the published packages, in a real browser, in dev and
prod, against a 0.9.11.post1 baseline: the #7068 router split (navigation-delta matrix matches the PR table, −47%
whole-frame bytes, redis/disk pickles store the URL once, old pickles discarded cleanly on upgrade); #6850 Slot
transparency and #7176 memo app-wraps (a page that crashed outright on 0.9.11.post1 now works); #6946 (−42% inbound
websocket bytes), #7168 (8/8 supersession shapes, baseline fails 3), #7145, #7157, #7187; #6181 (per-substate providers real in the compiled output; the
"on_load count halved" measurement was later shown to be timing noise, see Phase 7); #7159 both halves; #7015/#7189/#7198 (80 006-entry var leak gone, 1.5–3.8× faster ops), #7115, #7131,
#6930 (PEP 810 path active on 3.15), #7080, #6923; #7153/#7078 (three route URLs that 404 on the previous stable now
serve prerendered HTML), #7165, #7112, #7096 (the enterprise ag-grid demo's dev backend, dead on 0.9.11.post1, runs),
#7142, #7139; #7089/#7114/#7117/#7129/#7202/#7193/#7152/#7075; #7049 (with heavy libraries installed but unused:
`sys.modules` 1509 → 645, RSS 133 → 46.5 MB); #7083; the whole component train (sankey, `use_chart_width`, #6833 at
the render level, data_editor image cells, plotly `divId`, toast callbacks, code copy button); #7155 otel compile
spans; Python 3.10/3.14/3.15 install + run. Eleven reflex-examples apps upgraded in place with no regression, and
the enterprise ag-grid, map, dnd, flow, mantine and (behind the metaclass shim) MCP + OIDC surfaces behave
identically to the previous stable. Packaging: 19/19 published, 122 stubs correct, pins as intended.

Severity histogram (27 numbered findings, final; severities are post-verification):

| | confirmed by a verifier | claimed only (measurement / not re-verifiable here) | refuted or reclassified |
|---|---|---|---|
| critical | 1 (001) | – | – |
| high | 3 (003, 011, 012) | – | – |
| medium | 5 (015, 017, 018, 023 ↓ from high, 024) | – | 2 (016 → pre-existing memory-vs-redis divergence, low; 020 → the test app under-bundled, not a defect) |
| low | 6 (006, 008, 013, 019 ↓ from medium, 025, 004 — behaviour confirmed by both verifiers, defect status disputed) | 3 (002 changelog wording, 022 bundle-size measurement, 027 CDN blocked here) | 7 (005, 007, 009, 010, 014, 021, 026) |

Regressions vs 0.9.11.post1: 001, 003, 011, 017 (all confirmed). Plus four unnumbered explorer claims refuted by
verifiers (masked cached-var AttributeError — #7115 actually fixes it; `rx.asession()` failures invisible — a toast
is shown; npm stickiness with no way back — `REFLEX_USE_NPM=0`; "no alpha at all without the prerelease flag" — the
mixed set is what you get). Previous campaign items closed by this train: FINDING-016 (JSON lines), FINDING-018
(hydrate dropped by an unserializable var, via #7096), FINDING-021 (npm lockfile), #6978 (masked AttributeError).

Index:
- FINDING-001: State metaclass change breaks downstream metaclasses derived from `BaseStateMeta` — every reflex-enterprise 0.9.5 app using AuthPlugin, MCPPlugin or EventHandlerAPIPlugin fails to start (CRITICAL, regression) — **CONFIRMED** by the orchestrator, two explorers and the adversarial verifier
- FINDING-002: the #7132 changelog entry describes behavior #7136 made unreachable — a `_get_was_touched` var is now rejected at class creation (LOW, changelog/behavior mismatch, maintainer decision)
- FINDING-003: a `@rx.var(cache=False)` withheld from a delivered delta by a downstream `get_delta` filter is never re-sent — #6946's last-sent memo is written while the delta is BUILT, not when it is delivered (HIGH, regression; reproduced in pure reflex by `event_loop` in dev and prod+redis, through reflex-enterprise auth by `ent_mcp_oidc`, by the `ent_mcp_oidc` verifier's own 60-line pure-reflex script, and by the `event_loop` verifier verbatim in dev/memory and dev/redis against a correct 0.9.11.post1 baseline) — **CONFIRMED** by both verifiers
- FINDING-004: the documented `deps=["router"]` deprecation warning never fires in the default case — the guard in `_init_var_dependency_dicts` tests the MERGED dep set after auto-dep detection has added the `rx_router_*` names (LOW, new in #7068) — found by `router_vars` and `up_examples_b`; behaviour **CONFIRMED** by both clusters' verifiers (only the `auto_deps=True` + router-reading-body shape is silent; `auto_deps=False` and non-router bodies warn with the documented text, pinned by `tests/units/test_state.py:4184`), defect status **disputed**: the `router_vars` verifier keeps it as a LOW defect (the common legacy form gets no migration signal), the `up_examples_b` verifier calls it not-a-defect (in the silent shape auto-deps already register all five `rx_router_*` fields and unknown string deps are silently accepted on both versions, so nothing breaks at removal). Triage: a one-line nit in `_add_static_dep`, not a release item
- ~~FINDING-005~~: "a narrow `deps=` cannot narrow" — **REFUTED** by the verifier (`deps=[State.router.url], auto_deps=False` registers only `rx_router_url`; `deps=` is additive by long-standing design; the −47% vs −67% gap compares whole frames with the PR's router-only measurement). Kept in the refuted list below.
- FINDING-006: a substate shadowing a parent's backend (underscore) var is still silently ignored — `_check_overridden_inherited_vars` skips every `_`-prefixed name (`reflex/state.py:1335`) (LOW, pre-existing gap) — **CONFIRMED** by the verifier on both versions, with the runtime damage characterised (child default discarded, reads/writes resolve to the parent)
- ~~FINDING-007~~: "PR #7136's documented `REFLEX_STATE_ALLOW_RESERVED_NAMES=1` escape hatch is missing" — **REFUTED as a defect** by the verifier: the flag is promised only in the PR description; the news fragment, the docs paragraph and the changelog never mention it (so nothing shipped is wrong), and it would not have helped FINDING-001 anyway. Kept as a note for the release manager: #7136 shipped a breaking change with no opt-in, contrary to its own description.
- FINDING-008: `rx.dropdown_menu.trigger` swallows its child button's `on_click` — the menu opens, the handler never runs; the other four Radix triggers compose correctly (LOW after verification: pre-existing, upstream Radix — the menu opens on pointerdown and the dismissable layer sets `pointer-events:none`, a synthetic `el.click()` runs the handler, so reflex's wiring is correct) — **CONFIRMED** by the verifier as a bug to file, not a release item
- ~~FINDING-009~~: "`rx.cond` evaluates both branches eagerly; a render-time throw in the untaken branch fails the prod build" — **REFUTED** by the verifier: an `@rx.memo` component that throws and an idiomatic `None`-deref state expression both sit unharmed in the untaken branch (dev renders, prod prerenders); only a raw `rx.Var("<js>")` literal is inlined into the parent JSX and evaluated, which is plain JS semantics through reflex's escape hatch, and the prod build fails byte-identically on 0.9.11.post1. Kept in the refuted list.
- ~~FINDING-010~~: "`on_submit` form data is polluted with id-keyed duplicates" — **reclassified** by the verifier: intentional, long-standing API (`Form._get_form_refs()` sends every ref in the form subtree so an id-only field reaches the handler; the `None`s are `getRefValue` on non-input ids); byte-identical on 0.9.11.post1. A cleanup ticket at most; kept in the refuted list.
- FINDING-012: the `rx.data_editor` overlay editor — the image-preview carousel that is the headline of #7081 — never opens in PROD when the "Built with Reflex" badge is on: the sticky-badge app-wrap nests the dataeditor's `#portal` wrap and drops it (HIGH impact on a headline feature, pre-existing nesting, trivially small to fix) — **CONFIRMED** by the verifier on a fresh 12-line app with an A/B: `show_built_with_reflex=False` restores the portal and the carousel opens
- FINDING-013: `rx.vars.use_id()` inside an `rx.foreach` body returns one identical id for every item — duplicate DOM ids, every `html_for` label targets the first row (LOW after verification — by-design limitation documented on `use_hook_var` but not on `use_id()` or its three docs pages; a docs fix) — **CONFIRMED** by the verifier
- ~~FINDING-014~~: "the #7124 changelog's `reflex.components.datadisplay.code` path fails" — **REFUTED** by the verifier: the changelog names a module path, and `import reflex.components.datadisplay.code` works on both versions; only the `from … import code` spelling fails, and it never worked. Kept in the refuted list.
- FINDING-015: #7156's headline scenario — a toast action or `rx.call_script` callback that triggers an upload handler — still fails: the handler slot is fixed but the payload's `filesById?.["u2"]` is only in scope inside the component that renders `rx.upload`, so the click throws `ReferenceError: filesById is not defined` and no upload starts (MEDIUM — the verifier lowered it from HIGH: pre-existing on 0.9.11.post1, the documented `rx.upload` + sibling submit-button pattern uploads fine on 0.9.12a1, the failure is confined to scopes outside the component that holds the `UploadFilesContext` hook; the #7156 changelog line overclaims) — **CONFIRMED** by the verifier, not a regression
- FINDING-016: a cancelled foreground `@rx.event(supersedes=True)` handler loses its pre-cancellation state writes under prod+redis (dev/memory keeps them) — the `yield` before the `await` is not flushed when `CancelledError` propagates (LOW, pre-existing — **REFUTED as a release issue** by the verifier: 0.9.11.post1 + redis loses the same writes; it is a memory-vs-redis divergence, not dev/prod, and `StateManagerRedis._try_modify_state` skips the write-back when `CancelledError` propagates; separate upstream issue)
- FINDING-017: after a SIGTERM that fails to stop `reflex run` (dev), or while the app module is broken, the backend port stays bound and accepts connections that are never answered — 0.9.11.post1 released the port and clients got an immediate refusal; a side effect of #7114 moving the listening socket into the granian supervisor (MEDIUM after verification — dev-only, self-healing once a worker returns; regression) — **CONFIRMED** by the verifier, who added a signal-free repro (save a broken app file mid-run: 0.9.12a1 hangs for the client timeout, 0.9.11.post1 refuses instantly, both recover once fixed)
- FINDING-018: `reflex run` (dev) ignores SIGTERM/SIGINT delivered to its pid alone (`docker stop`, `kill <pid>` semantics) — reflex, bun and node survive and the ports stay bound; only a process-group signal (Ctrl-C) exits cleanly (MEDIUM, pre-existing on both versions; #6981's changelog line promises a clean SIGTERM exit) — **CONFIRMED** by the verifier with its own baseline
- FINDING-019: a stateful-pages marker containing non-UTF-8 bytes still crashes backend startup permanently — `UnicodeDecodeError` escapes `_read_stateful_pages_marker()`'s `except (FileNotFoundError, json.JSONDecodeError)` and the corrupt marker is never replaced (LOW after verification — the verifier reproduced it verbatim including the permanence claim and both controls, but lowered it from MEDIUM: #7142's atomic writer cannot produce a non-UTF-8 marker, 0.9.11.post1 had no guard at all so 0.9.12a1 is strictly better, and the fix is one line at `reflex/compiler/compiler.py:1218-1226`) — **CONFIRMED**, not a regression
- FINDING-020: a `@rx.dynamic` component never re-renders when the state it reads changes — the delta carries only the plain field, never the recomputed component var (**REFUTED** by the verifier: the delta DOES carry the recomputed component var; the test app bundled only the initial icon, the fallback `import` from jsdelivr is blocked by the container's egress proxy, and `bundle_library(rx.icon("bug"))` makes the same click re-render — not a defect; the real bug it exposed is FINDING-027)
- FINDING-021: literal asset `src` paths (`rx.image(src="/components/logo.svg")`) are not prefixed with `frontend_path`, so the image 404s while the file is served under `/app/...` (**REFUTED as a defect** by the verifier: by design — `rx.asset()` applies the prefix at `reflex/assets.py:95`, a literal string is indistinguishable from any other URL; pre-existing; the residue is a docs gap, nothing under `docs/` mentions `frontend_path` together with assets)
- FINDING-022: `frontend_lazy_bundled_libraries=True` INCREASED decoded initial JS bytes by ~65 KB (+3.7–5.5%) on every page of the test app, including pages that use no optional library — the #7078 "reducing JavaScript loaded by ordinary pages" claim did not hold (LOW, perf-claim gap; measured as decoded bodies on one app, needs a wire-bytes/larger-app confirmation) — claimed by `build_prod_export`; a measurement, not re-verified by the verifier
- FINDING-027: the CDN fallback URL a `@rx.dynamic` component generates for an unbundled sub-path import is malformed — `reflex_base/components/dynamic.py:205-214` computes `get_cdn_url()` for the root library (`…/lucide-react@1.26.0/+esm`) and appends the import's `package_path`, giving `…/+esm/dist/esm/icons/bug.mjs`, while jsdelivr needs `/+esm` to terminate the path, so the designed fallback cannot load even with CDN access (LOW, pre-existing — `dynamic.py` is byte-identical on 0.9.11.post1; found by the `build_prod_export` verifier while refuting FINDING-020) — claimed from the URL in the delivered delta; jsdelivr's behaviour could not be tested because the container's egress proxy blocks the CDN
- FINDING-023: a hydrate/event delta naming a substate the compiled frontend has no dispatcher for sets `backend_state_mismatch=true` in `state.js` and every later event is discarded — zero websocket frames leave the browser until the frontend is recompiled (MEDIUM after verification — the verifier reproduced it field for field on both versions but lowered it from HIGH: the latch is deliberate and commented as fatal-by-design in both versions, the "a reload does not recover" sub-claim is an artifact of `.web/nocompile` pinning the stale bundle — in the realistic cached-bundle shape a reload fetches the new bundle and recovers as the error message advises — and the #6181 timing caveat is weak because all 21 `SubstateProvider`s are statically nested in one `useMemo`; pre-existing, the previous campaign's FINDING-036) — **CONFIRMED** by `render_ctx_statemgr` and its verifier; a genuine defect for the mixed-version / load-balancer shape, not a release blocker
- FINDING-024: `app.modify_state("<client token>")` with the bare token raises `ValueError: Invalid path: ('',)` from `BaseStateToken.from_legacy_token` — the deprecated string form is broken for its most obvious argument (MEDIUM, pre-existing — the verifier reproduced the 500 and the 200 control, proved the baseline two ways, and adds that `App.modify_state` still carries an un-deprecated `token: str` overload at `reflex/app.py:1801`, so type checkers accept the call the runtime rejects) — **CONFIRMED** by the verifier
- FINDING-025: `reflex run` deletes the whole `.states/` directory at startup in `--env prod` as well as dev, whatever `REFLEX_STATE_MANAGER_MODE` is, so disk-backed state never survives a restart (LOW, pre-existing, intentional-looking `reset_disk_state_manager()` call at `reflex/reflex.py:597`; the verifier executed the 0.9.11.post1 baseline and the `--env prod` case and widened the scope: `StateManagerDisk` is the default whenever no redis URL is configured, so every `reflex run` restart drops every live session's state in the default single-process configuration, not only under `REFLEX_STATE_MANAGER_MODE=disk`) — **CONFIRMED** by the verifier
- ~~FINDING-026~~: "the #7083 changelog understates the `rx.Model` change" — **REFUTED** as a defect by the verifier: the behavior reproduces (a plain `class Item(rx.Model)` now raises the guided ImportError at definition time on a bare install), but the changelog's scope clause "Subclassing `rx.Model` (e.g. `class Item(rx.Model, table=True)`)" already covers every subclass; the `table=True` form is an example, not a restriction. Kept in the refuted list.
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

## FINDING-003: a withheld `@rx.var(cache=False)` is never re-sent once visible (HIGH, regression — CONFIRMED by two clusters and both verifiers)

- Clusters: `ent_mcp_oidc` (through reflex-enterprise auth) and `event_loop` (pure reflex, dev and prod+redis) |
  Regression vs 0.9.11.post1: **yes** in both | Adversarial verifiers: `ent_mcp_oidc` CONFIRMED, `event_loop` CONFIRMED
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
- `event_loop` verifier: reproduced the pure-reflex repro verbatim on 0.9.12a1 in dev/in-memory (the delta after
  `show` is `{fl: ['visible_rx_state_']}` only, the page stays `secret-0`, jumps to `secret-2` on the next bump and
  `secret-1` is never delivered) and in dev + redis (single worker, `REFLEX_REDIS_URL`; the stale
  `__last_delta_secret_rx_state_` memo is visible inside the pickled state in redis, so this is neither a prod-build
  nor a multi-worker artifact); 0.9.11.post1 delivers `secret-1` and `secret-3`. Deterministic across three runs on
  two transports, zero page/console errors. Strongest point against "API misuse": reflex-enterprise 0.9.5 overrides
  `BaseState.get_delta` for post-event auth filtering (`reflex_enterprise/auth/oidc/state.py:2529`) and its
  `redeliver_protected()` (`auth/enforcement.py:960-995`) re-marks withheld vars dirty on the assumption that the
  end-of-event delta re-delivers them — the assumption #6946 breaks for `cache=False` vars. Evidence:
  `event_loop/verification/out_dev12/filtered.*`, `out_dev12redis/filtered.stdout.txt`, `out_prev/filtered.*`;
  commands in `event_loop/NOTES.md` "## VERIFICATION".
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

## FINDING-015: #7156's advertised scenario still fails — `filesById is not defined` (MEDIUM, pre-existing — CONFIRMED; verifier lowered from HIGH)

- Cluster: `event_loop` | Regression vs 0.9.11.post1: no (both fail; 0.9.11.post1 fails earlier, in the handler slot) |
  Verifier: CONFIRMED as a defect, not a regression
- Repro: `event_loop/elapp` page `/callback`: `rx.toast("...", action={"label": "Upload", "on_click": CB.handle_upload(rx.upload_files(upload_id="u2"))})`
  fired from a frontend trigger, and `rx.call_script("1", callback=lambda v: CB.handle_upload(rx.upload_files(upload_id="u2")))`;
  select a file in the `u2` zone, click the action. Console: `ReferenceError: filesById is not defined`; no upload
  request; `uploaded` stays empty (`out/callback.txt` cases 6, 8, 9; `out/callback.errors.txt`).
- Mechanism: the compiled event is now `ReflexEvent("...cb.handle_upload", {...}, {}, "uploadFiles")` — the #7156
  ordering fix is real — but the payload emits `files: filesById?.["u2"]`, and `const [filesById, setFilesById] =
  useContext(UploadFilesContext)` is hoisted only into the component that renders `rx.upload`; a toast action or a
  `call_script` callback runs outside it. Either propagate the hook/VarData to the callback site or reword the
  changelog line ("handlers like `uploadFiles` never ran") — as shipped, the headline case does not work end to end.
- Verifier: reproduced verbatim on 0.9.12a1 (cases 6, 8, 9 fail — `_call_script ReferenceError: filesById is not
  defined` in the console for the callback, an uncaught `PAGEERROR filesById is not defined` for both toast variants,
  `uploaded == []`; case 10, plain `rx.upload(on_drop=...)`, passes) and on 0.9.11.post1 (the frontend-fired toast
  dies earlier on `queueEvents is not defined`, the backend-yielded toast fails with the identical `filesById` error).
  Checked the claim against the release branch: `packages/reflex-base/CHANGELOG.md` line 30 names exactly this case
  ("a `rx.call_script` callback or toast action triggering an upload handler … handlers like `uploadFiles` never
  ran"), so the entry overclaims. New control the explorer did not run (page `/upbtn`,
  `verification/elapp_with_upbtn_page.py`, `verification/scripts/s_upbtn.py`): the DOCUMENTED pattern —
  `rx.upload(id="u3")` plus a sibling `rx.button(on_click=UB.handle(rx.upload_files(upload_id="u3")))`, and the
  same button nested inside `rx.upload` — uploads fine on 0.9.12a1 with no page errors. Severity lowered to MEDIUM:
  nothing regressed, the documented pattern works, and only scopes that escape the component function holding the
  `UploadFilesContext` hook (the sonner action/cancel `onClick`, the eval'd backend callback in `.web/utils/state.js`
  `applyEvent`) fail. Evidence: `event_loop/verification/out_dev12/callback.{stdout,errors,console}.txt`,
  `callback.frames.jsonl`, `out_prev/callback.stdout.txt`, `out_dev12redis/upbtn.stdout.txt`.

## FINDING-016: cancelled foreground `supersedes=True` handler loses pre-cancellation writes under redis (LOW, pre-existing — REFUTED as a release issue by the verifier)

- Cluster: `event_loop` | Regression: **no** (the verifier ran the missing 0.9.11.post1 + redis baseline: identical
  loss) | Explorer's repro: `elapp` page `/supersede`, handler `frefresh` (foreground, appends `F{tag}:start`, `yield`,
  `await asyncio.sleep(2)`, appends `:done`); fire A then B within 2 s. Dev/memory: `["FA:start","FA:CANCELLED",
  "FB:start","FB:done"]`. Prod + redis (9 workers): `["FB:start","FB:done"]` — `FA:start` never reaches the client or
  redis despite the `yield` before the sleep (`out/supersede.txt` vs `out_prod/supersede.txt`, two consecutive runs).
  The background variant and non-cancelled foreground handlers keep their writes.
- Mechanism guess: with redis the state is written back when the event's `modify_state` context exits normally; a
  foreground handler cancelled mid-`await` (CancelledError propagates) does not flush, so the pre-cancellation
  mutation and its emitted delta are lost together.
- Verifier: isolated the variable — same dev build, same app, one worker, toggling only `REFLEX_REDIS_URL`
  (redis-server on 8695). 0.9.12a1 in-memory: `["FA:start","FA:CANCELLED","FB:start","FB:done"]`; 0.9.12a1 + redis:
  `["FB:start","FB:done"]`; 0.9.11.post1 + redis: `["FB:start","FB:done"]` — identical, so pre-existing. Controls in
  the same runs: `[g-mixed]` keeps a completed foreground handler's writes under redis on both versions, and the
  0.9.11.post1 run shows the pre-#7168 shapes for `[b-chains]`/`[d-poll]`/`[e-stale]`, proving the baseline server
  really was 0.9.11.post1. Root cause: `reflex/istate/manager/redis.py:487-494` (`StateManagerRedis._try_modify_state`)
  calls `set_state` only after the `yield state` body returns normally, so a `CancelledError` thrown into the body
  skips the write-back entirely, including what an intervening `yield` appeared to flush; background handlers commit
  per `async with self` block. The explorer's "dev/prod divergence" framing is imprecise — it is memory-vs-redis, and
  prod/multi-worker is not a factor. Not a defect for THIS release (arguably intentional: a cancelled event's partial
  writes are not committed), but worth a separate upstream issue because the two state managers disagree and an
  intervening `yield` gives a false impression of a flush under redis. Repro-quality note: dev + `REFLEX_REDIS_URL`
  reproduces it in ~90 s; the written prod+redis+9-workers recipe conflated three variables. Evidence:
  `event_loop/verification/out_dev12/supersede.*`, `out_dev12redis/supersede.stdout.txt`,
  `out_prevredis/supersede.stdout.txt`.

## FINDING-017: backend port stays bound and swallows connections when the worker cannot serve (MEDIUM, regression — CONFIRMED)

- Cluster: `dev_server_cli` | Regression vs 0.9.11.post1: **yes**, baselined in both directions by explorer and verifier
- Verifier: reproduced verbatim on its own ports (4 runs, 4 port pairs, raw sockets, granian 2.8.3 in BOTH venvs so
  the only delta is reflex's code) and closed the repro's gap — the SIGTERM lead-in only arises together with
  FINDING-018, so it wrote `verification/scripts/break_reload_probe.py`, which appends `raise RuntimeError(...)` to
  the app module mid-run (the ordinary "developer saved a broken file" case): 0.9.12a1 hangs for the full client
  timeout at +10 s and +24 s, 0.9.11.post1 refuses instantly, both recover to 200 once fixed. Downgraded HIGH → MEDIUM:
  dev-only (prod uses plain Granian, `exec.py:857`) and self-healing; the defect is the missing bound, not #7114.
- Root cause (verifier): `reflex/utils/exec.py:726-741` — `ParentBoundGranian._init_shared_socket` builds the
  listening socket in the granian supervisor (`SocketSpec(...).build()`, `sock.set_inheritable(True)`) instead of
  letting each worker bind, so the kernel keeps accepting whenever no worker is alive; 0.9.11.post1 has no such
  subclass.
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

## FINDING-018: `reflex run` ignores SIGTERM/SIGINT sent to its pid alone (MEDIUM, pre-existing — CONFIRMED)

- Cluster: `dev_server_cli` | Both versions: `exit_code=TIMEOUT_30s`, survivors reflex+bun+node, ports bound
  (`logs/sigres_N1_new_dev_TERM_proc.json`, `logs/sigres_P1_prev_dev_TERM_proc.json`); the process-GROUP signal exits 0
  in 0.2 s on 0.9.12a1 with no "exit code 143" line (#6981 verified for that path) but logs `[ERROR] Unexpected exit
  from worker-1` on the clean stop. Repro: `scripts/signal_test.py <venv> <dsc dir> L TERM proc <logdir> <FP> <BP>`
  (the `.sh` version in the same dir is superseded — it signalled the `setsid` wrapper). Verifier: both versions
  time out at 30 s with reflex+bun+node survivors; its `ports_after` column is the cleanest single evidence for
  FINDING-017 (same stuck process, backend port bound only on 0.9.12a1). Mechanism guess: `reflex/reflex.py:428-451`
  runs the frontend on a thread pool while `exec.run_backend` blocks the main thread, so granian's SIGTERM handling
  never tears down the bun/vite children the CLI spawned. The `[ERROR] Unexpected exit from worker-1` on a clean
  group stop is granian's own message (`granian/server/common.py:61`), identical on 0.9.11.post1 — not a regression.
- Impact: `docker stop`, systemd and `kill <pid>` never terminate a dev server; combined with FINDING-017 the port
  then hangs instead of refusing. Prod-mode signal handling was not exercised (out of timebox).

## FINDING-019 … FINDING-022, FINDING-027 (`build_prod_export`; verifier: 019 CONFIRMED at LOW, 020 and 021 REFUTED, 022 not re-verified, 027 new; details in `build_prod_export/NOTES.md` and its `## VERIFICATION`)

- FINDING-019: `head -c 64 /dev/urandom > .web/backend/stateful_pages.json`, then `reflex run --env prod --backend-only`:
  `UnicodeDecodeError` traceback (`logs/be_s3_garbage.log`), `Unexpected exit from worker-1`, nothing binds the port,
  and every later start fails the same way because the marker is left in place. Truncated JSON, a missing marker and
  a 4-worker cold start all rebuild cleanly, and `reflex compile --dry` leaves markers byte-identical — the fix works
  except for this input. Root cause: `Path.read_text()` decodes before `json` sees anything;
  `reflex/compiler/compiler.py::_read_stateful_pages_marker()` catches `JSONDecodeError` but not `UnicodeDecodeError`.
  One-line fix (catch `ValueError`/`OSError`, or read bytes).
  - Verifier: **CONFIRMED** verbatim (`verification/logs/marker_s3_garbage.log:24-49`; permanence in `marker_s3b_again.log`;
    the controls `marker_s1_truncated.log`/`marker_s2_missing.log` rebuild to `["components"]` and bind the port). Not a
    regression: 0.9.11.post1 has no guard at all (`with marker.open('r'): json.load(file)`), and the line-level replay in
    `verification/scripts/prev_marker_read.py` raises on both the garbage and the truncated marker, so 0.9.12a1 is strictly
    better. Lowered to LOW: the atomic writer cannot create a non-UTF-8 marker (external corruption, or a 0.9.11 write
    interrupted mid-multibyte-character in a non-ASCII route name), though the failure stays opaque (bare granian worker
    exit). Root cause `reflex/compiler/compiler.py:1218-1226`, called from `compile_app` at line 1256.
- FINDING-020: `@rx.dynamic def widget(state: DynState)` rendering `rx.icon(tag=state.tag)`; flipping `tag` updates a
  plain `rx.text(DynState.tag)` and the websocket delta carries `tag_rx_state_`, but the dynamic component keeps
  rendering the old icon in dev, backend-only prod and on 0.9.11.post1 (`out/backend_only_0912a1.json`).
  - Verifier: **REFUTED** — the stated root cause is provably wrong. On a full prod run the websocket delta after
    `#dyn-flip` carries the recomputed component var (`dynamic_reflex_state_dynamic_locals_wrapper_locals_lambda_rx_state_
    = "//__reflex_evaluate\nimport LucideBug from \"https://cdn.jsdelivr.net/npm/lucide-react@1.26.0/+esm/dist/esm/icons/
    bug.mjs\"…"`, `verification/out/vcheck_prod_new.json`). The widget freezes because the app calls
    `bundle_library(rx.icon("rocket"))` only, so the new module is imported from jsdelivr, which this container's
    egress proxy refuses (`net::ERR_TUNNEL_CONNECTION_FAILED` ×2 in the console; `[Reflex Frontend Exception]
    TypeError: Failed to fetch dynamically imported module` in `verification/logs/prod_new_unbundled.log:44-102`).
    Decisive control: one added line, `bundle_library(rx.icon("bug"))` (`verification/bpapp_bundle_bug_patch.txt`), and
    the identical click flips `dyn:rocket`/`lucide-rocket` → `dyn:bug`/`lucide-bug` and survives reload
    (`out/vcheck_prod_bundlebug.json`, `shots/prod-bundlebug-dyn-after.png` vs `prod-new-dyn-after.png`). In backend-only
    mode the delta really carries only `tag_rx_state_`, for a different reason: the marker is `["components"]`, so `/dyn`
    is never re-evaluated and the dynamic var is never created on `DynState` — a marker/#7096 interaction, not
    dependency tracking. What the written repro lacked: console capture for `/dyn` and the server log's
    frontend-exception block. Side effect: FINDING-027.
- FINDING-021: `rx.image(src="/components/logo.svg")` under `frontend_path="/app"` requests `/components/logo.svg`
  (404) while `/app/components/logo.svg` serves 200; identical on both versions. Either prefix root-relative literal
  asset paths at compile time or document that `rx.asset()` is required with `frontend_path`.
  - Verifier: **REFUTED as a defect** — symptom reproduced (`#logo` keeps `src="/components/logo.svg"`, the only 4xx
    of the run, `naturalWidth == 0`; the built tree holds only `.web/build/client/app/...`), but `rx.asset()` is the
    supported API and applies the prefix in `AssetPathStr.__new__` → `prepend_frontend_path` (`reflex/assets.py:95`,
    same line on 0.9.11.post1); a literal `src` string is indistinguishable from any other URL, and rewriting literals
    at compile time would break absolute/CDN/external URLs. Residue: a docs task — nothing under `docs/` mentions
    `frontend_path` together with assets, so adding `frontend_path` silently breaks every literal-src image.
- FINDING-022: `/app/` 1 177 996 → 1 243 249 B (+65 253), `/app/about` +3.7%, `/app/components` +5.4% decoded JS with
  the flag on: fewer requests (17 → 14 files) but a single `esm-*.js` module ~65 KB larger than the shiki/icon chunks
  it displaces. Direction consistent across all three pages; caveat: Playwright `response.body()` bytes on one app.
  - Not re-verified: a measurement rather than a defect claim; still needs wire bytes on a larger app before the #7078
    wording is judged.
- FINDING-027 (new, from the verifier; LOW, pre-existing): the CDN fallback URL for an unbundled sub-path dynamic import
  is malformed — `reflex_base/components/dynamic.py:205-214` computes `get_cdn_url()` for the ROOT library
  (`https://cdn.jsdelivr.net/npm/lucide-react@1.26.0/+esm`) and then appends the import's `package_path`, producing
  `…/+esm/dist/esm/icons/bug.mjs`; jsdelivr's `/+esm` must terminate the path, so the designed fallback for an unbundled
  sub-path import cannot work even with CDN access. `dynamic.py` is byte-identical between 0.9.11.post1 and 0.9.12a1
  (`cmp` clean). Status: the URL is in the delivered delta (`verification/out/vcheck_prod_new.json`), but jsdelivr's
  response could not be observed here (the egress proxy blocks the CDN, `curl` rc 56) — confirm with one request against
  jsdelivr before filing. Also recorded, unexplained: the first prod worker exited (`[ERROR] Unexpected exit from
  worker-1`) right after four of those frontend exceptions while the browser was idle; the bundled, exception-free run
  stayed up (single occurrence on a shared 4-CPU host, `verification/logs/prod_new_unbundled.log`).

## FINDING-023 … FINDING-025 (`render_ctx_statemgr`; all pre-existing, all CONFIRMED by the verifier — 023 lowered to MEDIUM; details in `render_ctx_statemgr/NOTES.md` and its `## VERIFICATION`)

- FINDING-023 (standing HIGH from the previous campaign): `renderapp` with `RENDERAPP_EXTRA_STATE=1` defines a backend
  state class the compiled frontend does not know about; the hydrate delta names it, `.web/utils/state.js` sets
  `backend_state_mismatch = true`, and both the socket `event` handler and `processEvent()` return early forever:
  `A_after_load='0'`, `sent_frames_from_clicks=0`, same after reload (`out/mismatch_new_result.json`,
  `out/mismatch_prev_result.json`). A one-way latch with no reset path; #6181 moved dispatcher registration into a
  `useLayoutEffect` with `delete` on unmount but left the latch. Realistic trigger: a stale `.web/` after adding a
  State class with the frontend compile skipped (backend-only workers, `nocompile`).
  - Verifier: **CONFIRMED** field for field on both versions (`verification/v_mismatch_new_result.json` vs
    `v_mismatch_prev_result.json`: `A_after_load '0'`, `sent_frames_from_clicks 0`, `events_reach_backend false`,
    `after_reload_sent_frames 0`, `recv_frames 14`, no page errors; the server logs show the `CLIENT_ERROR` round-tripping
    with the backend healthy). Lowered HIGH → MEDIUM on three grounds: (1) the latch is deliberate — both versions'
    `state.js` say "Validate the whole delta before dispatching anything…" and "A backend/frontend state mismatch is
    fatal; do not send further events", so a fix is a design change, not a regression repair; (2) "a reload does not
    recover" is an artifact of the repro — `.web/nocompile` pins the server to the stale bundle, whereas in the realistic
    shape (backend redeployed with a new substate, browser holding a cached old bundle) a reload fetches the new bundle
    and recovers exactly as the error message advises; what stays broken is the within-session case a reload cannot fix
    (mixed-version backends behind a load balancer, `api_url` pointed at a different backend); (3) the "#6181 makes it
    newly reachable by timing" caveat is weak — all 21 `SubstateProvider`s are statically nested in `StateProvider`'s
    single `useMemo` (`context.jsx:189-213`) and can only unmount with the whole tree, socket included. Latch at
    `state.js:730` (0.9.12a1) / `:749` (0.9.11.post1); early returns at `:706`/`:725`, `processEvent()` at `:520`/`:532`.
    Worth fixing (drop/warn on the unknown substate and apply the rest, or never send substates the page did not
    register), not a release blocker.
- FINDING-024: `_split_substate_key` partitions the legacy token on `_`; a bare UUID yields an empty state path and
  `get_class_substate` rejects `['']`. The deprecation warning fired just before names the right format, but the API
  route gets a bare 500 (`evidence/modify_state_legacy_token_traceback.txt`).
  - Verifier: **CONFIRMED** — `GET /api/poke?token=$T&value=x&legacy=1` → bare `Internal Server Error` 500, the control
    without `legacy=1` → 200 `{"ok":true,…}`; the traceback matches line for line (`app.py:1842` → `token.py:247` →
    `state.py:1477`, `verification/v_issue2_traceback.txt`). Baseline proven two ways (`verification/legacy_token_check.py`
    raises the identical `ValueError` on both venvs; `from_legacy_token`'s source is character-identical). Missed by the
    explorer: `App.modify_state` still advertises an un-deprecated `token: str` overload (`reflex/app.py:1801`), so a
    type checker accepts the call the runtime rejects with a message naming a path the caller never wrote; `docs/` never
    mentions the string form, so the fix is API-surface only (default an empty state path to the root state, or raise a
    message that names the `BaseStateToken` replacement).
- FINDING-025: `reflex/reflex.py::_run` calls `reset_disk_state_manager()` unconditionally before the app starts;
  after a clean SIGTERM flush wrote six pickles, the next `reflex run --env prod` left `.states/` empty
  (`logs/disk_verify.log`). Reasonable in dev (stale schema), surprising for prod disk-backed state.
  - Verifier: **CONFIRMED** and extended — SIGTERM then SIGKILL left two pickles intact (md5s recorded), the next
    `reflex run` emptied `.states/` and `/api/disk_read` returned `{"disk":null,"cache":null}`; the 0.9.11.post1
    baseline (seeded pickles emptied by `reflex run`, `verification/v_reset_prev_tail.log`) and the `--env prod` case
    (seeded pickles emptied while the prod build was still compiling, `v_reset_prod_tail.log`) were executed rather than
    argued from source. Scope correction: `StateManagerDisk` is the default whenever no redis URL is configured —
    `renderapp` accumulated `.states/*.pkl` with no state-manager variable set — so every `reflex run` restart drops
    every live session's state in the default configuration; defensible in dev, a decision for `--env prod`. Call site
    `reflex/reflex.py:597` (0.9.11.post1: `:571`, not `:570` as the notes say).

## FINDING-012: `rx.data_editor` image-preview overlay dead in prod with the default badge (HIGH impact, pre-existing — CONFIRMED by the verifier with an A/B)

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

## FINDING-004, FINDING-006 (LOW; behaviour CONFIRMED by the verifiers — 004's defect status disputed; details in the cluster NOTES)

- FINDING-004 (`router_vars`, ISSUE 1; CONFIRMED, diagnosis corrected by the verifier): `@rx.var(deps=["router"])`
  with a body that reads `self.router` (the default `auto_deps=True` case) raises no deprecation warning; the
  guard at `reflex/state.py:1205-1221` tests `dvar_set.isdisjoint(ROUTER_VARS)` on the dep set that
  `ComputedVar._deps()` returns, and `reflex_base/vars/base.py:2876-2895` seeds the dependency tracker with the
  very set objects from `_static_deps`, so the auto-detected `rx_router_*` names are merged in place and the
  legacy string becomes indistinguishable from the Var form. The guard DOES fire for `auto_deps=False`, and for
  bodies that do not read the router (`router_vars/verification/scripts/v_deps_legacy_matrix.py`). Fix at
  declaration time (`_add_static_dep`), not after `_deps()`. Repro: `router_vars/scripts/deps_legacy.py`.
  - Second verifier (`up_examples_b`, independent): the same matrix result (`verification/rdvar.py`, five variants —
    `deps=["router"], auto_deps=False` warns with the documented text whether or not the body reads the router, a
    non-router body warns, `deps=[State.router], auto_deps=False` correctly stays silent, and the written repro is the
    only silent shape), plus end to end: a `/routerdep2` page with `@rx.var(deps=["router"], auto_deps=False,
    cache=True)` logs the `DeprecationWarning` twice in a real `reflex run --env prod` server log
    (`verification/uc_new_prod.verify.log`) and still renders. The release source pins it: `tests/units/test_state.py:4184`
    asserts exactly one deprecation for the string + `auto_deps=False` form and none for the Var form. This verifier's
    judgment: **not a defect** — the silent shape is the redundant one (auto tracking already registers all five
    `rx_router_*` names there) and an unknown string dep is silently accepted on both versions (`verification/bogusdep.py`:
    `deps=["no_such_var"]` accepted on 0.9.12a1 and 0.9.11.post1), so those users break neither at 0.9.12 nor at the
    1.0 removal, while the users who would break do get the warning. The `router_vars` verifier's counter-argument
    (`tests/units/test_state.py:4141`: the string only keeps working while `router` is still a var) holds only if
    unknown string deps start raising. Triage: a nit, one line in `_add_static_dep`; dropped from the fix-before-release
    list.
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
- **"AttributeError inside a cached var is still masked as `VarAttributeError`" (`ent_aggrid`, carried from two earlier
  campaigns as reflex-dev/reflex#6978)**: refuted for 0.9.12a1 by the verifier — the explorer's own
  `scripts/probe_masked_attrerror.py` yields a chained `ReflexRuntimeError` on reflex-base 0.9.12a1 and the masked
  error only on 0.9.11.post1. #7115 fixes #6978; `vars_typing` reached the same conclusion independently.
- **FINDING-026 — "#7083's changelog understates the `rx.Model` behavior change" (`db_optional_imports`)**: refuted by
  the verifier — the entry says "Subclassing `rx.Model` (e.g. `class Item(rx.Model, table=True)`) without the `db`
  extra installed now raises the guided ImportError"; the plain subclass is a subclass, and PR #7083's body records
  that the maintainers accepted definition-time failure for every subclass. Behavior confirmed, wording adequate.
- **"A failing `rx.asession()` inside a background task is invisible to the client" (`db_optional_imports`)**: refuted
  by the verifier — the server log carries `[Reflex Backend Exception]` markers and the browser shows a red sonner
  toast ("An error occurred. / ValueError: No async database url configured / See logs for details.") after both the
  foreground handler and the background task (`db_optional_imports/verification/shots/noasync_new_*.png`); the
  explorer's driver watched console/pageerror/HTTP/deltas only, and the toast (`id="backend_error"`, ~4 s) had gone
  before its assertions. The underlying "requires `async_db_url`, nothing hints at it" remains a docs nit.
- **"One `REFLEX_USE_NPM=1` run permanently switches a project to npm with no documented way back" (`dev_server_cli`)**:
  refuted by the verifier — `REFLEX_USE_NPM=0` is an explicit escape hatch (`reflex/utils/js_runtimes.py:115-132`
  `prefer_npm_over_bun`, step 2) and restores bun in one run; the lockfile-driven stickiness itself is deliberate
  and works (`verification/scripts/lock_probe.sh`, five runs). Closes the previous campaign's FINDING-021.
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
- **FINDING-016 — "a cancelled foreground `supersedes=True` handler loses its pre-cancellation writes under prod+redis
  (dev/prod divergence)" (`event_loop`)**: refuted as a release issue by the verifier. The behavior is real but identical
  on 0.9.11.post1 + redis (the baseline the explorer skipped), and the variable is the redis state manager, not prod or
  worker count: `StateManagerRedis._try_modify_state` (`reflex/istate/manager/redis.py:487-494`) writes back only when
  the `yield state` body returns normally, so a `CancelledError` discards every mutation of the cancelled foreground
  handler. Pre-existing, LOW; a separate upstream issue about memory-vs-redis semantics.
- **FINDING-020 — "a `@rx.dynamic` component never re-renders when the state it reads changes" (`build_prod_export`)**:
  refuted by the verifier — the delta after the flip carries the recomputed component var; the test app bundled only
  the initial icon, so the new module was imported from jsdelivr, which the container's egress proxy blocks;
  `bundle_library(rx.icon("bug"))` makes the identical click re-render. `@rx.dynamic` and its dependency tracking work;
  the real, pre-existing bug it exposed is the malformed CDN fallback URL (FINDING-027).
- **FINDING-021 — "literal asset `src` paths are not prefixed with `frontend_path`" (`build_prod_export`)**: refuted as a
  defect by the verifier — by design; `rx.asset()` is the API that prepends `frontend_path` (`reflex/assets.py:95`,
  identical on 0.9.11.post1), and a literal string cannot be told apart from any other URL. Docs gap only.

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
unknown kwargs (kills row selection in `ag_grid_finance`) — all four CONFIRMED by the verifier as pre-existing
downstream defects (with the decisive curl pair for the `%3F` bug: the same path with a real `?` returns 200; and
`column_def` pinned to `ColumnDef` deriving from `PropsBase` instead of the strict `NoExtrasAllowedProps`). The
explorer's sixth claim — the `CachedVarOperation` AttributeError "still masked as `VarAttributeError`" — was
**REFUTED**: running the explorer's own probe on 0.9.12a1 gives `ReflexRuntimeError: Computing cached property …
raised AttributeError: REAL ERROR …` with the real error as `__cause__` (#7115 works, `reflex_base/vars/base.py:
2234-2242`); only 0.9.11.post1 masks it (the explorer most likely ran the probe twice against the old venv). The
0.9.11.post1 worker death is the previous stable's defect that #7096 fixes, not anything in this release. Caveat
carried from the agent: the
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

### `event_loop` (pass 26, anomaly 5, fail 2, skipped 1) — #6946/#7168/#7145/#7157/#7187 verified; FINDING-003 confirmed, 015 confirmed (MEDIUM), 016 refuted
Six-page `elapp` plus a websocket-frame-capturing Playwright harness (`scripts/wsdrive.py` + per-scenario drivers),
run in dev, in prod with redis and 9 granian workers, and as a full 0.9.11.post1 baseline. #6946 dedupes
constant/derived/alternating/NaN/list/async/substate uncached vars, is per-client-token correct across browser
contexts, survives hard reload (hydrate uses `dict()`) and redis multi-worker, and cuts inbound websocket bytes
26 059 → 15 274 (~42%) on the same click sequence; events that change nothing send no frame. #7168 passes all
eight supersession shapes while the baseline fails three (cross-chain child cancellation, poll-loop restart,
stale-late-enqueue). #7145: 3000 self-chained ticks, zero RecursionError in dev, prod and baseline logs. #7157 fixes
every frontend-fired toast action/cancel shape (plain, `@rx.memo`, `ComponentState`) that threw `queueEvents is
not defined` on 0.9.11.post1. #7187: one redis connection per worker, flat over 600 `/_health` probes. Issues:
FINDING-003 (confirmed, pure reflex), FINDING-015 (verifier: confirmed, pre-existing, MEDIUM), FINDING-016 (verifier:
refuted as a release issue — identical on 0.9.11.post1 + redis). Anomalies worth a line: an `on_load`-started
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
prop, a `ComponentState`, `rx.foreach` over sqlmodel rows). Issues: FINDING-004 (independently; this cluster's
verifier refuted it as a defect — the warning fires for every shape that would break), and prod 404s for dynamic routes
(pre-existing on both, issue #6983 / PR #6996; the verifier reproduced it with a 12-line app on both versions —
byte-identical screenshots, the SPA shell still hydrates into the right page but with status 404 — and roots it in
`reflex/utils/exec.py:383` serving `.web/build/client` through Starlette `PrecompressedStaticFiles(html=True)`, which
answers a miss with `404.html` at 404; the build's `__spa-fallback.html` is byte-identical to `404.html` and never used). Notes: a naive `uv pip install --upgrade
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
FINDING-017 (confirmed, medium), FINDING-018 (confirmed, pre-existing); the clean-stop `[ERROR] Unexpected exit from
worker-1` line is granian's own and identical on 0.9.11.post1 (verifier); the "one `REFLEX_USE_NPM=1` run sticks the
project on npm with no way back" claim was REFUTED — the stickiness is deliberate (`js_runtimes.py:99-132`,
`_persisted_lockfile_implies_npm`) and `REFLEX_USE_NPM=0` switches back in a single run (the previous campaign's
FINDING-021 can be closed).
Anomaly: `reflex cloud ... --json` emits its error path as plain text (hosting-cli 0.1.72, almost certainly
pre-existing). Not covered: prod-mode signal handling, `reflex export/init --json`, #7166 logging under `reflex run`.

### `build_prod_export` (pass 16, anomaly 5, fail 3, skipped 2) — #7153/#7078/#7165/#7112/#7096/#7142/#7139 verified; FINDING-019 confirmed (LOW), 020/021 refuted, 022 measured, 027 new
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
identical on 0.9.11.post1 → pre-existing. Issues: FINDING-019 (verifier: confirmed, LOW), 020 (refuted — under-bundled
app plus a blocked CDN), 021 (refuted — by design), 022 (measurement), 027 (new, from the verifier). Not covered: the vite RSS half of #7112
(another agent's server shared the box), brotli/zstd compression formats, lazy-library load-failure retry. Tester
trap: `uv pip install --prerelease=allow sentry-sdk` resolves 3.0.0a7, which crashes in `sentry_sdk.init()` against
opentelemetry-api 1.44.0 before any reflex code runs — pin `sentry-sdk<3`.

### `render_ctx_statemgr` (pass 21, anomaly 8, fail 4, skipped 3) — #6181 and #7159 verified; #6180 not observable; FINDING-023 (MEDIUM), 024, 025 confirmed pre-existing
Render-count probe app (10 substates, memo sections, two ComponentStates, foreach over 300 rows, colour-mode and
event-loop consumers, LocalStorage/Cookie/SessionStorage, client_state, background tasks, event chains, a second page
and a dynamic route), a byte-identical 0.9.11.post1 copy, and a StateManagerDisk probe app with Starlette routes
exposing the manager's disk contents, cache and write queue. #6181: per-substate providers are real in the compiled
output; the recorded "A/B/dual 2 vs 4 in dev" on_load halving did not survive re-verification (bimodal 2/4 on all
three versions over six fresh contexts each, see Phase 7 — treat as unchanged / not measurable in this app); every
other scenario was already isolated on 0.9.11.post1 and is unchanged; prod replays the suite with exactly half the
dev counts (StrictMode). #7159: a debounced write flushes the LATEST of two different instances; a state never obtained
from `get_state` is persisted; `modify_state` from an API route pushes live and persists; state survives a hot reload;
the shutdown flush wrote at the SIGTERM second with a 30 s debounce. #6180: not contradicted but not observable — the
colour-mode and event-loop probes recorded 0 extra renders on 0.9.11.post1 too because they sit behind memo boundaries;
do not count #6180 as verified. #7132: FINDING-002 confirmed in one line (both a var and a computed var named
`_get_was_touched` raise; both allowed on 0.9.11.post1). Issues: FINDING-023/024/025 (all confirmed by the verifier; 023
lowered to MEDIUM, 025's scope widened to the default state manager). Anomalies: `BaseStateToken` vs
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
0.9.12a1 preserves it (`scripts/serializer_override.py`). Verifier: the changelog-wording claim (FINDING-026) and the "asession failure invisible in a background task" claim
were refuted (see the refuted list); `reflex db init` without the extra printing a raw click traceback (exit 1, 35
lines, identical on both versions) was CONFIRMED as a pre-existing low. Latent fragility noted: optional-library serializers are matched by identity against hard-coded
module paths (`pandas.core.frame`, `plotly.graph_objs._figure`, `PIL.Image`, `sqlmodel.main`) — a library reorg would
disable serialization silently. Skipped: reflex-local-auth (covered by `up_examples_b`).

## Phase 7 — re-verification on reflex 0.9.12a2 + reflex-enterprise 0.9.6a1 (2026-09-21)

**Verdict: READY — release reflex 0.9.12 and the related packages of this train, subject to the two release conditions at the end of this section.** Every original failing repro passes on the published reflex 0.9.12a2 (+ reflex-enterprise 0.9.6a1): 96 checks passed, 0 failed, 2 skipped (enterprise prod behind the paid-tier gate; #6180 not measurable in this app — both skipped in the campaign too) across the five re-verification clusters; the regression sweep on the surfaces the fixes touch found no new reflex defect; the five new items surfaced are pre-existing or static-only in reflex-enterprise and none blocks.

Scope: release branch `r/pre-2026.09.18-35410916948` at `f223a0bff` = `main` `006543ab3` (all four reflex fix PRs
#7215/#7216/#7217/#7218 plus #7230) + changelog materialization; the a2 changelog lists exactly those five entries.
`check_release_versions.py` → all 19 packages published (reflex/reflex-base 0.9.12a2, components unchanged since a1);
`audit_pyi.py` → PASS, 122 stubs identical in wheel and sdist, no foreign stubs (`reverify-0.9.12a2/packaging/`).
reflex-enterprise 0.9.6a1 came as an offline wheel (`Requires-Dist: reflex[db]>=0.9.6`, still no upper bound).
Method as in the campaign: PyPI-only venvs (`a2`, `enta2` = a2 + rxe 0.9.6a1[mcp], baselines `prev` = 0.9.11.post1,
`shared` = 0.9.12a1, `ent` = a1 + rxe 0.9.5), five re-verification agents (Opus, xhigh) on reserved ports, an
independent adversarial verifier for every newly claimed issue. Artifacts: `reverify-0.9.12a2/<cluster>/NOTES.md`
(with `## VERIFICATION` appendices), `logs/`, `out/`, `shots/`; briefs in `reverify-0.9.12a2/briefs/`.

### Original failing repros, re-run against the published packages

| finding | issue / fix | repro (unchanged campaign script) | 0.9.11.post1 | 0.9.12a1 | 0.9.12a2 (+ rxe 0.9.6a1) | result |
|---|---|---|---|---|---|---|
| FINDING-001 | #7211 / #7215 | `orch_probes/metaclass_probe.py`, 3 cases | 3 OK | 2 FAIL (metaclass conflict) | 3 OK; `type(rx.State) is BaseStateMeta`; reserved names still rejected through a custom metaclass | **PASS** |
| FINDING-001 downstream | #7211 / rxe #232 | `ent_import_probe.py` (23 modules, 13 attrs), MCPPlugin-only and AuthPlugin-only apps, `demos/oidc` | 23/23, `/ping` 200 | 1 FAIL, `/ping` 000 | 23/23, BAD=0, `/ping` 200, `demos/oidc` builds — no shim anywhere | **PASS** |
| FINDING-003 | #7212 / #7216 | `pure_delta_memo.py` steps 3/4 | True/True | False/False | True/True | **PASS** |
| FINDING-003 (browser) | | `elapp` `/filtered` + `s_filtered.py`, dev memory and dev + redis | secret-1 / secret-3 | secret-0 / secret-2 | secret-1 / secret-3, zero console/page/network errors | **PASS** |
| FINDING-003 (enterprise) | | `@rxe.var(auth=True, cache=False)` right after OIDC login | immediate | stale until reload | immediate, stays correct across events and reload | **PASS** |
| FINDING-011 | #7214 / rxe #232 | `probe_router_redact.py` in-process | OK | LEAK (with rxe 0.9.5) | OK (and OK for rxe 0.9.6a1 on 0.9.11.post1: legacy `router` still redacted) | **PASS** |
| FINDING-011 (HTTP / MCP) | | unmodified `tickets` demo: `POST /_reflex/retrieve_state`, ndjson event delta, MCP `reflex://state/vars` reads | `router` blanked | not runnable (FINDING-001) | `rx_router_session` with `client_token`/`session_id` blanked, `client_ip` kept, on all three surfaces; UUID sweep finds only ticket ids | **PASS** |
| FINDING-017 | #7213 / #7217 | `break_reload_probe.py` at +10 s / +24 s after breaking the app module | REFUSED 0.00 s | TIMEOUT 6 s | REFUSED 0.00 s, 200 again 12 s after the fix | **PASS** |
| FINDING-017 (#7114 guard) | | 20 Hz `/ping` across two hot reloads | – | 0 refused | 806 requests, 0 refused, 0 errors; latency bumps only at the two edits | **PASS** |
| FINDING-017 (SIGTERM route) | | `sigterm_port_probe.py` at +8 s / +18 s | REFUSED | TIMEOUT 6 s | REFUSED (FINDING-018 itself unchanged, pre-existing) | **PASS** |
| FINDING-012 | #6143 / #7218 | `vapp` prod, default badge, `editor_probe.py` | fails (pre-existing) | `portal_exists=false`, 2× "portal not found" | `#portal` present, badge present, carousel opens with its images, no error; `root.jsx` shows badge and portal as siblings | **PASS** |
| #7230 (new in a2) | #7229 | own app: `self.router.*` writes from a background task outside `async with self`, from a substate, via `ReadOnlyStateProxy` | `ImmutableStateError` | **bypassed** (a1 regression) | `ImmutableStateError`; in-lock writes allowed and emit `rx_router_page` (a2 also emits from substates, where prev emitted nothing) | **PASS** |

### Regression sweep on the surfaces the fixes touch

- Smoke: blank app dev and prod driven in Chromium, zero console/page/network errors; generated `package.json`
  byte-identical to the a1 smoke copy (the `"mergician": "v2.0.2"` nit unchanged).
- Router / deltas: the `routerlab` 24-step matrix diffs to zero lines against the campaign (every event, delta size,
  key set); #6946 savings intact (24 delta frames / 15 274 B inbound, identical to a1; 0.9.11.post1 26 059 B);
  #7168 8/8 supersession shapes byte-identical; #7145 3000 self-chained ticks, no RecursionError.
- Dev server: hot reload reaches a held-open browser in ~1 s with the backend answering throughout; a syntax error
  saved mid-run refuses fast and recovers in 2 s; `--backend-only` + `--frontend-only` pair; `--json` logging
  intact (#7193); SIGINT to the process group exits 0 in ~1 s with no listener left.
- Components in prod: the 9-page gallery app diffs against the a1 prod results with zero differing keys for code,
  misc, plotly, props, sankey and toast; the only change is the data_editor overlay coming alive and three console
  errors disappearing.
- Enterprise (rxe 0.9.6a1 on a2, no shim): full OIDC browser flow (PKCE login, protected and background events,
  reload, second tab, RP-initiated logout) matches the 0.9.11.post1 run apart from ports; MCP resources/tools,
  `queue_event`, protected-handler enforcement, rate limiting (7×200 → 429 with Retry-After), garbage bearer 401,
  legacy SSE and streamable transports as recorded; demos map 13/13, dnd 18/18, flow 11/11, mantine 52/52, ag_grid 13
  routes identical to the campaign; tickets REST 401/401/401 + api-catalog 200; the tickets `/` UI, inert on
  0.9.10/0.9.11a1 and unstartable on a1, now hydrates and runs (rxe #231). Prod for enterprise demos stays behind
  the paid-tier gate (skipped, as in the campaign).
- Upgrade path: form-designer (reflex-local-auth 0.5.0 + `reflex[db]` + alembic), basic_crud (mounted FastAPI
  router) and data_visualisation (pandas, recharts, plotly, the campaign's `/pandas` probe page) upgraded IN PLACE
  from 0.9.11.post1 to a2 with `.web/`, `reflex.lock/` and sqlite preserved: every flow passes, first post-upgrade
  run is a ten-line clean recompile, pre-upgrade bcrypt logins and rows survive, cold `.web` rebuild converges,
  prod mode serves the authenticated flows; `package.json` drift is exactly react-router 8.3.1 → 8.4.0.
- Render / state managers: the `renderapp` render-count suite reproduces the campaign's a1 numbers — every
  event-driven scenario's render delta compares equal, the prod replay is identical mark for mark (127/54
  websocket frames on both); the #7159 StateManagerDisk probes match (debounce flushes the latest instance,
  `modify_state` from an API route persists, hot-reload survival, a shutdown flush of five pickles at the SIGTERM
  second with a 30 s debounce). #7216 exercised in a fresh app across dev/memory, dev/redis (1 worker) and
  prod/redis (2 workers): the withheld uncached var reads U0 → U3 → U4 → U5 on a2 where a1 reads U0 → U0 → U4 → U4,
  identical twelve-step table on all three managers, no stale value, duplicate frame, missing key or pickling
  error. #7218 generalizes: custom app wraps at priority −2 and −3 and the real data_editor portal all render
  beside the badge in prod (a1 renders only the +5 and 0 wraps); the memo_aschild app's uploads, toaster and a live
  toast coexist with the badge. memo_aschild's 52-check driver passes in dev and prod. Measurement correction for
  the campaign report: the initial `on_load` A/B/dual render count is bimodal (2 or 4) on 0.9.11.post1, a1 and a2
  alike (six fresh contexts each), so the campaign's "#6181 halves the on_load count" row should read
  "unchanged / not measurable in this app"; #6180 stays not observable here.

### New items surfaced by the re-verification (none blocks 0.9.12; all adversarially verified)

- **rxe 0.9.6a1 type-checks against the removed `reflex.istate.validation`** — `reflex_enterprise/auth/oidc/state.py:63`
  imports `_StateMeta` under `TYPE_CHECKING` from a module a2 deleted; the runtime branch (`type(rx.State)`) is what
  executes, all 110 rxe modules import, and 245 of 246 `from reflex…` imports in the wheel resolve. Static-only,
  LOW, confirmed by the verifier as isolated and narrower than claimed. Fixed and merged in reflex-enterprise
  [#235](https://github.com/reflex-dev/reflex-enterprise/pull/235): `OIDCCookieMeta` now derives from the public
  `reflex_base.vars.BaseStateMeta` (the metaclass of `rx.State` on every supported reflex), a new unit test
  executes every `TYPE_CHECKING` import in the package against the installed reflex, and the lock moves to
  0.9.12a2; verified on 0.9.6, 0.9.9 and 0.9.12a2.
- **rxe EventHandlerAPIPlugin `GET /_reflex/events/openapi.yaml` returns 500 unless `pyyaml` is installed** —
  Starlette's `parse_docstring` asserts on the missing package; same code and same missing dependency in rxe 0.9.5,
  so pre-existing. `/.well-known/api-catalog` (200) points at the failing URL. reflex-enterprise follow-up: declare
  `pyyaml` (or answer 501 with the explanation). The verifier rebuilt both venvs itself and ran the 0.9.11.post1 +
  rxe 0.9.5 baseline: identical 500, identical traceback; with `pyyaml` installed the endpoint serves a valid 34-path
  document. LOW–MEDIUM for reflex-enterprise, irrelevant to the reflex 0.9.12 decision.
- **HTTP 404 status for non-prerendered paths in prod** (page renders and hydrates, only the status is wrong) —
  byte-identical on 0.9.11.post1, a1 and a2; this is the campaign's `up_examples_b` finding, already tracked as
  #6983 / PR #6996. Not new.
- **`rx.accordion.root(collapsible=True, type="multiple")` React warning** — Radix only honours `collapsible` for
  `type="single"`, so the prop reaches the DOM and React warns in dev builds only; no DOM attribute, behaviour
  intact, identical on all three versions; reflex-examples' form-designer ships the combination. Docs nit at most.
- **Declaring `get_delta` on a State subclass is rejected at class creation** (`EventHandlerShadowsBuiltInStateMethodError`,
  raised for a plain mixin base too) — identical on 0.9.11.post1, a1 and a2 (only the raise site moved:
  `reflex/state.py` → `reflex/istate/validation.py` → `reflex_base/vars/base.py`), so pre-existing. The verifier
  reproduced it and refuted the headline: the rejection is the blanket reserved-member guard with a working opt-in,
  `@rx.state._override_base_method`, which makes the class-body override work on all four venvs (root state,
  substate, shared mixin) and is exactly what reflex-enterprise 0.9.6a1 ships (`auth/oidc/state.py:2541`); and
  `get_delta` is not a documented extension point (`docs/` never mentions it, the docstring describes monkeypatching).
  Downgraded to cosmetic: the error message could name the marker when the shadowed member is a method rather than a
  var. No release action.
- Mixed-version trap unchanged: `uv pip install --upgrade reflex==0.9.12a2` without `--prerelease=allow` moves only
  reflex/reflex-base; an app in that state still runs identically. Release-note line for the alpha; moot once
  0.9.12 is final (the bare pin then pulls the whole set).
- Confirmed unchanged, pre-existing, not re-reported: FINDING-018 (SIGTERM to the pid alone), granian's cosmetic
  `Unexpected exit from worker-1` on clean shutdown, FINDING-023/024/025 and FINDING-008, all re-run and identical field for field.
- Campaign artifact-copy gaps for the next runner (not reflex defects): `components_bumps/verification/vapp/` lacks
  `vapp/__init__.py`; `components_bumps/gallery/gallery/gallery.py:10` asserts the original explorer's venv path.

### Release conditions

1. Publish reflex-enterprise 0.9.6 (from #232, the 0.9.6a1 content) **no later than** reflex 0.9.12 and its
   related packages: the published rxe 0.9.5 has no upper bound on reflex, so a user who upgrades only reflex lands
   on the broken pair with no resolver warning. Put "reflex 0.9.12 requires reflex-enterprise >= 0.9.6" in both
   release notes.
2. After the final versions publish, run the stock-install smoke from the skill's Phase 7: `pip install reflex==0.9.12`
   with no prerelease flag, init, run, browser, and confirm the resolved graph is all-final (the component packages
   must have moved from their `a1` versions to finals in the same batch).
