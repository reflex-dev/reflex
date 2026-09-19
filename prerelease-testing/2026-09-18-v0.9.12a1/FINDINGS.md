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
- FINDING-003: a `@rx.var(cache=False)` withheld from a delivered delta by a downstream `get_delta` filter is never re-sent — #6946's last-sent memo is written at compute time (MEDIUM, regression, downstream-visible through reflex-enterprise auth) — claimed by `ent_mcp_oidc`, verification pending
- FINDING-004: the documented `deps=["router"]` deprecation warning never fires — the guard in `_init_var_dependency_dicts` is dead code (LOW, new in #7068) — claimed by `router_vars`, verification pending
- FINDING-005: any computed var reading `self.router` depends on all five router fields; a narrow `deps=[State.router.url]` cannot narrow; measured navigation delta −47% vs the PR's −67% (LOW, perf claim gap, #7068) — claimed by `router_vars`, verification pending
- FINDING-006: a substate shadowing a parent's backend (underscore) var is still silently ignored — #7077's guard covers base vars only (LOW, pre-existing gap) — claimed by `router_vars`, verification pending
- FINDING-007: PR #7136's description promises a `REFLEX_STATE_ALLOW_RESERVED_NAMES=1` escape hatch that does not exist in the published packages or the release branch (LOW, PR/migration-doc mismatch, maintainer decision) — claimed by `ent_mcp_oidc`

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
  All three start on 0.9.11.post1. With a test-only shim that forces the one class definition through
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

## FINDING-003: a withheld `@rx.var(cache=False)` is never re-sent once visible (MEDIUM, regression — claimed, verification pending)

- Cluster: `ent_mcp_oidc` | Regression vs 0.9.11.post1: yes (explorer ran both) | Verifier: pending; the
  `event_loop` explorer was asked to build a pure-reflex repro
- Repro (needs the FINDING-001 shim to run enterprise on 0.9.12a1): `ent_mcp_oidc/NOTES.md` ISSUE-2 and
  `scripts2/uncached_after_login.py` — an `@rxe.var(auth=True, cache=False)` stays at its compiled default
  through login and two further events; only a full reload shows the server value. 0.9.11.post1 shows it
  right after login. Evidence: `ent_mcp_oidc/logs/uncached_new.json`, `uncached_prev.json`, `shots/uncached_*.png`.
- Mechanism (explorer's analysis): #6946 records the last value an uncached var sent per client when the
  delta is computed, not when it is delivered; enterprise's `get_delta` override filters the protected
  entry out of the delta, so the memo says "sent" for a value the browser never received, and the next
  recomputation (same value) is deduped away. Any downstream delta filter, or any delivery failure between
  compute and emit, has the same exposure.

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

_(other clusters pending)_
