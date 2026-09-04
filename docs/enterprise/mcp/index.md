---
title: Auto MCP
---

_New in reflex-enterprise v0.9.4._

# Auto MCP

`rxe.MCPPlugin` publishes your Reflex app over the
[Model Context Protocol](https://modelcontextprotocol.io) — no server code, no
tool definitions, no glue. Every event handler the app registers becomes
something an agent can search and apply, and the session's live state becomes
something it can read back.

Where [Event Handler API](/docs/enterprise/event-handler-api/) exposes the same
surface as REST + OpenAPI for scripts and HTTP clients, `MCPPlugin` exposes it
as a streamable-HTTP MCP server for LLM agents and MCP-aware editors. Both
plugins share one implementation, so an agent and a `curl` script drive exactly
the same handlers with the same auth and the same rate limits.

```md alert info
# Requires `reflex-enterprise` with the `mcp` extra, and `rxe.App()` (not `rx.App()`).
Enabling the plugin without the extra installed prints an actionable error and leaves the app otherwise untouched.
```

## Installation

The MCP SDK is an optional dependency, so it is only pulled in when you ask for
it:

```bash
pip install "reflex-enterprise[mcp]"
```

## Quickstart

**1. Add the plugin to `rxconfig.py`:**

```python
import reflex_enterprise as rxe

config = rxe.Config(
    app_name="my_app",
    plugins=[rxe.MCPPlugin()],
)
```

**2. Use `rxe.App()`** in your app module:

```python
import reflex_enterprise as rxe

app = rxe.App()
```

**3. Point an MCP client at the endpoint.** With a dev server running, the
server is mounted at `/_reflex/mcp`:

```bash
claude mcp add --transport http my-app http://localhost:8000/_reflex/mcp
```

or, in a client that takes a JSON config:

```json
{
  "mcpServers": {
    "my-app": {
      "type": "http",
      "url": "http://localhost:8000/_reflex/mcp"
    }
  }
}
```

Every request needs an app-issued bearer token. A client that speaks OAuth 2.1
obtains one by itself when an [`AuthPlugin`](/docs/enterprise/auth/overview/) is
configured; otherwise, grab an anonymous session token and send it as a header
(see [Authentication](/docs/enterprise/mcp/authentication/)):

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/_reflex/auth/token \
        | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -X POST http://localhost:8000/_reflex/mcp \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

The transport is stateless streamable HTTP with JSON responses, so a single
JSON-RPC POST is a complete call — there is no separate `initialize`
round-trip to manage.

## Endpoints

| Path | Purpose |
| --- | --- |
| `POST /_reflex/mcp` | The MCP server (streamable HTTP). Tools, resources, and prompts are served from this one path. |
| `POST /_reflex/auth/token` | Anonymous session token grant, rate limited per client IP. Shared with `EventHandlerAPIPlugin`. |
| `POST /_reflex/mcp/upload` | Ticket-authenticated file-upload endpoint used by the upload directions `queue_event` returns. |
| `/agent-consent` | The consent page shown during the OAuth flow (only with an `AuthPlugin`; route configurable). |
| `/.well-known/oauth-protected-resource/_reflex/mcp`, `/.well-known/oauth-authorization-server`, `/authorize`, `/token`, `/register-oidc-client`, `/revoke` | The OAuth 2.1 authorization server, when it is enabled. The four endpoint paths are configurable. See [Authentication](/docs/enterprise/mcp/authentication/). |

Change the mount with `MCPPlugin(path="/mcp")`; the upload endpoint and the
protected-resource metadata follow it.

## Tools

| Tool | What it does |
| --- | --- |
| `search_events(query, limit)` | Free-text search over the app's event handlers. Returns each match's `name`, summary/description, and the JSON schema of its payload parameters. An empty `query` lists everything. This is the server-side-filtered entry point — the one to use on a large app. |
| `queue_event(event_name, payload, query)` | Apply an event to the caller's session and return the resulting state delta. |
| `get_pending_updates()` | Only registered with `pending_updates="queue"` — returns and clears followup deltas buffered for the session. |

`search_events` returns a `results` list along with `total_available`,
`total_matched`, and `returned`, so an agent can tell when its query was
capped (`max_search_results`, default 20; callers may request fewer, never
more).

`queue_event` takes the `name` from a search result (the canonical dotted form
`foo.bar`; the slash form `foo/bar` and the fully-qualified registry name also
resolve), invokes the handler with `payload` as keyword arguments, and returns:

```json
{
  "event": "tickets___tickets____ticket_state.create_ticket",
  "delta": {
    "reflex___state____state.tickets___tickets____ticket_state": {
      "tickets": ["..."],
      "total_count": 3
    }
  }
}
```

Var names come back clean: the framework's internal `_rx_state_` field-marker
suffix is stripped from every agent-facing delta and state read, so an agent
sees `total_count`, not `total_count_rx_state_`.

The optional `query` object becomes the request's query parameters, which is
how an agent supplies [dynamic route variables](#dynamic-route-variables) —
handlers read them through `self.router` exactly as they would for a page URL's
query string.

## Resources

State and event metadata are exposed as `reflex://` resources rather than
tools, so a client can browse them without spending a tool call:

| Resource | Contents |
| --- | --- |
| `reflex://state` | The exposed state names (fully-qualified; the root is `reflex___state____state`). |
| `reflex://event` | Every exposed handler: `name`, `state`, `summary`. The flat-enumeration alternative to `search_events`. |
| `reflex://event/<event_name>` | One handler's full description, including its payload schema. |
| `reflex://state/events/<state_name>` | The handlers defined on one state. |
| `reflex://state/vars/<state_name>` | The session's live state rooted at a state — the resolved `.dict()` of frontend + computed var values. Read `reflex___state____state` for the whole app. |
| `reflex://state/vars/<state_name>/<var_name>` | A single var's live value. A computed var is marked dirty and **recomputed** rather than served from the cache. |

The `reflex://state/vars/...` resources read the session bound to the caller's
bearer token; the metadata resources are session-independent.

You can also publish your own read-only, parameterized views of session state —
see [custom MCP resources](/docs/enterprise/mcp/custom-resources/).

## Server instructions

On connect, the server advertises auto-generated `instructions` — the MCP
analog of the OpenAPI spec's `info` preamble. They describe the app and where
it is served, the authentication model, the available tools and resources, the
exposed state names, the app's pages (with the handlers their `on_load`
triggers), and the dynamic route variables. Most agents need nothing beyond
this to start driving the app.

The page listing covers your app's pages only. The auth machinery's own routes
— `/login`, `/callback`, `/logout`, `/forbidden`, each OIDC provider's popup
pages, and the MCP consent page — are omitted, along with their dynamic route
variables: they are human-interactive sign-in plumbing an agent cannot drive,
so advertising them would only invite it to "visit" a page it can't use.

Override the generated text with `MCPPlugin(instructions="...")`, and add
`contact` / `license_info` / `api_version` to have them rendered into it:

```python
rxe.MCPPlugin(
    api_version="2.1.0",
    contact={"name": "Ops", "email": "ops@example.com"},
    license_info={
        "name": "Apache-2.0",
        "url": "https://opensource.org/licenses/Apache-2.0",
    },
)
```

## Dynamic route variables

If any page uses dynamic route segments (e.g. `/tickets/[ticket_id]`), those
names are listed in the server instructions and can be passed in the
`queue_event` `query` object:

```json
{
  "event_name": "tickets___tickets____ticket_state.load_ticket_detail",
  "payload": {},
  "query": {"ticket_id": "8f2c…"}
}
```

The handler reads them through `self.router`, just as it does for a browser
navigation.

## File uploads

A file-upload handler (one taking `list[rx.UploadFile]` or an
`rx.UploadChunkIterator`) cannot be invoked inline — its files arrive as a
multipart body. `queue_event` detects those handlers and, instead of running
them, returns directions for making the upload out of band:

```json
{
  "status": "upload_required",
  "upload_type": "buffered",
  "event": "my_app___my_app____upload_state.handle_upload",
  "upload": {
    "url": "https://my-app.example/_reflex/mcp/upload?ticket=…",
    "method": "POST",
    "content_type": "multipart/form-data",
    "headers": {"Reflex-Event-Handler": "…"},
    "form_fields": [
      {"name": "__reflex_event_args", "value": "{\"description\": \"Q3 report\"}"},
      {"name": "files", "type": "file"}
    ]
  },
  "example_curl": "curl -X POST …"
}
```

The URL is pre-signed with a **single-use** ticket bound to the caller's session
**and to that exact handler**, so the agent POSTs the files with no credential
of its own — the endpoint resolves the ticket and injects the session token
server-side. Non-file handler arguments ride in a `__reflex_event_args` JSON
form field that must precede the file parts. Tickets expire after
`upload_ticket_ttl` (default 5 minutes).

The upload endpoint re-checks the allowlist rather than trusting the request: a
POST with no valid ticket is a `401`, and one whose `Reflex-Event-Handler`
doesn't match the handler the ticket was minted for — or names a handler that
isn't public and upload-shaped — is a `403`. A raw bearer token is not accepted
there at all, since only the ticket path carries the scope gate and rate limit
applied when the ticket was minted.

## Sessions and followup deltas

Each bearer token is bound to its own server-side Reflex session. That session
is real state — chain a few `queue_event` calls and each one sees the effects
of the last — but it has no browser websocket.

The delta an event produces is returned inline by `queue_event`, and the full
picture is available from `reflex://state/vars/...`. Reflex still routes
*followup* deltas to a session by token, though: chained events,
background-task results, cookie syncs, per-event auth bookkeeping. For an MCP
session there is no socket to push those to, so by default they are dropped
(`pending_updates="drop"`) rather than logged as emissions to a disconnected
client. The session is also pre-seeded as hydrated, so the page
hydrate/`on_load` chain does not re-run on every tool call.

Set `pending_updates="queue"` to buffer them instead. A `get_pending_updates`
tool is then exposed, returning and clearing whatever accumulated since the
last call — the way for an agent to collect a background task's result:

```python
rxe.MCPPlugin(pending_updates="queue")
```

## Limiting what is exposed

Only your application's own event handlers are published. Framework and auth
handlers — every OIDC provider (including your own `OIDCAuthState`
subclasses), the login/logout/callback dispatchers, the page guard, and other
`reflex` / `reflex_enterprise` internals — are withheld, so an agent cannot
drive the login flow by queueing its events.

There is deliberately no per-handler "hide from MCP" flag. To restrict what an
agent may do, use the `auth=` checks described in
[Authentication](/docs/enterprise/mcp/authentication/#surface-aware-auth-checks),
which can require an OAuth scope or reject a surface outright.

To publish no action surface at all — only state reading, your own
`rxe.mcp.resource` methods, and anything you add through `configure=` — pass
`expose_events=False`:

```python
rxe.MCPPlugin(expose_events=False)
```

## Configuration reference

All arguments are keyword-only and optional.

### Server

| Option | Default | Purpose |
| --- | --- | --- |
| `path` | `/_reflex/mcp` | Where the MCP endpoint is mounted. |
| `server_name` | `"<app_name> MCP"` | Name advertised by the server. |
| `instructions` | auto-generated | Override the generated server instructions. |
| `api_version` | `"1.0.0"` | Version reported in the instructions. |
| `contact` / `license_info` | `None` | Contact / license objects rendered into the instructions. |
| `max_search_results` | `20` | Cap on `search_events` results. |
| `expose_events` | `True` | Whether the event surface is published at all. |
| `configure` | `None` | Hook receiving the `FastMCP` server before it is mounted — see [Extending the server](/docs/enterprise/mcp/extending/). |
| `pending_updates` | `"drop"` | `"drop"` or `"queue"` — how followup deltas for the browserless session are handled. |

### Authentication

| Option | Default | Purpose |
| --- | --- | --- |
| `auth` | `None` | `None` = OAuth on exactly when an `AuthPlugin` is configured; `True` forces it (and fails fast without one); `False` keeps the endpoint anonymous-only. |
| `anonymous_sessions` | `True` | Serve the anonymous token endpoint and accept its tokens at the MCP endpoint — alongside OAuth, not instead of it. Always effectively on when OAuth is off. |
| `anonymous_session_ttl` | `3600` | Anonymous token lifetime in seconds (no refresh — a new token is a new session). |
| `app_scopes` | `None` | `{name: description}` scopes offered as individually grantable checkboxes on the consent screen. |
| `required_scopes` | `None` | Scopes a token must carry to reach the endpoint at all. |
| `valid_scopes` / `default_scopes` | `None` | Scopes dynamic registrations may request / are granted when they request none. |
| `issuer_url` | config `deploy_url` / `api_url` | Public origin serving the OAuth endpoints. Must be `https` in production. |
| `consent_path` | `/agent-consent` | Frontend route of the consent page. |
| `consent_page` | default page | Custom consent page builder, or a `"module.function"` import path. |
| `access_token_ttl` / `refresh_token_ttl` | `3600` / 30 days | Issued-token lifetimes (refresh rotates on use). |
| `client_registration_ttl` | 90 days | Lifetime of a dynamic client registration; `None` keeps them forever. |
| `pending_authorization_ttl` / `authorization_code_ttl` | `600` / `60` | How long a started authorization may wait for login + consent, and the code lifetime (codes are single-use regardless). |
| `upload_ticket_ttl` | `300` | Lifetime of a pre-signed upload ticket. |
| `enable_dynamic_client_registration` | `True` | Serve RFC 7591 dynamic client registration. |
| `enable_token_revocation` | `True` | Serve RFC 7009 token revocation. |
| `registration_path` | `/register-oidc-client` | Origin-root path of the registration endpoint — deliberately not the SDK's bare `/register`, which would shadow an app's own sign-up page. |
| `authorization_path` / `token_path` / `revocation_path` | `/authorize` / `/token` / `/revoke` | Origin-root paths of the other OAuth endpoints. Override any that collide with your own routes; each must be distinct and outside the MCP mount. |
| `auth_store` | auto | Token/consent storage. Defaults to Redis when the app's state manager is Redis, otherwise in-process. |

### Rate limiting

| Option | Default | Purpose |
| --- | --- | --- |
| `call_rate_limit` / `call_rate_window` | `60` / `60.0` | Per-session-token cap on MCP calls. Per-handler override via `rxe.event(rate_limit=...)`. |
| `token_rate_limit` / `token_rate_window` | `10` / `60.0` | Per-client-IP cap on anonymous token grants. |
| `registration_rate_limit` / `registration_rate_window` | `10` / `60.0` | Per-client-IP cap on dynamic client registration. |
| `registration_trusted_proxy_hops` | `0` | Number of trusted reverse proxies, for resolving the real client IP of the per-IP limiters. |

Setting a limit to `0` disables it, which is not recommended in production —
see [deploying to production](/docs/enterprise/mcp/deployment/).

## Related

- [Authentication](/docs/enterprise/mcp/authentication/): anonymous tokens, the
  OAuth 2.1 flow, consent, app scopes, and surface-aware auth checks.
- [Custom MCP resources](/docs/enterprise/mcp/custom-resources/):
  `rxe.mcp.resource` for read-only, parameterized views of session state.
- [Extending the server](/docs/enterprise/mcp/extending/): add your own tools,
  resources, and prompts.
- [Deploying to production](/docs/enterprise/mcp/deployment/): TLS, storage,
  reverse proxies, and rate-limit tuning.
- [Event Handler API](/docs/enterprise/event-handler-api/): the same surface
  over REST + OpenAPI.
