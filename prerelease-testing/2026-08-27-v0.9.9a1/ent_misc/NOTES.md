# ent_misc cluster — reflex-enterprise 0.9.4 (PyPI) on reflex 0.9.9a1

Scope: enterprise **mantine** demo, **flow** demo, **MCP plugin** (minimal app), **OIDC** demo.
All installs from PyPI only. Baselines with `reflex==0.9.8` where needed.
Date: 2026-08-28. Ports used: frontend 3380-3385, backend 8380-8386 (all released).

## TL;DR

| App | 0.9.9a1 | 0.9.8 baseline | Verdict |
| --- | --- | --- | --- |
| mantine demo | 11/11 browser checks pass, clean console | not run (nothing failed) | works |
| flow demo | **crashes at import**: `from reflex.page import DECORATED_PAGES` → ImportError; after a 2-line patch to the new API, 11/11 pass | original code runs unmodified, 11/11 | **REGRESSION** (app-level import removed by #6382) |
| MCP plugin (`rxe.MCPPlugin`) | 17/17 MCP-protocol checks pass | not run (nothing failed) | works |
| OIDC demo | 7/7 checks to the IdP boundary (mock IdP) | identical 7/7 | works as far as testable; `/_reflex/cookies/sync` 404s on BOTH versions (not a regression) |

FINDING-001 (`reflex_enterprise/vars.py:143` reads removed `dynamic.bundled_libraries`)
was **not** triggered by any app in this cluster: mantine, flow, the MCP app and the OIDC
demo never construct a `LambdaVar`, so they compile fine on 0.9.9a1. The breakage from
#6382 that *does* hit this cluster is a different removal from the same PR: see below.

## Setup common to all apps

- Venv per app dir: `uv venv <dir>/venv --python 3.11` then
  `uv pip install --python <dir>/venv/bin/python --prerelease=allow 'reflex==0.9.9a1' 'reflex-enterprise==0.9.4' [extras]`
  (baseline: `'reflex==0.9.8'`, no `--prerelease=allow` needed).
- **`CI=true` required**: `rxe.App()` calls `_check_login()`, prints
  ``"`reflex-enterprise` is free to use but you must be logged in"`` and `exit()`s when the
  user tier is anonymous. `CI=true` (or `REFLEX_BACKEND_ONLY`) bypasses it
  (reflex_enterprise/app.py `_check_login`). All runs here used
  `REFLEX_TELEMETRY_ENABLED=false CI=true`.
- Playwright drivers run with the shared driver venv
  (`$SB/envs/driver/bin/python`, chromium at `/opt/pw-browsers/chromium`), MCP driver with
  a dedicated venv (`mcp==1.29.0`, httpx). `NO_PROXY=localhost,127.0.0.1` set only on
  driver/curl processes, never on servers.
- Context note (both 0.9.8 and 0.9.9a1, NOT a regression): `reflex.__version__` raises
  `AttributeError: No reflex attribute __version__` (lazy_loader has no such attr).
  Use `importlib.metadata.version("reflex")`.

## 1. mantine demo (`mantine_099/`)

Source: `/home/user/reflex-enterprise/demos/mantine`, unmodified.
Run: `cd mantine_099 && REFLEX_TELEMETRY_ENABLED=false CI=true ./venv/bin/reflex run --frontend-port 3380 --backend-port 8380 --loglevel debug`
Drive: `$SB/envs/driver/bin/python drive_mantine.py http://localhost:3380 shots_mantine_099`

**11/11 pass on 0.9.9a1** (`shots/shots_mantine_099/results.json`): index cards/links; `/dates`
calendar renders 126 day cells; DatePicker day click fires `on_change` → `rx.toast("Date selected: ...")`;
TimeInput change → toast; `/pill` renders 7 pills, remove button → "Removed" toast + pill removed;
Source tab shows code block; `/tags-input` initial tags render, typing+Enter adds a tag through the
`on_change`→state→`value` round-trip, removing Tag1 round-trips too; radix Select dropdown navigation
`/tags-input`→`/dates` works. No console errors/warnings, no failed requests, no server-log tracebacks.
Baseline 0.9.8 skipped (nothing failed to compare).

Benign server-log lines: deprecations for string `disable_plugins` (demo code, 0.8.28),
`console.error` deprecation fired by the enterprise login-check path (0.9.9), implicit Radix
Themes enablement (0.9.0), bun "incorrect peer dependency react@19.2.8" warning.

## 2. flow demo (`flow_099/` patched, `flow_098/` pristine)

### REGRESSION: `from reflex.page import DECORATED_PAGES` removed in 0.9.9a1 (PR #6382)

The demo's own `flow/flow.py` line 2 does `from reflex.page import DECORATED_PAGES` to build
its index page. On 0.9.9a1 this crashes at import/compile:

```
File ".../flow/flow.py", line 2, in <module>
    from reflex.page import DECORATED_PAGES
ImportError: cannot import name 'DECORATED_PAGES' from 'PageNamespace' (unknown location)
```

- 0.9.8 `reflex/page.py` exposes module-level `DECORATED_PAGES` (a defaultdict, kept as a
  class attr on the `PageNamespace` that replaces the module in `sys.modules`). 0.9.9a1's
  `reflex/page.py` drops it entirely — pages now accumulate on
  `RegistrationContext.ensure_context().decorated_pages` (PR #6382, RegistrationContext work).
- The 6382 breaking-change note (`packages/reflex-base/news/6382.breaking.md`) documents the
  `bundled_libraries` move and `get_config(reload=True)`, but **not** the `DECORATED_PAGES`
  removal, and there is no shim — downstream code (including reflex-enterprise's own demo)
  gets a confusing ImportError naming `PageNamespace (unknown location)`.
- Minimal trigger: `venv/bin/python -c "from reflex.page import DECORATED_PAGES"` (works on
  0.9.8, ImportError on 0.9.9a1).

`flow_099/flow/flow.py` carries a documented try/except patch falling back to
`RegistrationContext.ensure_context().decorated_pages` (entries are the same
`(render_fn, kwargs)` tuples) purely to keep testing the rest of the demo.
`flow_098/` is the pristine demo.

### With the patch, everything else works on 0.9.9a1

Run: `cd flow_099 && REFLEX_TELEMETRY_ENABLED=false CI=true ./venv/bin/reflex run --frontend-port 3381 --backend-port 8381 --loglevel debug`
Drive: `$SB/envs/driver/bin/python drive_flow.py http://localhost:3381 shots_flow_099`

**11/11 pass** (`shots/shots_flow_099/results.json`): index links (6 pages); `/overview` renders
11 nodes / 6 edges / minimap / controls; real mouse-drag of a node moves it and the position
sticks through the `on_nodes_change` → `apply_node_changes` → state round-trip; node-toolbar
emoji button sets state (🚀→🔥); `/nodes/custom-node` renders; `/nodes/drag-handle` node drags
via the custom handle only (body drag correctly inert); `/nodes/connection-limit` handle-to-handle
drag creates an edge and the `is_connectable`/`get_node_connections` limit refuses a second edge;
`/nodes/add-node-on-edge-drop` dropping a connection on the pane creates a node+edge via
`on_connect_end` + `screen_to_flow_position`; `/nodes/intersections` dragging one node onto
another applies the highlight class. Zero console errors, zero page errors, zero 4xx/5xx.

Baseline: `flow_098` (reflex 0.9.8, **unpatched** demo) on ports 3382/8382 → same driver,
**11/11 pass**. So the ONLY 0.9.9a1 breakage in the flow demo is the `DECORATED_PAGES` import.

package.json diff 0.9.8→0.9.9a1 (`pkg/flow_package_deps_098_vs_099.diff`): react-router
7.18.2 → 8.3.0, `react-router-dom` dropped; xyflow/enterprise deps identical.

## 3. MCP plugin — minimal app (`mcp_app/`)

App: `mcp_app/rxconfig.py` (`rxe.Config(plugins=[rxe.MCPPlugin(configure=customize)])` with a
custom `ping` tool + `config://version` resource) and `mcp_app/mcp_app/mcp_app.py`
(`CounterState` with `increment(amount)`, `set_label_value`, computed `doubled`, and an
`@rxe.mcp.resource summary`). Install used the `reflex-enterprise[mcp]==0.9.4` extra
(pulls `mcp` SDK 1.29.0).

Run (backend only is enough): `cd mcp_app && REFLEX_TELEMETRY_ENABLED=false CI=true ./venv/bin/reflex run --backend-only --backend-port 8383 --loglevel debug`
Drive: `$SB/envs/ent_misc_drv/bin/python drive_mcp.py http://localhost:8383 mcp_results_099.json`
(driver venv: `uv pip install 'mcp==1.29.0' httpx` — note `mcp` 2.0.0 renamed
`streamablehttp_client`→`streamable_http_client`; the driver uses the 1.x name).

**17/17 pass on 0.9.9a1** (`mcp_results_099.json`), i.e. the MCP plugin is fully functional:

- `POST /_reflex/auth/token` issues an anonymous bearer (200, `expires_in 3600`).
- `/_reflex/mcp` without a bearer → 401 (after following the 307 redirect to `/_reflex/mcp/`;
  clients POSTing exactly `/_reflex/mcp` get a 307 first — minor quirk, MCP SDK handles it).
- initialize returns generated instructions ("# mcp_app MCP (v1.0.0) ... 2 event handler(s)").
- tools: `ping` (custom, returns "pong"), `search_events`, `queue_event`.
- resources: `config://version` (custom), `reflex://event`, `reflex://state`, and the no-arg
  `@rxe.mcp.resource` advertised concretely as `state-resource://mcp_app____counter_state/summary`
  (arg-less resources appear in resources/list, not templates — templates hold the four
  `reflex://...{var}` families).
- `search_events("increment")` finds `mcp_app____counter_state.increment` with schema+rest_path.
- `queue_event` increment(5) twice → deltas show count 5 then 10 (session persists across calls
  on one bearer). First call's delta also contains the root state/router (hydrate seeding).
- `reflex://state/vars/reflex___state____state.mcp_app____counter_state` returns live vars
  `{"count": 10, "doubled": 20, "label": "hello"}`; `/doubled` marks the computed var dirty and
  recomputes (20); `state-resource://.../summary` returns `{"count": 10, "label": "hello"}`;
  `reflex://event/<name>` returns the handler schema.

Startup anomalies (benign, logged in `logs/mcp_app_server.log`): a
`pydantic_settings ... IncompleteFieldDefinitionWarning: Field 'lifespan' has an incomplete
definition` warning from the mcp SDK's Settings model, and the in-memory API-token-store notice.
No baseline needed (nothing broken).

Note on state naming: tools (`queue_event`, `search_events`, `state-resource://`) use the short
name `mcp_app____counter_state`; `reflex://state/vars/...` requires the fully-qualified
`reflex___state____state.mcp_app____counter_state` (listed by `reflex://state`). Passing the
short name to state/vars errors with a helpful message.

## 4. OIDC demo (`oidc_099/`, baseline `oidc_098/`)

No external IdP available, so the run uses `mock_idp.py` — a stdlib HTTP server on
`http://localhost:8385` serving the OIDC discovery document, an empty JWKS, an `/authorize`
page that echoes its query params, and a `/token` endpoint that always returns
400 `invalid_grant`. localhost is proxy-exempt in this environment, so the backend's
server-side discovery fetch reaches it without touching proxy config.

Run:
```
python3 mock_idp.py 8385 &
cd oidc_099 && REFLEX_TELEMETRY_ENABLED=false CI=true \
  OKTA_ISSUER_URI=http://localhost:8385 OKTA_CLIENT_ID=dummy-okta-client OKTA_CLIENT_SECRET=dummy-okta-secret \
  DATABRICKS_ISSUER_URI=http://localhost:8385 DATABRICKS_CLIENT_ID=dummy-dbx-client DATABRICKS_CLIENT_SECRET=dummy-dbx-secret \
  ./venv/bin/reflex run --frontend-port 3384 --backend-port 8384 --loglevel debug
```
(Env-var scheme: `{PROVIDER}_{KEY}` falling back to `OIDC_{KEY}`; keys `ISSUER_URI`,
`CLIENT_ID`, `CLIENT_SECRET` — reflex_enterprise/auth/oidc/config.py.)
Drive: `$SB/envs/driver/bin/python drive_oidc.py http://localhost:3384 shots_oidc_099`

**7/7 pass on 0.9.9a1** (`shots/shots_oidc_099/results.json`):

- Index renders both provider cards with "Login with Okta"/"Login with Databricks" buttons.
- "Do Nothing" event and "Cookie Sync" click produce no page errors (but see anomaly below).
- Clicking Okta login: backend fetches `/.well-known/openid-configuration` from the issuer and
  redirects the browser to the mock `/authorize` with a fully correct request:
  `client_id=dummy-okta-client`, `redirect_uri=http://localhost:3384/_reflex_oidc_okta/authorization-code/callback`,
  `scope=openid email profile`, opaque `state`, PKCE `code_challenge` + `code_challenge_method=S256`,
  `response_type=code`, `response_mode=query` (screenshot `02_okta_authorize_redirect.png`).
- Databricks login carries the subclass's `_requested_scopes` (`all-apis offline_access openid
  email profile`) and its own client_id/callback (`_reflex_oidc_databricks/...`).
- Callback wiring: GET the real `redirect_uri` with `code=bogus-code` + the real `state` →
  backend runs the full callback (server log: "Processing auth callback" → "Exchanging
  authorization code for tokens"), POSTs the mock `/token`, and the mock's 400 surfaces as a
  clean logged `RuntimeError: Token request failed with status 400: {"error": "invalid_grant"...}`
  — no crash, page still serves.
- `/iframe` page renders the app in an iframe.

**What genuinely needs a real IdP** (untestable here): successful token exchange + ID-token
signature validation against a real JWKS, `userinfo` display, logout redirect
(`end_session_endpoint`), access-token refresh and `_on_access_token_change`, and the
iframe/popup post-message auth completion.

### Anomaly (BOTH versions — not a regression): `/_reflex/cookies/sync` → 404

Clicking "Cookie Sync" (`HTTPCookie.sync()`) POSTs `http://localhost:<backend>/_reflex/cookies/sync`
and gets **404** on 0.9.9a1 AND on the 0.9.8 baseline (`shots/shots_oidc_09*/results.json`,
req_failures). `HTTPCookie.sync()` registers the route at compile time via
`get_app().app._api.routes.insert(0, Route("/_reflex/cookies/sync", ...))`
(reflex_enterprise/auth/cookie.py `ensure_handlers_registered`), which evidently never lands in
the serving backend worker in this demo shape (deprecated `register_auth_endpoints()` path, no
`rxe.AuthPlugin`). Likely an enterprise-side issue rather than a 0.9.9a1 one; recorded for the
enterprise team. The demo otherwise functions.

Baseline: `oidc_098` (reflex 0.9.8), ports 3385/8386, same env/driver → identical 7/7 and the
same cookies/sync 404. The mock's `/favicon.ico` 404 in the browser console is the mock IdP's
own, not the app's.

## Rerun quickstart

```
SB=/tmp/claude-0/-home-user-reflex/20b6ffc8-8244-5bac-b158-8501871b3811/scratchpad   # or any scratch dir
# per app dir: create venv + install as in "Setup" above, then use the run+drive commands
# in each section. Drivers live next to this file; screenshots land in the dir you pass.
```

Servers were run one at a time; all PIDs killed and ports verified free afterwards.
