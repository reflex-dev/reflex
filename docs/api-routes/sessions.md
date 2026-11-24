---
title: Browser Sessions
---

# Browser Sessions

Reflex can bind each tab's state to a signed browser session. The browser keeps
the session credential in an HTTP-only cookie; the `client_token` identifies a
tab and is not sufficient to access its state when enforcement is enabled.
This establishes ownership of state, not a user identity or login. Application
authentication and authorization still belong in your app or AuthPlugin.

## Modes

Session ownership is enforced by default. To change it, set
`REFLEX_SESSION_TOKEN_MODE` in the environment of every backend worker and
replica, for example `REFLEX_SESSION_TOKEN_MODE=warn reflex run`:

| Mode | Behavior |
| --- | --- |
| `enforce` (default) | Requires session ownership for event contexts and uploads. A socket presenting a client token that its session does not own receives a new token and fresh state. |
| `warn` | Issues sessions and warns about unauthorized state access, while allowing it for compatibility. A tab keeps a client token that its session does not own. |
| `off` | Disables ownership enforcement. Fresh tabs receive a client token; existing legacy tokens remain usable. |

## Upgrading

Under `enforce`, an app that upgrades can see these changes:

- A tab that was open during the upgrade holds a legacy token. Legacy tokens
  are not bound to a session on first use: doing so would let anyone who
  learned an old token claim its state. The tab therefore gets a new token and
  its state resets once.
- Server code that reaches the state of another client, such as a broadcast
  from an event handler or a webhook route that calls `app.modify_state`,
  raises `SessionAuthorizationError`. Pass `session_token=SessionToken.SYSTEM`
  (see [Server-side state access](#server-side-state-access)).
- A browser that does not store the session cookie gets fresh state on each
  new connection (see [Origins, cookies, and embedding](#origins-cookies-and-embedding)).
- A client that is not a browser must use the client token that the backend
  sends, not one that it made.
- A cached old frontend cannot persist a session cookie, so it loses state on
  reconnect until the page reloads.

Set `REFLEX_SESSION_TOKEN_MODE=warn` while you update server code, integration
clients, and reflex-enterprise. `warn` allows each of these cases and logs a
warning that names the call site.

## Startup and refresh

The WebSocket connects first. If it has no valid session cookie, the backend
issues a session and a bound tab token in-band. Hydration and `on_load` can run
while the frontend exchanges that credential at `POST /_reflex/session` in the
background. Uploads wait for this exchange to finish and remain cancellable
while waiting. Transient exchange failures retry with backoff while ordinary
WebSocket events continue; waiting HTTP requests resume when the cookie is ready.
Disconnecting cancels the pending exchange. The credential is never
stored in localStorage or sessionStorage.

The credential that the socket sends is a short-lived bearer credential. It is valid
for up to one minute and only at `POST /_reflex/session`; the backend does not accept
it as a cookie value, and it does not accept a cookie value for exchange.

A `403` from the exchange means the backend does not trust the origin of the
page (see [Origins, cookies, and embedding](#origins-cookies-and-embedding)).
The frontend logs the origin to the browser console once, does not retry, and
releases waiting uploads. The app keeps working over the WebSocket, but the
browser has no session cookie, so `enforce` resets the state of that tab on
each new connection.

The endpoint also supports a JSON POST with no credential to create a session
for a non-browser client. It returns `token_type`, `expires_in`, `refresh_in`, and
`client_token`, and sets the cookie. Pass an existing `Reflex-Client-Token`
header to retain an owned tab token. The endpoint honors `backend_path`.
Reflex-enterprise's bearer issuer at `/_reflex/auth/token` is unchanged.

Fresh browser tabs coordinate initial cookie creation with Web Locks. Browsers
without Web Locks cannot guarantee that simultaneous first connections share
one session; if a competing cookie wins, the affected tab reconnects with the
server's replacement token. Waiting HTTP requests remain queued until that
replacement connection is accepted. Storage keys are scoped to the backend URL.

`session_token_ttl` in `rx.Config` is the lifetime of one session credential and
defaults to seven days. `session_token_max_age` is the maximum age of the
session and also defaults to seven days. It counts from the first issue of the
session, and renewal cannot extend a session past it. At that age the session
ends: the next connection gets a new session, and under `enforce` the tab gets
a new token and fresh state. With both defaults, a session lasts seven days.
Set `session_token_ttl` below `session_token_max_age` to end an idle session
sooner while an active one renews up to the maximum age.
`session_token_refresh_interval` defaults to half that lifetime. Only
`POST /_reflex/session` renews the cookie, and its response is `no-store`, so a
shared cache never stores the credential. A browser timer renews an idle
session at that age, and a tab that becomes visible after that age renews at
once, so a suspended timer does not require a new session while the socket
survives. A socket that connected with a valid cookie renews it over HTTP: the
backend sends the credential over the socket only when the browser has no valid
cookie, so page scripts cannot read a credential that is in the cookie.
A socket retains its validated session for its
connected lifetime. Cookie expiry is checked on subsequent HTTP requests and
reconnections. Refresh retains the session ID and existing tab bindings.

## Origins, cookies, and embedding

Secure cookies use `Secure; HttpOnly; SameSite=None; Partitioned; Path=/`, no Domain,
and an app-specific `__Host-` name; non-loopback HTTP development uses an insecure
cookie without the `__Host-` prefix. Set `api_url` to the public backend URL,
including when TLS terminates at a reverse proxy. Cookies are not scoped by
port, so applications sharing a host must have distinct `app_name` values.
The signed audience also binds each credential to `app_name`, so one app cannot
accept another app's session even when they share a signing key.

Installing an in-band credential requires a trusted Origin. Reflex trusts
`deploy_url`, `api_url`, explicit `cors_allowed_origins`, the development
loopback frontend origins, and a page on the host that the request reached
(for example a development server opened through a LAN address).
`cors_allowed_origins=["*"]` does **not** authorize credential exchange. Configure `deploy_url` for the frontend and list any
EmbedPlugin host origins explicitly. This prevents another origin from
installing a session credential it already knows. A valid existing cookie
always takes precedence over an exchanged credential.

Partitioned cookies allow cross-site iframes and separate frontend/backend
sites in browsers that support them. The session belongs to the top-level
site's partition. Browsers that block third-party cookies without supporting
partitioned cookies cannot persist sessions in those contexts. Plain HTTP on
a non-loopback development host uses a warning and an insecure `SameSite=Lax`
cookie; use HTTPS for embedding and production.

A browser stores a `Secure` cookie only from HTTPS or a loopback host. A
production app served over plain HTTP on another host, or a development server
opened through a LAN address while `api_url` is a loopback URL, therefore has
no persistent session. The default `enforce` mode gives the tab a new token and
fresh state on each new connection, so use HTTPS, or set `api_url` to the
address that the browser uses. `warn` and `off` keep the tab token, so such an
app works as before.

All ports of the backend host share the cookie, because cookies are not scoped
by port. A page on another port of that host can therefore open a socket in
the same session and get its own client token, but only when the backend
accepts its WebSocket origin. Production accepts the `deploy_url` origin by
default; development and an explicit `cors_allowed_origins` can accept more.
Such a page cannot read the state of another tab without that tab's client
token. Do not treat the session alone as proof of who the user is.

Cookie headers remain readable on the server through `self.router.headers`.
They are omitted from frontend router data, and the session credential itself
is stripped before request headers reach app code. Use `rx.Cookie` for cookies
that intentionally need to be readable in browser JavaScript.

## Signing keys

Set `REFLEX_SECRET_KEY` to a random value of at least 32 bytes. Store it in
your deployment's secret manager or environment. Never put it in
`rxconfig.py`. If you load it from a local `.env` file, add that file to
`.gitignore`. To generate a key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Give every replica and every new deployment the same `REFLEX_SECRET_KEY`. A
server with a different key rejects the sessions that the other servers issued.

Without `REFLEX_SECRET_KEY`, `reflex run` generates a temporary key at startup
and shares it with its backend workers. The key is not saved, so all sessions
reset when `reflex run` restarts. Reflex logs a warning when it generates a key.

### Changing the key

```md alert warning
# Keep the old key when you add a new one.

If you replace the old key with the new key, every session resets at once.
```

1. Put the new key first and keep the old key after it, separated by a comma:
   `REFLEX_SECRET_KEY=<new key>,<old key>`. Restart or redeploy every backend,
   because a running backend reads the keys once. New cookies use the first key.
   Cookies signed with the old key stay valid.
2. Wait at least the maximum session age (`session_token_max_age`, seven days by
   default). Active sessions move to the new key when their cookie refreshes.
   Tab bindings are kept.
3. Remove the old key: `REFLEX_SECRET_KEY=<new key>`.

If the old key leaked, do not keep it. Set only the new key. Anyone who has the
old key can sign valid cookies, so it must stop working at once, even though
all sessions reset. There is no per-session revocation mechanism in this
release.

## Server-side state access

`EventContext.session_token` contains a validated `SessionToken` with a
non-secret `id`, `issued_at`, `expires_at`, and `authorizes(client_token)`.
It does not imply that the client is logged in.

`app.modify_state`, event enqueueing, and chained events inherit the ambient
session. HTTP and custom WebSocket routes receive the requesting session, and
framework WebSocket events receive the socket's session. Explicit `session_token=None` means anonymous
access. A handler cannot modify another session's state under `enforce`. The
same check applies when a handler links an `rx.SharedState` to a client token:
only the session that owns that token can make the link.

Lifespan work starts with `SessionToken.SYSTEM`. For intentional trusted
server-side fan-out, pass it explicitly:

```python
from reflex_base.session import SessionToken

async with app.modify_state(
    rx.BaseStateToken(ident=client_token, cls=MyState),
    session_token=SessionToken.SYSTEM,
) as root_state:
    state = await root_state.get_state(MyState)
    state.message = "Server maintenance starts soon"
```

Do not use `SYSTEM` to bypass checks on client-supplied tokens in HTTP routes.
The low-level state-manager APIs remain trusted internals; framework network
entry points perform their checks before loading state. Custom endpoints that
call state-manager APIs directly must provide their own authorization.
Apply rate limiting to `/_reflex/session` through your existing reverse proxy
or `api_transformer` middleware; do not trust arbitrary forwarded-IP headers.
