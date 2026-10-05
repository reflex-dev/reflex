# Exposing a Reflex app over MCP

`reflex_enterprise.MCPPlugin` publishes your app's event handlers as
[Model Context Protocol](https://modelcontextprotocol.io) tools, so an AI agent
can drive the app directly — search the available handlers, apply events, and
read back session state.

```bash
pip install "reflex-enterprise[mcp]"     # brings in the MCP SDK
```

```python
# rxconfig.py
import reflex_enterprise as rxe

config = rxe.Config(
    app_name="my_app",
    plugins=[rxe.MCPPlugin()],
)
```

A streamable-HTTP MCP server is mounted at `/_reflex/mcp` exposing two tools:

- `search_events(query)` — free-text search over the app's handlers, returning
  each handler's name and payload schema. The server-side-filtered entry point,
  best for large apps.
- `queue_event(event_name, payload, query)` — apply an event and return the
  resulting state delta. For a file-upload handler it instead returns directions
  for POSTing the files to the upload endpoint out of band.

plus a `reflex://` **resource** family for introspecting and reading the app:

- `reflex://state` — the exposed state names.
- `reflex://event` — enumerate the event handlers; `reflex://event/<event_name>`
  for one handler's full schema (the flat-enumeration alternative to
  `search_events`).
- `reflex://state/events/<state_name>` — the event handlers defined on a state.
- `reflex://state/vars/<state_name>` — the session's live state rooted at a
  state (the resolved `.dict()` — cached frontend + computed var values; read
  the root `reflex___state____state` for the whole app).
- `reflex://state/vars/<state_name>/<var_name>` — a single var's live value; a
  computed var is marked dirty and **recomputed** rather than served from cache.

The `reflex://state/vars/...` resources read session state — the session bound
to the caller's bearer token. The metadata resources (`reflex://state`,
`reflex://event`, ...) are session-independent.

On connect the server advertises auto-generated `instructions` describing the
app, its pages, dynamic route variables, and the authentication model. Pass
`MCPPlugin(instructions=...)` to override the generated text.

## Authentication

Every request to the MCP endpoint (and the REST event API) requires an
**app-issued bearer token** — a caller-invented UUID or client token is never
accepted, and no tool takes a `token` argument. This is the core hardening of
the agent surface: because the underlying Reflex session token is
**server-generated and never leaves the server**, an API credential can only
ever address its own dedicated session — never a browser session or another
agent's — and the number of sessions a client can create is bounded by rate
limits.

Tokens come from one of two places, and the client/agent may choose either
when both are available:

### Anonymous sessions — the token endpoint

`POST /_reflex/auth/token` returns an opaque bearer bound to a fresh,
server-generated anonymous session:

```bash
curl -X POST https://my-app.example/_reflex/auth/token
# {"access_token": "...", "token_type": "Bearer", "expires_in": 3600,
#  "session": "anonymous"}
```

Use it as `Authorization: Bearer <access_token>` on the MCP endpoint (or the
REST API). Reuse the token across calls to address the same session; when it
expires, request a new one (which is a new, blank session).

Anonymous sessions carry **no user identity**: with an `AuthPlugin` configured,
only `auth=False` handlers and vars are reachable through one. Without an
`AuthPlugin` this is the only token source. The endpoint is **rate limited per
client IP** (`token_rate_limit`, default 10/minute) because every grant seeds a
server-side session that consumes memory; disable anonymous sessions entirely
with `MCPPlugin(anonymous_sessions=False)` when agents must always act as a
signed-in user.

### With an `AuthPlugin` — OAuth 2.1

When an `AuthPlugin` is configured, `MCPPlugin` turns the app into a
spec-compliant **OAuth 2.1 Authorization Server + Resource Server** for the MCP
endpoint, and **federates the human login to your existing OIDC providers**. No
extra configuration is required — it is on by default (pass `auth=False` to
keep the endpoint anonymous-only even alongside an `AuthPlugin`):

```python
config = rxe.Config(
    app_name="my_app",
    plugins=[rxe.AuthPlugin(), rxe.MCPPlugin()],
)
```

How it works:

1. An unauthenticated MCP request gets `401` with a `WWW-Authenticate` header
   pointing at the app's protected-resource metadata
   ([RFC 9728](https://www.rfc-editor.org/rfc/rfc9728)).
2. The client discovers the authorization server
   ([RFC 8414](https://www.rfc-editor.org/rfc/rfc8414)) and registers itself
   dynamically ([RFC 7591](https://www.rfc-editor.org/rfc/rfc7591)).
3. The client opens the authorization endpoint in a browser. The app redirects
   to a **consent page** — a normal authenticated Reflex page, so the page guard
   bounces an anonymous visitor through your standard `/login` palette (any
   configured provider) and back.
4. The human approves — individually ticking any developer-defined
   [app scopes](#app-specific-scopes) they want to grant. The app snapshots
   the login server-side, mints a single-use authorization code, and completes
   the OAuth exchange with **its own opaque, resource-bound access + refresh
   tokens** (PKCE verified) carrying exactly the granted scopes.

The MCP client only ever holds tokens the app issued for its own MCP endpoint.
Upstream identity-provider tokens never leave the server. Each token is bound to
a dedicated server-side session, so the **entire enforcement stack applies to
agent traffic unchanged**: the per-event `AuthMiddleware` gate, callable
`auth=` checks, delta filtering, multi-provider selection, and
`AuthUserState.current()` all work exactly as they do for a browser user.
Because sessions are not authentication, the OAuth-mode tools take **no `token`
argument** — the session is derived from the validated bearer token.

Upstream token refresh happens server-side. If the upstream login expires and
cannot be refreshed, the token is revoked and the tool returns a clear
"re-authenticate" error so the client re-runs the flow.

#### Consent and the confused-deputy protection

Because a logged-in browser often skips the identity provider's own consent
screen, the app's consent page is the human checkpoint that stops a malicious
MCP client from silently acting as the user. It always shows the client's name
alongside the exact redirect host the authorization code will be sent to, and
requires an explicit **Approve** click — a prior approval is surfaced as a
"you have authorized this client before" hint but never silently auto-submits.
Consent is recorded per `(user, client, redirect URI)` for the audit trail.

The consent route is served with `X-Frame-Options: DENY` and
`frame-ancestors 'none'`, so it cannot be embedded — the primary clickjacking
defense. In a **split frontend/backend deployment** (the SPA is served from a
different origin than the backend), those response headers are applied by the
backend and do not cover the separately-served consent HTML; configure your
frontend host/CDN to send the same anti-framing headers for the consent route.
The approve handler additionally refuses to run inside a detected iframe as
best-effort defense-in-depth.

Customize the consent page with the same builder contract as the `AuthPlugin`
pages:

```python
rxe.MCPPlugin(consent_page="my_app.mcp.consent_page")
```

#### Configuration

Common `MCPPlugin` options for OAuth mode:

| Option | Default | Purpose |
| --- | --- | --- |
| `auth` | `None` | `None` = OAuth on iff an `AuthPlugin` is configured; `True` forces it (requires an `AuthPlugin`); `False` keeps the endpoint anonymous-only. |
| `expose_events` | `True` | Whether the app's event handlers are exposed (`search_events`/`queue_event` + event metadata). `False` publishes only state resources, `rxe.mcp.resource` methods, and `configure=` additions. |
| `anonymous_sessions` | `True` | Serve the anonymous token endpoint alongside OAuth (always effectively on when OAuth is off). |
| `anonymous_session_ttl` | 1h | Anonymous token lifetime (no refresh — a new token is a new session). |
| `token_rate_limit` / `token_rate_window` | 10 / 60s | Per-client-IP cap on anonymous token grants. |
| `call_rate_limit` / `call_rate_window` | 60 / 60s | Per-session-token cap on MCP calls; per-handler override via `rxe.event(rate_limit=...)`. |
| `issuer_url` | config `deploy_url`/`api_url` | Public origin serving the OAuth endpoints. Must be `https` in production (see below). Set explicitly behind a reverse proxy whose public origin differs. |
| `consent_path` | `/agent-consent` | Frontend route of the consent page (shared by the OAuth and token-grant paths). |
| `app_scopes` | `None` | Developer-defined scopes (`{name: description}`) offered as individually grantable checkboxes on the consent screen. |
| `required_scopes` | `None` | Scopes a token must carry to reach the MCP endpoint (anonymous tokens carry none, so setting this disables anonymous access). |
| `access_token_ttl` / `refresh_token_ttl` | 1h / 30d | Issued-token lifetimes (refresh rotates on use). |
| `enable_dynamic_client_registration` | `True` | Serve RFC 7591 dynamic client registration (at `registration_path`). |
| `registration_path` | `/register-oidc-client` | Origin-root path of the client registration endpoint (not the SDK's bare `/register`, which would shadow an app's own sign-up page). Clients discover it from the AS metadata. |
| `authorization_path` / `token_path` / `revocation_path` | `/authorize` / `/token` / `/revoke` | Origin-root paths of the other OAuth endpoints. Also front-inserted and discovered from the AS metadata; override any that collide with the app's own routes. Each must be distinct and not under the MCP mount. |
| `auth_store` | auto | Override token/consent storage. Defaults to Redis when the app's state manager is Redis, otherwise in-process. |
| `pending_updates` | `"drop"` | How followup state deltas for an MCP session are handled (see below). |

#### App-specific scopes

Finding *"authorizing a client grants the agent the user's full authority"* is
addressed with developer-defined, app-specific scopes. Declare them on the
plugin:

```python
rxe.MCPPlugin(
    app_scopes={
        "orders:read": "Read your order history",
        "orders:write": "Place and modify orders",
    },
)
```

Each app scope appears on the consent screen as an **individually grantable
checkbox** (a scope the client requested starts ticked, others unticked). The
minted access/refresh tokens carry exactly the scopes the human granted —
uniformly, for every configured IdP, instead of relying on each IdP's own
scope behavior. App scopes are automatically advertised in the OAuth metadata
so clients may request them; add them to `default_scopes` to have dynamic
registrations request them by default (pre-ticking the boxes).

#### Surface-aware auth checks (`ctx.surface` / `ctx.token_scopes`)

Granted scopes are enforced in your own `auth=` checks: every auth context
(event, var, page) carries the **access surface** the request arrived through
and the **scopes of the app-issued token** mediating it:

- `ctx.surface` — `"browser"` (the normal websocket path), `"event_api"`
  (the REST plugin), or `"mcp"`.
- `ctx.token_scopes` — `None` for a browser request (the user's full
  authority; no token restricts it), a tuple for an API request: the
  consent-granted scopes of an OAuth token, or `()` for an anonymous session.

Use them **restrictively** — require a scope when the access is
token-mediated, never treat a scope as granting more than the user could do
from a browser:

```python
def can_write_orders(ctx) -> bool:
    # Browser users keep their normal authority; an agent needs the grant.
    return ctx.token_scopes is None or "orders:write" in ctx.token_scopes

class OrderState(rx.State):
    @rxe.event(auth=can_write_orders)
    def place_order(self, item_id: str): ...
```

This is deliberately identity-*and*-surface-based: the same signed-in user
keeps full access in the browser while their delegated agent is limited to
what they ticked on the consent screen. (There is intentionally no per-handler
"hide from MCP" flag — the point of the MCP surface is exposing the app; use
`auth=` checks over `ctx.surface`/`ctx.token_scopes` to restrict actions, or
`expose_events=False` to publish no event surface at all.)

#### Per-token call rate limiting

Every MCP call (and REST API call) is counted against the presenting session
token: `call_rate_limit` per `call_rate_window` (default 60/minute), tracked
per process. Exceeding it returns a clear retry-after error. Individual
handlers can override their own budget where the default is wrong:

```python
class ReportState(rx.State):
    @rxe.event(rate_limit=2, rate_limit_window=60.0)
    def generate_expensive_report(self): ...

    @rxe.event(rate_limit=0)   # exempt from per-token limiting
    def cheap_ping(self): ...
```

Overridden handlers are counted in their own per-token bucket; everything else
shares the token's default bucket. Browser (websocket) events are never rate
limited by this mechanism.

#### Backend-only sessions and followup deltas

An MCP session has no browser websocket. The delta an event produces is returned
inline by `queue_event`, and full state by the `reflex://state/vars/...`
resource, so there is no connection to push to. Reflex still routes *followup* deltas — chained events,
background-task results, cookie syncs, the per-event auth bookkeeping — to a
session by token. For an MCP session those are dropped by default
(`pending_updates="drop"`); the session is also seeded so the page
hydrate/`on_load` chain does not re-run on every tool call.

Set `pending_updates="queue"` to buffer those followup deltas instead; a
`get_pending_updates` tool is then exposed that returns and clears them, so an
agent can retrieve out-of-band updates (e.g. a background task's result) on a
subsequent call.

## Production deployment

### TLS is required

The internal OAuth authorization server hands out **bearer credentials** —
authorization codes on redirect URLs, and access/refresh tokens on the token
endpoint. Over plain HTTP those are readable (and replayable) by any on-path
observer, so the OAuth issuer **must be served over `https`**.

This is enforced at wiring time: when MCP OAuth is enabled, a resolved issuer
(`MCPPlugin(issuer_url=...)`, or the config's `deploy_url`/`api_url`) that is
plain `http` on a non-loopback host fails startup with a `ConfigError`.
`http://localhost` / `http://127.0.0.1` / `http://[::1]` remain allowed so
local development works without certificates.

In the common production shape — TLS terminated at a reverse proxy in front of
the app — set `issuer_url` (or `deploy_url`/`api_url`) to the **public
`https` origin** the proxy serves, and set `registration_trusted_proxy_hops`
to the number of trusted proxies so the per-IP rate limiters (dynamic client
registration and the anonymous token endpoint) key on the real client address
from `X-Forwarded-For` instead of the proxy's. The anonymous token endpoint
and the REST API carry bearer tokens on every request, so they need the same
TLS protection even when OAuth is off.

### Storage

Tokens, pending authorizations, and consent records are stored in **Redis**
when the app is configured with a `redis_url`, and **in-process** otherwise.
The in-memory store is fine for a single-process app or development, but it
does not survive a restart and is not shared across workers — configure Redis
for multi-worker or production deployments so agents don't have to
re-authenticate after every restart or land on a worker that doesn't recognize
their token.

The OAuth discovery documents bake in the app's public origin. If neither
`issuer_url` nor the config's `deploy_url`/`api_url` is set, wiring fails fast
with a `ConfigError`.

### Rate limits

Three per-process limiters protect the endpoints an unauthenticated or
low-trust caller can reach (multi-worker deployments limit per worker):

- `registration_rate_limit` — RFC 7591 dynamic client registration, per IP.
- `token_rate_limit` — anonymous session grants, per IP (each grant seeds a
  server-side session).
- `call_rate_limit` — MCP/REST calls, per session token, with per-handler
  `rxe.event(rate_limit=...)` overrides.

Tune them to your traffic; setting any to `0` disables that limiter (not
recommended in production).

## Custom state resources (`rxe.mcp.resource`)

`queue_event` drives your event handlers (actions). For the read side, decorate
a state method with `rxe.mcp.resource` to expose it as a **var-like, read-only
MCP resource**: a computed value that can take arguments and is tied to the
caller's session state. It is registered as a top-level resource — **not** an
event handler — so it never appears in `search_events` / `queue_event`.

```python
class DashboardState(rx.State):
    orders: list[dict] = []

    @rxe.mcp.resource
    def order_count(self) -> int:
        """How many orders the current user has."""
        return len(self.orders)

    @rxe.mcp.resource(auth=admins_only)
    def revenue(self, quarter: str) -> dict:
        """Revenue for a quarter (admins only)."""
        return {"quarter": quarter, "total": self._revenue_for(quarter)}
```

The method runs against the caller's live session state and its return value is
the resource content. Its parameters become URI-template variables (each a
required path segment), so the resources above are addressed as:

```
state-resource://<state>/order_count
state-resource://<state>/revenue/{quarter}
```

where `<state>` is the state's fully-qualified (module-prefixed) name — the same
naming `search_events` uses. The resources are advertised in the server
`instructions` and via the standard `resources/templates/list`.

`auth=` takes the same values as `rxe.var` — `True` (any authenticated user,
the default), `False` (public), or a `check(ctx) -> bool` callable whose
`ctx.auth_user_state` carries the user (plus `ctx.surface` /
`ctx.token_scopes`) — and is enforced whenever an `AuthPlugin` provides
identity. The session is always the one bound to the caller's bearer token; an
anonymous session has no user, so only `auth=False` resources are readable
with one.

Resources are read-only by contract (like a computed var); drive state changes
through `queue_event`.

## Extending the server

Beyond the built-in tools and `reflex://` resources, you can add your own tools,
resources, and prompts to the underlying [`FastMCP`](https://modelcontextprotocol.io)
server. There are two ways in, both handing you the same instance.

### At build time — `configure=`

Pass `MCPPlugin(configure=...)` a callable (or a `"module.function"` import
path). It is invoked as `configure(server)` once the built-in tools/resource are
registered and **before the server is mounted**, so anything you register is
serving from the first request:

```python
def customize(server):
    @server.tool()
    def ping() -> str:
        return "pong"

    @server.resource("config://version")
    def version() -> str:
        return "1.0.0"

config = rxe.Config(
    app_name="my_app",
    plugins=[rxe.MCPPlugin(configure=customize)],
)
```

A tool or resource that declares a `Context`-typed parameter has it injected by
FastMCP, giving you the active request / session — the same mechanism the
built-in OAuth-mode tools use to resolve the caller's session.

### At runtime — `get_mcp_server()`

If you would rather register from application code (for example a reflex
lifespan task), grab the active server with `reflex_enterprise.get_mcp_server()`:

```python
import reflex_enterprise as rxe

@rxe.get_mcp_server().tool()
def ping() -> str:
    return "pong"
```

The server is built when the app is **compiled**, so `get_mcp_server()` (and the
equivalent `plugin.get_mcp_server()` instance method) raise a `RuntimeError`
until then — call them after compile, or use `configure=` for setup-time
customization. If you register tools after the transport is already serving,
connected clients see them on their next `tools/list`.

## What is exposed

Both `MCPPlugin` and `EventHandlerAPIPlugin` expose only your application's own
event handlers. Framework and auth handlers — every OIDC provider (including
your own `OIDCAuthState` subclasses), the login/logout/callback dispatchers, the
page guard, and other `reflex`/`reflex_enterprise` internals — are withheld, so
an agent cannot drive the login flow by queueing its events. Agents authenticate
through the token endpoint or the OAuth flow above instead.

To expose **no** event surface over MCP at all — only session-state reading,
`rxe.mcp.resource` methods, and your own `configure=` tools — pass
`MCPPlugin(expose_events=False)`.
