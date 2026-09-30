---
title: Browser Sessions
---

# Browser Sessions

Reflex can bind each tab's state to a signed browser session. The browser keeps
the session credential in an HTTP-only cookie; the `client_token` identifies a
tab and is not sufficient to access its state when enforcement is enabled.
This establishes ownership of state, not a user identity or login. Application
authentication and authorization still belong in your app or AuthPlugin.

## Rollout

Set `REFLEX_SESSION_TOKEN_MODE` in the backend environment:

| Mode | Behavior |
| --- | --- |
| `warn` (default) | Issues sessions and warns about unauthorized state access, while allowing it for compatibility. |
| `enforce` | Requires session ownership for event contexts and uploads. A socket presenting an unbound client token receives a new token and fresh state. |
| `off` | Disables ownership enforcement and retains legacy WebSocket token handling. |

Use `enforce` after updating your frontend, integration clients, and
reflex-enterprise. Legacy tokens are not bound to a session on first use: doing
so would let anyone who learned an old token claim its state. Existing state
therefore resets when an old tab first migrates to a bound token. Cached old
frontends remain usable in `warn`; they cannot persist a new session cookie and
will lose state on reconnect under `enforce`.

## Startup and refresh

The WebSocket connects first. If it has no valid session cookie, the backend
issues a session and a bound tab token in-band. Hydration and `on_load` can run
while the frontend exchanges that credential at `POST /_reflex/session` in the
background. Uploads wait for this exchange to finish. The credential is never
stored in localStorage or sessionStorage.

The endpoint also supports a JSON POST with no credential to create a session
for a non-browser client. It returns `token_type`, `expires_in`, and
`client_token`, and sets the cookie. Pass an existing `Reflex-Client-Token`
header to retain an owned tab token. The endpoint honors `backend_path`.
Reflex-enterprise's bearer issuer at `/_reflex/auth/token` is unchanged.

Fresh browser tabs coordinate initial cookie creation with Web Locks. Browsers
without Web Locks cannot guarantee that simultaneous first connections share
one session; if a competing cookie wins, the affected tab reconnects with the
server's replacement token. Storage keys are scoped to the backend URL.

`session_token_ttl` in `rx.Config` defaults to seven days.
`session_token_refresh_interval` defaults to half that lifetime. HTTP responses
refresh an existing session after that age; active WebSockets ask the browser
to refresh in the background. A socket retains its validated session for its
connected lifetime. Cookie expiry is checked on subsequent HTTP requests and
reconnections. Refresh retains the session ID and existing tab bindings.

## Origins, cookies, and embedding

Cookies use `Secure; HttpOnly; SameSite=None; Partitioned; Path=/`, no Domain,
and an app-specific `__Host-` name. Set `api_url` to the public backend URL,
including when TLS terminates at a reverse proxy. Cookies are not scoped by
port, so applications sharing a host must have distinct `app_name` values.

Installing an in-band credential requires a trusted Origin. Reflex trusts
`deploy_url`, `api_url`, explicit `cors_allowed_origins`, and the development
loopback frontend origins. `cors_allowed_origins=["*"]` does **not** authorize
credential exchange. Configure `deploy_url` for the frontend and list any
EmbedPlugin host origins explicitly. This prevents another origin from
installing a session credential it already knows. A valid existing cookie
always takes precedence over an exchanged credential.

Partitioned cookies allow cross-site iframes and separate frontend/backend
sites in browsers that support them. The session belongs to the top-level
site's partition. Browsers that block third-party cookies without supporting
partitioned cookies cannot persist sessions in those contexts. Plain HTTP on
a non-loopback development host uses a warning and an insecure `SameSite=Lax`
cookie; use HTTPS for embedding and production.

Cookie headers remain readable on the server through `self.router.headers`.
They are omitted from frontend router data, and the session credential itself
is stripped before request headers reach app code. Use `rx.Cookie` for cookies
that intentionally need to be readable in browser JavaScript.

## Signing keys

Set `REFLEX_SESSION_SECRET` to a strong random secret of at least 32 bytes in
your deployment's secret manager or environment. Never put it in `rxconfig.py`.
If you load it from a local `.env`, add that file to `.gitignore`.

Without the variable, Reflex creates a 256-bit secret in
`.web/backend/session_secret`, readable only by its owner. Workers on one host
share it, and it survives hot reload, `reflex init`, and upgrades. Exported
bundles exclude it. Production logs a warning when the generated key is used.
All replicas and replacement deployments must receive the same environment
secret to preserve sessions.

For rotation, supply a comma-separated list with the new key first and the
previous key second. New cookies use the first key; all listed keys verify.
Keep the previous key for at least the maximum lifetime of cookies it signed.
Refreshing a cookie preserves tab bindings, even after its old signing key is
retired. There is no per-session revocation mechanism in this release.

## Server-side state access

`EventContext.session_token` contains a validated `SessionToken` with a
non-secret `id`, `issued_at`, `expires_at`, and `authorizes(client_token)`.
It does not imply that the client is logged in.

`app.modify_state`, event enqueueing, and chained events inherit the ambient
session. HTTP routes receive the requesting session, and framework WebSocket events
receive the socket's session. Explicit `session_token=None` means anonymous
access. A handler cannot modify another session's state under `enforce`.

Lifespan work starts with `SessionToken.SYSTEM`. For intentional trusted
server-side fan-out, pass it explicitly:

```python
from reflex_base.session import SessionToken

async with app.modify_state(
    rx.BaseStateToken(client_token, MyState),
    session_token=SessionToken.SYSTEM,
) as state:
    state.message = "Server maintenance starts soon"
```

Do not use `SYSTEM` to bypass checks on client-supplied tokens in HTTP routes.
The low-level state-manager APIs remain trusted internals; framework network
entry points perform their checks before loading state. Custom endpoints that
call state-manager APIs directly must provide their own authorization.
Apply rate limiting to `/_reflex/session` through your existing reverse proxy
or `api_transformer` middleware; do not trust arbitrary forwarded-IP headers.
