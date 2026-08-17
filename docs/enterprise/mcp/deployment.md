---
title: Deploying MCP to Production
---

_New in reflex-enterprise v0.9.4._

# Deploying MCP to Production

The MCP endpoint is an agent-facing, credential-bearing surface. Four things
need attention before it faces anything but localhost: TLS, the issuer origin,
token storage, and the rate limiters.

## TLS is required

The internal OAuth authorization server hands out **bearer credentials** —
authorization codes on redirect URLs, and access/refresh tokens on the token
endpoint. Over plain HTTP those are readable (and replayable) by any on-path
observer, so the OAuth issuer **must be served over `https`**.

This is enforced at wiring time: with MCP OAuth enabled, a resolved issuer
(`MCPPlugin(issuer_url=...)`, or the config's `deploy_url` / `api_url`) that is
plain `http` on a non-loopback host fails startup with a `ConfigError`.
`http://localhost`, `http://127.0.0.1`, and `http://[::1]` remain allowed so
local development works without certificates.

The anonymous token endpoint and the REST API carry bearer tokens on every
request too, so they need the same TLS protection even when OAuth is off.

## Behind a reverse proxy

In the common production shape — TLS terminated at a reverse proxy in front of
the app — two settings matter:

```python
rxe.MCPPlugin(
    issuer_url="https://my-app.example",
    registration_trusted_proxy_hops=1,
)
```

- **`issuer_url`** (or the config's `deploy_url` / `api_url`) must be the
  **public `https` origin** the proxy serves. The OAuth discovery documents
  bake it in, so a wrong value produces metadata clients cannot follow. If
  neither is set, wiring fails fast with a `ConfigError`.
- **`registration_trusted_proxy_hops`** is the number of trusted proxies in
  front of the app. The per-IP rate limiters (dynamic client registration and
  the anonymous token endpoint) then key on the real client address, read that
  many hops from the right of `X-Forwarded-For`, instead of on the proxy's
  address. The default `0` ignores `X-Forwarded-For` entirely — correct when
  the app is reachable directly, since the header is attacker-controlled on a
  request that did not traverse a stripping proxy.

`EventHandlerAPIPlugin` has the same setting under the name
`trusted_proxy_hops`.

## Route collisions

The OAuth endpoints are inserted at the **origin root**, ahead of the SPA
catch-all, so they win over an app page at the same path. That is why dynamic
client registration defaults to `/register-oidc-client` instead of the MCP
SDK's bare `/register` — the latter would shadow a sign-up page. If your app
serves `/authorize`, `/token`, or `/revoke`, move the OAuth endpoint rather
than the page:

```python
rxe.MCPPlugin(token_path="/oauth/token", revocation_path="/oauth/revoke")
```

Clients discover every endpoint from the authorization-server metadata, so the
values only need to avoid your routes. They must be distinct from each other
and must not live under the MCP mount (a route there would be shadowed by the
mounted sub-app and 404) — both are checked at wiring time, as is the same
constraint on `consent_path`.

## Storage

Tokens, pending authorizations, consent records, and upload tickets are stored
in **Redis** when the app is configured with a `redis_url`, and **in-process**
otherwise.

The in-memory store is fine for a single-process app or development, but it
does not survive a restart and is not shared across workers. Configure Redis
for multi-worker or production deployments so agents don't have to
re-authenticate after every restart or land on a worker that doesn't recognize
their token.

```md alert info
# Redis 6.2 or newer is required.
The store relies on `GETDEL` for single-use authorization codes. The version is probed once at startup, so an older server fails fast at boot rather than mid-exchange.
```

Override the store explicitly with `MCPPlugin(auth_store=...)` (or
`EventHandlerAPIPlugin(token_store=...)`) if you need something else.

## Rate limits

Three per-process limiters protect the endpoints an unauthenticated or
low-trust caller can reach. Multi-worker deployments limit per worker, so
budget accordingly.

| Limiter | Default | Keyed on | Protects |
| --- | --- | --- | --- |
| `registration_rate_limit` | 10 / 60s | client IP | RFC 7591 dynamic client registration — the one OAuth endpoint an anonymous caller can write through. |
| `token_rate_limit` | 10 / 60s | client IP | Anonymous session grants; each one seeds a server-side session that consumes memory. |
| `call_rate_limit` | 60 / 60s | session token | MCP and REST calls, with per-handler `rxe.event(rate_limit=...)` overrides. |

Setting any of them to `0` disables that limiter, which is not recommended in
production.

## One OAuth-enabled mount per app

The OAuth facade binds a single authorization server per process and serves its
RFC 8414 / RFC 9728 discovery documents at fixed origin-root paths, so a second
OAuth-enabled `MCPPlugin` would shadow the first. That configuration raises a
`ConfigError` at wiring time rather than failing silently. Additional MCP
surfaces can run with `auth=False` (anonymous sessions only).

## Security checklist

- **Scope the agent's authority.** Approving a client should not hand it
  everything the user can do — declare
  [app scopes](/docs/enterprise/mcp/authentication/#app-specific-scopes) and
  check `ctx.token_scopes` / `ctx.surface` in the `auth=` callbacks of anything
  consequential.
- **Every application event handler is exposed by default.** Framework and auth
  handlers are withheld, but yours are not. Gate privileged handlers with
  `auth=` checks, or publish no action surface at all with
  `MCPPlugin(expose_events=False)`.
- **State reads redact the session's own credentials.** The server-side
  `client_token` / `session_id` are stripped from the `router` var, so the
  session token never reaches the agent.
- **Anti-framing headers on the consent route.** The backend sends
  `X-Frame-Options: DENY` and `frame-ancestors 'none'`; in a split
  frontend/backend deployment, configure your frontend host or CDN to send them
  for the consent route as well.
- **Put the endpoint behind your normal perimeter** (VPN, WAF, IP allowlists)
  if the app is not meant to be agent-drivable from the public internet.

## Related

- [Auto MCP](/docs/enterprise/mcp/): configuration reference for every option
  named here.
- [Authentication](/docs/enterprise/mcp/authentication/): tokens, the OAuth
  flow, scopes, and per-token rate limiting.
- [Auth: deploying to production](/docs/enterprise/auth/deployment/): HTTPS and
  cookie requirements for the underlying OIDC login.
