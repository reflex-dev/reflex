---
title: MCP Authentication
---

_New in reflex-enterprise v0.9.4._

# MCP Authentication

Every request to the MCP endpoint — and to the
[Event Handler API](/docs/enterprise/event-handler-api/) REST endpoints —
requires an **app-issued bearer token**. A caller-invented UUID is never
accepted, and no MCP tool takes a `token` argument.

That is the core of the model: the underlying Reflex session token is
**server-generated and never leaves the server**, so a credential can only ever
address its own dedicated session — never a browser session, never another
agent's — and the number of sessions a client can create is bounded by rate
limits.

Tokens come from one of two places. When both are available the client picks.

## Anonymous sessions

`POST /_reflex/auth/token` returns an opaque bearer bound to a fresh,
server-generated anonymous session:

```bash
curl -X POST https://my-app.example/_reflex/auth/token
```

```json
{
  "access_token": "…",
  "token_type": "Bearer",
  "expires_in": 3600,
  "session": "anonymous"
}
```

Send it as `Authorization: Bearer <access_token>` on the MCP endpoint (or the
REST API). Reuse the token across calls to address the same session; when it
expires, request a new one — which is a new, blank session, since anonymous
tokens have no refresh.

Anonymous access and OAuth coexist — in fact that is the default with an
[`AuthPlugin`](/docs/enterprise/auth/overview/) configured. Both token
authorities are wired, and the endpoint accepts a bearer from either, so an
agent that does not need to act as a user can skip the login flow entirely.

Anonymous sessions carry **no user identity**, though. With an `AuthPlugin`
configured, that means:

- `queue_event` refuses any handler that is not `auth=False`, with an
  actionable error rather than a silent redirect delta.
- Protected vars are withheld from the `reflex://state/vars/...` reads, and
  only `auth=False` [`rxe.mcp.resource`](/docs/enterprise/mcp/custom-resources/)
  methods resolve.
- `AuthUserState.current()` has no user.

Handler metadata (`search_events`, `reflex://event`) stays readable either way.
Without an `AuthPlugin` this is the only token source.

The endpoint is rate limited per client IP (`token_rate_limit`, default 10 per
minute) because every grant seeds a server-side session that consumes memory.

Two ways to require a signed-in agent instead:

```python
rxe.MCPPlugin(anonymous_sessions=False)  # MCP rejects anonymous bearers
rxe.MCPPlugin(required_scopes=["orders:read"])  # anonymous tokens carry no scopes
```

```md alert info
# The token endpoint is shared with `EventHandlerAPIPlugin`.
Whichever plugin wires it first decides its settings (TTL, rate limit), and the route is served if *either* plugin enables it. `anonymous_sessions=False` on `MCPPlugin` always makes the MCP endpoint reject anonymous bearers — but the REST surface keeps accepting any token the shared endpoint mints, so set it on both plugins to stop issuing them at all.
```

## OAuth 2.1 with an `AuthPlugin`

When an `AuthPlugin` is configured, `MCPPlugin` turns the app into a
spec-compliant **OAuth 2.1 Authorization Server + Resource Server** for its MCP
endpoint, and federates the human login to your existing OIDC providers. No
extra configuration is required — it is on by default:

```python
config = rxe.Config(
    app_name="my_app",
    plugins=[rxe.AuthPlugin(), rxe.MCPPlugin()],
)
```

Pass `MCPPlugin(auth=False)` to keep the endpoint anonymous-only even alongside
an `AuthPlugin`, or `auth=True` to require the OAuth flow (which fails fast if
no `AuthPlugin` is configured).

### How the flow runs

1. An unauthenticated MCP request gets a `401` with a `WWW-Authenticate` header
   pointing at the app's protected-resource metadata
   ([RFC 9728](https://www.rfc-editor.org/rfc/rfc9728)).
2. The client discovers the authorization server
   ([RFC 8414](https://www.rfc-editor.org/rfc/rfc8414)) and registers itself
   dynamically ([RFC 7591](https://www.rfc-editor.org/rfc/rfc7591)).
3. The client opens the authorization endpoint in a browser. The app redirects
   to a **consent page** — a normal authenticated Reflex page, so the page guard
   bounces an anonymous visitor through your standard `/login` palette (any
   configured provider) and back.
4. The human approves, ticking whichever [app scopes](#app-specific-scopes)
   they want to grant. The app snapshots the login server-side, mints a
   single-use authorization code, and completes the exchange with **its own
   opaque, resource-bound access + refresh tokens** (PKCE verified) carrying
   exactly the granted scopes.

| Endpoint | Purpose |
| --- | --- |
| `/.well-known/oauth-protected-resource/_reflex/mcp` | RFC 9728 protected-resource metadata for the MCP endpoint. |
| `/.well-known/oauth-authorization-server` | RFC 8414 authorization-server metadata. |
| `/register-oidc-client` | RFC 7591 dynamic client registration (rate limited per IP; disable with `enable_dynamic_client_registration=False`). |
| `/authorize` | Authorization endpoint — redirects to the consent page. |
| `/token` | Token endpoint (authorization code + refresh grant, refresh rotates on use). |
| `/revoke` | RFC 7009 revocation (disable with `enable_token_revocation=False`). |

Those four endpoints are served at the **origin root**, ahead of the app's own
routes, and clients only ever reach them through the metadata document — so
their paths are configurable when one would collide with a page you serve:

```python
rxe.MCPPlugin(
    registration_path="/register-oidc-client",  # the default
    authorization_path="/authorize",
    token_path="/token",
    revocation_path="/revoke",
)
```

Registration defaults to `/register-oidc-client` rather than the MCP SDK's bare
`/register` precisely because that path is a common sign-up route the OAuth
endpoint would otherwise shadow. Each path must be distinct and must not live
under the MCP mount, which is checked at wiring time.

The MCP client only ever holds tokens the app issued for its own MCP endpoint;
upstream identity-provider tokens never leave the server. Upstream refresh
happens server-side, and if the upstream login expires and cannot be refreshed
the app-issued token is revoked and the tool returns a clear "re-authenticate"
error so the client re-runs the flow.

Because each token is bound to a dedicated server-side session, the **entire
enforcement stack applies to agent traffic unchanged**: the per-event
`AuthMiddleware` gate, callable `auth=` checks, delta filtering, multi-provider
selection, and `AuthUserState.current()` all behave exactly as they do for a
browser user.

### Consent and the confused-deputy problem

A logged-in browser usually skips the identity provider's own consent screen,
so the app's consent page is the human checkpoint that stops a malicious MCP
client from silently acting as the user. It always shows the client's name
**alongside the exact redirect host** the authorization code will be sent to
(the name comes from dynamic registration and is therefore attacker-controlled;
the host is not), and requires an explicit **Approve** click. A prior approval
is surfaced as a "you have authorized this client before" hint but never
auto-submits. Consent is recorded per `(user, client, redirect URI)` for the
audit trail.

The consent route is served with `X-Frame-Options: DENY` and
`frame-ancestors 'none'`, the primary clickjacking defense, and the approve
handler additionally refuses to run inside a detected iframe.

```md alert warning
# Split frontend/backend deployments
When the SPA is served from a different origin than the backend, those response headers are applied by the backend and do not cover the separately-served consent HTML. Configure your frontend host or CDN to send the same anti-framing headers for the consent route.
```

### Customizing the consent page

The page lives at `/agent-consent` by default (`consent_path=`, which must not
be under the MCP mount). Replace the component with the same builder contract
as the [`AuthPlugin` pages](/docs/enterprise/auth/custom-pages/):

```python
rxe.MCPPlugin(consent_page="my_app.mcp.consent_page")
```

The builder is called with a `plugin=` keyword argument and returns a
component. Render it against `MCPConsentState`, which exposes `client_name`,
`redirect_uri`, `redirect_host`, `requested_scopes`, `app_scope_options`,
`app_scope_grants`, `previously_authorized`, `error_message`, and `ready`,
plus the `approve`, `deny`, and `set_app_scope_grant` handlers:

```python
import reflex as rx
from reflex_enterprise.plugins.mcp_auth.consent_state import MCPConsentState


def consent_page(**context) -> rx.Component:
    return rx.vstack(
        rx.heading(f"Authorize {MCPConsentState.client_name}"),
        rx.text(
            f"The authorization code will be sent to {MCPConsentState.redirect_host}"
        ),
        rx.hstack(
            rx.button(
                "Approve",
                on_click=MCPConsentState.approve,
                disabled=~MCPConsentState.ready,
            ),
            rx.button("Deny", on_click=MCPConsentState.deny, variant="soft"),
        ),
    )
```

## App-specific scopes

Approving a client should not hand an agent the user's entire authority.
Declare app-specific scopes to make the grant granular:

```python
rxe.MCPPlugin(
    app_scopes={
        "orders:read": "Read your order history",
        "orders:write": "Place and modify orders",
    },
)
```

Each app scope appears on the consent screen as an **individually grantable
checkbox** — a scope the client requested starts ticked, the others unticked.
The minted access and refresh tokens carry exactly the scopes the human
granted, uniformly across every configured IdP rather than depending on each
IdP's own scope behavior. App scopes are advertised in the OAuth metadata so
clients may request them; add them to `default_scopes` to have dynamic
registrations request them by default (pre-ticking the boxes).

Use `required_scopes` to gate the endpoint itself:

```python
rxe.MCPPlugin(app_scopes={...}, required_scopes=["orders:read"])
```

A bearer token must carry those scopes to reach the MCP endpoint at all.
Anonymous tokens carry no scopes, so setting `required_scopes` also disables
anonymous access.

## Surface-aware auth checks

Granted scopes are enforced in your own `auth=` checks. Every auth context —
event, var, and page — carries the surface the request arrived through and the
scopes of the token mediating it:

- `ctx.surface` — `"browser"` (the normal websocket path), `"event_api"` (the
  REST plugin), or `"mcp"`.
- `ctx.token_scopes` — `None` for a browser request (the user's full authority;
  no token restricts it), or a tuple for an API request: the consent-granted
  scopes of an OAuth token, or `()` for an anonymous session.

Use them **restrictively**: require a scope when the access is token-mediated,
and never treat a scope as granting more than the user could do from a browser.

```python
import reflex as rx
import reflex_enterprise as rxe


def can_write_orders(ctx) -> bool:
    # Browser users keep their normal authority; an agent needs the grant.
    return ctx.token_scopes is None or "orders:write" in ctx.token_scopes


def browser_only(ctx) -> bool:
    return ctx.surface == "browser"


class OrderState(rx.State):
    @rxe.event(auth=can_write_orders)
    def place_order(self, item_id: str): ...

    @rxe.event(auth=browser_only)
    def export_everything(self): ...
```

This is deliberately identity-*and*-surface-based: the same signed-in user
keeps full access in the browser while their delegated agent is limited to what
they ticked on the consent screen.

## Rate limiting

Every MCP call — tools and session-reading resources alike — is counted against
the presenting session token: `call_rate_limit` per `call_rate_window` (default
60 per minute), tracked per process. Exceeding it returns a clear retry-after
error. Browser (websocket) events are never rate limited by this mechanism.

Individual handlers can override their own budget where the default is wrong:

```python
class ReportState(rx.State):
    @rxe.event(rate_limit=2, rate_limit_window=60.0)
    def generate_expensive_report(self): ...

    @rxe.event(rate_limit=0)  # exempt from per-token limiting
    def cheap_ping(self): ...
```

An overridden handler is counted in its own per-token bucket; everything else
shares the token's default bucket. The two per-IP limiters — anonymous token
grants and dynamic client registration — are covered in
[deploying to production](/docs/enterprise/mcp/deployment/#rate-limits).

## Related

- [Auto MCP](/docs/enterprise/mcp/): the endpoint, tools, and resources.
- [Secure by default](/docs/enterprise/auth/secure-by-default/): how `auth=`
  checks work for pages, handlers, fields, and vars.
- [Deploying to production](/docs/enterprise/mcp/deployment/): TLS
  requirements, token storage, and reverse proxies.
