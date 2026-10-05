# Changelog

All notable changes to this project are documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Unreleased changes live as [towncrier](https://towncrier.readthedocs.io) news
fragments under `news/`; a release materializes them into a section below.

<!-- towncrier release notes start -->

## v0.9.7a2 (2026-10-05)

### Features

- Allow `reflex run --env prod` and `reflex export` on the Free tier when the app shows the "Built with Reflex" badge. Exports now always include the badge when it is enabled, including `reflex export --env dev`. ([#241](https://github.com/reflex-dev/reflex-enterprise/issues/241))


## v0.9.7a1 (2026-10-05)

### Breaking Changes

- Upgrade the AG Grid wrapper from 34.3.1 to 36.2.0 and integrated AG Charts from
  11.2.4 to 14.2.0. Applications with custom grid CSS or chart options should review
  the [migration notes](https://reflex.dev/docs/enterprise/ag-grid/upgrading-to-36-2/).
  Add `suppress_overlays` for the new provided overlays. Fix `row_id_key` callback
  generation, pinned-row prop names (retaining existing aliases), and datasource URL
  query parameters. Add Playwright coverage using the `reflex_app` fixture. ([#ag-grid-36](https://github.com/reflex-dev/reflex-enterprise/issues/ag-grid-36))

### Features

- Add `rxe.google_font` to load a Google Font from the document head, with
  `preconnect` hints and `display=swap`, so the font is fetched during the initial
  HTML parse instead of after the global stylesheet:

  ```python
  app = rxe.App(head_components=rxe.google_font("Inter", weights=[400, 700]))
  ``` ([#239](https://github.com/reflex-dev/reflex-enterprise/issues/239))

### Miscellaneous

- Improve authentication audit hook type annotations. ([#237](https://github.com/reflex-dev/reflex-enterprise/issues/237))


## v0.9.6 (2026-09-21)

### Bug Fixes

- A login popup opened by an iframed app now closes when the login finishes,
  instead of loading the whole app inside itself. `auth_callback` took its next
  step from `redirect_to_url`, which a popup inherits from its opener
  (`window.open` copies session storage), so that target could not say whether
  the window was a popup. The callback hands back to the opener instead, and
  `CLOSE_POPUP` / `POST_MESSAGE_AND_CLOSE_POPUP` take an optional `fallback_url`
  so a window with no reachable opener navigates there rather than being left
  parked with nothing to close it. Tokens the exchange rejected close the popup
  without being announced to the opener. ([#223](https://github.com/reflex-dev/reflex-enterprise/issues/223))
- An app using `MCPPlugin` or `EventHandlerAPIPlugin` without an `AuthPlugin` no
  longer fails on hydrate with "no dispatch function for substate(s)
  `...___is_iframed_state`, `...___generic_oidc_auth_state`". Importing
  `reflex_enterprise.auth.oidc.state` defines those two states, and two paths
  imported it in apps that never asked for auth — after `App._compile()` had
  already baked the frontend's state list, leaving the backend with states the
  frontend had never heard of.

  `is_exempt` imported the module just to test `issubclass(..., OIDCAuthState)`,
  which both plugins reach in `post_compile` while snapshotting the event-handler
  registry; it now looks the module up in `sys.modules` instead, since no
  `OIDCAuthState` subclass can exist while it is unloaded. Separately,
  `register_reflex_resources` was never told that no `AuthPlugin` is configured,
  so reading `reflex://state/vars/<state>/<var>` resolved user identity — and
  imported the module — on a *running* backend; it now receives the same
  `enforce_auth` flag as its sibling registrations. Apps that do configure an
  `AuthPlugin` are unaffected: it loads the provider module before compilation. ([#231](https://github.com/reflex-dev/reflex-enterprise/issues/231))
- Fix `TypeError: metaclass conflict` with `OIDCAuthState` on reflex 0.9.12+.
- The REST, MCP and agent surfaces blank the session's `client_token` and
  `session_id` again before handing state back to a caller. reflex 0.9.12 split
  the root `router` var into per-field `rx_router_*` vars, and the redaction —
  which looked the session up under `router` — silently stopped firing, so
  `POST /_reflex/retrieve_state` and the event-delta stream disclosed the
  server-generated session token. Both layouts are now redacted, and the
  redaction also matches the router data by type so a further framework rename
  cannot quietly turn it back into a no-op.


## v0.9.5 (2026-09-01)

### Bug Fixes

- A sign-in callback whose `state` disagrees with the nonce stored for the tab is now reported once rather than on every websocket reconnect. A tab left open on a stale callback URL previously logged an error and recorded a suspected-CSRF audit entry each time it reconnected, for as long as it stayed open. ([#216](https://github.com/reflex-dev/reflex-enterprise/issues/216))
- A session the provider has logged out elsewhere is now reset instead of looping.
  Its access and ID tokens are still signed and unexpired, so the local validity
  check passes while the provider refuses both the userinfo call and the refresh.
  Neither the refresh's own reset nor the caller's forced-expiry reset was
  reaching that case, so the session kept its dead cookies, repeated the whole
  failure on every userinfo interval, and left no `session_expired` in the audit
  trail. ([#217](https://github.com/reflex-dev/reflex-enterprise/issues/217))
- Access dynamic bundled libraries in reflex 0.9.9 style. ([#219](https://github.com/reflex-dev/reflex-enterprise/issues/219))


## v0.9.4 (2026-08-14)

### Breaking Changes

- **`EventHandlerAPIPlugin` now requires an app-issued bearer token on every
  request** — the bare caller-supplied `client_token` (a UUID naming a session)
  is no longer accepted. This closes the session-takeover vector where a caller
  could name (or guess) another session's token: sessions are now
  server-generated and bound to a bearer the app issues, obtained from the
  anonymous token endpoint or the OAuth flow. State reads redact the session's
  server-side `client_token`/`session_id` from the returned `router` var so the
  session token never reaches the client. ([#198](https://github.com/reflex-dev/reflex-enterprise/issues/198))
- `EventHandlerAPIPlugin` no longer exposes auth/framework event handlers (any
  `OIDCAuthState` provider, the page guard, route dispatchers, `AuthUserState`,
  and other `reflex`/`reflex_enterprise` states). Callers drive the app's own
  handlers and authenticate through the token endpoint or the OAuth flow rather
  than by queueing the login events directly. ([#198](https://github.com/reflex-dev/reflex-enterprise/issues/198))
- OIDC cookie names now carry a `_partitioned` suffix so they do not collide with
  the unpartitioned cookies written by earlier versions. Sessions established
  before this upgrade are not recognized under the new names, so users sign in
  once more after it is deployed. ([#206](https://github.com/reflex-dev/reflex-enterprise/issues/206))

### Features

- **New: `reflex_enterprise.MCPPlugin`** — serve a Reflex app to AI agents over
  the Model Context Protocol. Adding the plugin mounts an MCP server that
  publishes the app's public event handlers as `search_events` / `queue_event`
  tools, a `reflex://` resource family for reading the app (`reflex://state`,
  `reflex://event[/{event_name}]`, `reflex://state/events/{state_name}`, and
  `reflex://state/vars/{state_name}[/{var_name}]` for the caller's live session
  state, computed vars recomputed), and auto-generated `instructions` covering
  the app's location, auth model, tool workflow and pages, so a client knows how
  to drive it on connect. `configure=` (a callable or a `"module.function"` path)
  hands you the underlying `FastMCP` server before it is mounted to register your
  own tools, resources and prompts — also reachable at runtime via
  `reflex_enterprise.get_mcp_server()`; `expose_events=False` publishes reads
  only, without the app's action surface; `pending_updates=` chooses `"drop"`
  (default) or `"queue"` (buffered for a `get_pending_updates` tool) for deltas
  from chained events and background tasks, which have no websocket to land on.
  Upload handlers cannot run inline, so `queue_event` returns out-of-band upload
  directions (URL, headers, form fields and a `curl` example) carrying a
  short-lived, single-use ticket bound to the one handler it was minted for.
  Requires the optional `mcp` extra (`pip install reflex-enterprise[mcp]`). ([#198](https://github.com/reflex-dev/reflex-enterprise/issues/198))
- MCP OAuth: with an `AuthPlugin` configured, `MCPPlugin` makes the app a
  spec-compliant OAuth 2.1 Authorization Server + Resource Server for its MCP
  endpoint, federating the human login to the existing OIDC flow through a
  brandable consent page. Clients discover the flow (RFC 9728 / RFC 8414),
  register dynamically (RFC 7591), and receive the app's own opaque,
  resource-bound tokens — upstream identity-provider tokens never leave the
  server. Each token is bound to a dedicated session, so the full enforcement
  stack (per-event gate, callable `auth=` checks, delta filtering,
  `AuthUserState.current()`) applies to agent traffic unchanged.
  `app_scopes={name: description}` renders each scope as an individually
  grantable checkbox on the consent screen and the minted token carries only what
  was granted, readable in `auth=` callbacks via `ctx.token_scopes`. Tokens and
  consent live in Redis when the app is configured for it, otherwise in-process.
  On by default alongside an `AuthPlugin`; opt out with `MCPPlugin(auth=False)`.
  In production the issuer must be served over `https` — a plain-http issuer
  (outside loopback dev hosts) is rejected at wiring time with a `ConfigError`,
  since the authorization server hands out bearer credentials on that origin.
  See the production/TLS section in `docs/mcp.md`. ([#198](https://github.com/reflex-dev/reflex-enterprise/issues/198))
- The `rxe.mcp.resource` decorator tags a state method as a top-level MCP
  *resource* — a var-like, parameterized, read-only view of the caller's session
  state, served at `state-resource://<state>/<method>[/{param}]` with the
  method's parameters as URI-template variables. It is never an event handler, so
  it stays out of `search_events` / `queue_event`, and its `auth=`
  (`True`/`False`/a `check(ctx)` callable, the same contract as `rxe.var`) gates
  the read whenever an `AuthPlugin` provides identity. ([#198](https://github.com/reflex-dev/reflex-enterprise/issues/198))
- Anonymous API sessions: `MCPPlugin` and `EventHandlerAPIPlugin` serve
  `POST /_reflex/auth/token`, returning an app-issued bearer bound to a fresh,
  **server-generated** session — the client never picks or sees the underlying
  client token. The endpoint is rate limited per client IP (`token_rate_limit`)
  so one origin cannot mint unbounded sessions. With an `AuthPlugin` an agent may
  stay anonymous (no user identity, so only `auth=False` surfaces are reachable)
  or complete the OAuth flow for an authenticated session. On by default; turn it
  off with `anonymous_sessions=False` on every API plugin you register, since the
  shared endpoint is served if either enables it. ([#198](https://github.com/reflex-dev/reflex-enterprise/issues/198))
- Auth contexts (event/var/page) now carry `ctx.surface` (`"browser"` /
  `"event_api"` / `"mcp"`) and `ctx.token_scopes` (the app-issued token's
  scopes, or `None` for a browser request), so `auth=` checks can restrict what
  a delegated agent may do independent of the underlying user's identity. ([#198](https://github.com/reflex-dev/reflex-enterprise/issues/198))
- Per-token API rate limiting: every MCP/REST call is counted against the
  presenting session token (`call_rate_limit` / `call_rate_window`), with
  per-handler overrides via `rxe.event(rate_limit=..., rate_limit_window=...)`
  (`rate_limit=0` exempts a handler). ([#198](https://github.com/reflex-dev/reflex-enterprise/issues/198))
- Cross-origin iframe login: OIDC cookies are now set with `SameSite=None` and the
  `Partitioned` attribute (including on Python versions whose `http.cookies` cannot
  emit `Partitioned` itself), so an app can complete the login flow while embedded
  in an iframe whose outer page is on a different origin. Logging out from the inner
  frame now clears the session proactively instead of waiting for a `postMessage`
  from the popup -- that message was only ever caught by a listener bound to the
  login button, so it never arrived on a page that rendered no login button. ([#206](https://github.com/reflex-dev/reflex-enterprise/issues/206))
- An app that does not configure the `AuthPlugin` no longer loads the auth system
  from its OIDC providers. The provider helpers that reach for plugin-owned things
  -- `AuthUserState`, the deauthentication app-state sweep, the audit emissions --
  are wrapped in `@requires_plugin(AuthPlugin)` and do nothing when the plugin is
  absent, so the provider still clears its own cookies but never grafts
  `AuthUserState` onto a state tree the frontend compiled without it. Previously
  that state was loaded anyway and every update computed for it reached the client
  as a dispatch error on the frontend and backend consoles.

  The guard is reusable by any plugin integration that must stay inert in apps
  that did not enable the plugin: `reflex_enterprise.plugins.guards` exposes
  `requires_plugin(SomePlugin, default=...)` as a decorator for sync and async
  helpers, plus `has_plugin` / `configured_plugin` for the underlying question. ([#210](https://github.com/reflex-dev/reflex-enterprise/issues/210))

### Bug Fixes

- Popup auth flows honor `redirect_to_url` again: it is saved before the flow is
  initiated, so the query parameter set on the iframed page survives, and the saved
  URL is what the success handler redirects to. ([#206](https://github.com/reflex-dev/reflex-enterprise/issues/206))
- Fix a cross-site iframe losing a valid session to a cross-tab logout that never
  happened. An iframe's partitioned `localStorage` cannot see the token hash the
  login popup wrote at top level, so its empty report was read as proof that
  another tab had logged out -- and won that race whenever it arrived before the
  server-queued hash write. The reported hash is now a change ping rather than a
  verdict: any disagreement queues one cookie sync and the callback adopts whatever
  the cookie jar holds. Token material means record the session's hash, re-assert
  it into this partition's `localStorage` and refresh if due; an empty jar is a
  real logout and resets as before. ([#207](https://github.com/reflex-dev/reflex-enterprise/issues/207))
- `MessageListener` no longer accumulates `message` listeners. Its effect cleanup
  removed a different function than the one it registered, so a listener leaked on
  every re-render and each popup message was then handled once per leaked listener. ([#208](https://github.com/reflex-dev/reflex-enterprise/issues/208))


## v0.9.3 (2026-08-05)

### Features

- Auth: `AuthPlugin(audit=...)` — an observe-only audit hook called for every auth lifecycle action (login, logout, token refresh, session expiry) and every access decision (event gate, page guard). See the [audit docs](https://reflex.dev/docs/enterprise/auth/audit). (#200)
- Auth: replay gate-blocked events after login — an action blocked by the event gate for an anonymous visitor (the click or form submit that triggered the login redirect) is preserved and replayed once the user authenticates and lands back on the same page, instead of being silently lost (#190)

### Bug Fixes

- OIDC: split authorization-callback failure outcomes — handle identity-provider `error` responses, restart the flow once when the sign-in session was lost, and reserve the "possible CSRF attack" warning for a genuine state mismatch; the callback is now also idempotent across websocket reconnects instead of re-firing against an already-exchanged code (#203)
- OIDC: stop reporting expired ID tokens as backend errors — routine expiry during re-validation now logs at INFO without a traceback and no longer sets `has_error`; signature and other validation failures still log at ERROR (#202)

### Miscellaneous

- OIDC: add token-presence context (`access_token`/`id_token`/`refresh_token` booleans, never values) to forced-logout warnings so the cause is visible in production logs (#195)
- OIDC: attribute forced logouts from the token-refresh paths in logs and downgrade the userinfo reset warning to debug for anonymous visitors, cutting log noise (#203)
- Fix unawaited-coroutine `RuntimeWarning`s in the auth test suite (#192)

## v0.9.2.post1 (2026-07-06)

### Bug Fixes

- Do not update `AuthUserState` when `AuthPlugin` is not registered (#196)
- Serialize `HTTPCookie.sync` requests to avoid data race (#196)

## v0.9.2 (2026-07-06)

### Features

- Add Highcharts chart component (#182)
- Add `reflex_app` pytest plugin for downstream testability (#179)

### Bug Fixes

- Auth: redeliver protected vars on public pages (#186)

### Performance

- Auth: skip protected-var redelivery on same-user navigation (#187)

### Miscellaneous

- Add logging to silent auth failure/logout paths (#188)

## v0.9.1 (2026-07-01)

### Features

- Add `reflex_enterprise.AuthPlugin` providing integrated secure-by-default auth primitives for protecting pages, fields, vars, and event handlers. See the [full docs](https://reflex.dev/docs/enterprise/auth/overview) for usage.

## v0.9.0 (2026-06-09)

### Breaking Changes

- Restrict `reflex export` and `reflex run --env prod` to paid tiers (#177)

## v0.8.3 (2026-06-01)

### Bug Fixes

- Handle map layer `event_handlers` prop properly (#175)
- OIDC: use `self.__class__` instead of `type(self)` for handler lookups (#176)
- Redo `redirect_to_login` when userinfo is unavailable (#174)

## v0.8.2 (2026-05-19)

### Features

- `InteractiveLeafletLayer` and enhanced event handling for map components (#170)
- `postMessage`-based token sync for iframed OIDC popup flows (#172)

### Bug Fixes

- OIDC: try refresh token before resetting auth on validation failure (#173)

### Miscellaneous

- Harden GitHub Actions workflows (#171)

## v0.8.1 (2026-05-11)

### Bug Fixes

- Always set `cls._has_registered_endpoints = True` (#169)

## v0.8.0 (2026-05-08)

### Bug Fixes

- `HTTPCookie`: remove `BaseState` patches and fix subclass var dependencies (#164)

### Miscellaneous

- Remove runtime version checks throughout the package (#168)

## v0.7.3 (2026-05-01)

### Features

- Add valid issuers and related cleanup (#163)

### Bug Fixes

- Avoid race condition between updating the `localStorage` value and redirect (#167)
- Fix backend path handling for HTTP cookies (#166)

## v0.7.2 (2026-04-27)

### Bug Fixes

- `messageListener.js`: reference `public_path` in the wrapped component (#162)

## v0.7.1.post2 (2026-04-27)

### Miscellaneous

- Remove the GitHub Packages upload step and attach the wheel to the GitHub Release instead

## v0.7.1 (2026-04-24)

### Features

- Add event handlers as HTTP endpoints and expose them via the OpenAPI spec (#156)

### Miscellaneous

- Add license URL (#161)

## v0.7.0.post1 (2026-04-21)

### Bug Fixes

- Fix importable path for Mantine (#160)

## v0.7.0 (2026-04-20)

### Bug Fixes

- Reflex 0.9 compatibility: use `importable_path` for assets in 0.9.0+ (#159)
- Additional Reflex 0.9 compatibility fixes (#157, #158)

## v0.6.5 (2026-03-27)

### Miscellaneous

- Replace AWS CodeArtifact with GitHub Packages for the enterprise wheel (#154)
- Remove `rx.Base` for 0.9 compatibility (#155)

## v0.6.4 (2026-03-18)

### Features

- Expose display name (#152)

### Miscellaneous

- Improve token type validation (#153)

## v0.6.3 (2026-03-16)

### Miscellaneous

- Raise with an error message (#151)

## v0.6.2 (2026-03-10)

### Bug Fixes

- Redirect after logout consistently (#150)

## v0.6.1 (2026-03-09)

### Features

- Add APIs for Reflex Enterprise to override UI (#149)

## v0.6.0 (2026-03-03)

### Performance

- OIDC: reduce and centralize out-of-band events (#148)

## v0.5.5 (2026-02-21)

### Bug Fixes

- Ignore refresh access token errors (#142)

### Miscellaneous

- OIDC: handle local storage updates internally (#147)

## v0.5.4 (2026-02-19)

### Bug Fixes

- OIDC: reset auth for invalid tokens in `userinfo` (#146)

## v0.5.3 (2026-02-19)

### Features

- OIDC: allow a pluggable `_http_client` implementation (#145)

## v0.5.2.post1 (2026-02-18)

### Bug Fixes

- Also save `redirect_to_url` in `sessionStorage` (#144)

## v0.5.2 (2026-02-18)

### Miscellaneous

- Store PKCE identifiers in `sessionStorage` (#143)

## v0.5.1 (2026-02-17)

### Bug Fixes

- Redirect to login with an invalid token (#141)

## v0.5.0 (2026-02-13)

### Features

- Implement refresh token in `OIDCAuthState` (#139)

### Miscellaneous

- Overhaul OIDC implementation for flexibility (#135)
- Upgrade dependency pins (#140)

## v0.4.3 (2026-01-22)

### Bug Fixes

- Fix issuer claim request to support multiple values (#137)

### Miscellaneous

- Exclude OIDC routes from `/sitemap.xml` (#134)

## v0.4.2 (2026-01-07)

### Features

- Add `HTTPCookie` partitioned attribute (#129)
- Allow cross-origin cookie sync when `same_site="none"` (#128)

### Miscellaneous

- Use Starlette `cookie_parser` instead of `SimpleCookie` (#133)
- Do not validate cookie domain (#130)
- Pre-commit fixes (#131)

## v0.4.1 (2025-12-19)

### Features

- Allow passing arbitrary headers to `HTTPCookie.sync` (#127)

## v0.4.0 (2025-12-17)

### Features

- Implement HTTP Cookie support (#119)
- Add `presets` and other props for Mantine date components (#120)
- Return the row count in `Datasource` and `SSRMDatasource` (#123)
- Row grouping options include the `RowGroupingModule` (#122)
- Apply default sort order by `primary_key` (#121)

### Bug Fixes

- `args_names` must be a tuple (#124)

### Miscellaneous

- Bump ag-grid to 34.3.1 (#125)
- Add upload step to build job (#126)
