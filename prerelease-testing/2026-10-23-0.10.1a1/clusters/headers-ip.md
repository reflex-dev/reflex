# Cluster `headers-ip` — client IP trust, request headers, websocket header handling

## Changelog lines (verbatim)
- (reflex #7614, BREAKING) `router.session.client_ip` now ignores untrusted `X-Forwarded-For` headers by default. Configure `trusted_proxy_hops` to use forwarded client addresses from a trusted proxy chain.
- (reflex-base #7614) Add the `trusted_proxy_hops` configuration option for safely resolving client IPs from trusted proxy headers.
- (reflex #7588) Repeated request headers are no longer collapsed to their last value: repeated `cookie` fields are joined with `"; "` and any other repeated field with `", "`, so `router.headers.cookie` keeps every cookie.
- (reflex #7602) Websocket connections now accept request header values containing bytes that are not valid UTF-8.
- (reflex #7443) Raise an actionable error when a legacy string passed to `App.modify_state()` has a missing or unknown state path.

## What to build
An app that displays `self.router.session.client_ip`, `self.router.headers.cookie`, `self.router.headers.raw_headers` (or whatever the released API exposes — read the source on the pre-release branch), `x_forwarded_for`, and a custom header. Drive it (a) with the browser normally, (b) with a raw socket.io/websocket client from the driver venv (`python-socketio` or `websockets` with a hand-rolled Engine.IO handshake — simplest: `pip install python-socketio[asyncio_client]` into your own venv) sending: multiple `Cookie` headers, repeated custom headers, `X-Forwarded-For: 1.2.3.4, 10.0.0.1`, `X-Real-IP`, `Forwarded`, header values with invalid UTF-8 bytes (`b'\xff\xfe'`) — websockets library may refuse to send those; use a raw TCP HTTP/1.1 upgrade request if so.
Matrix: `trusted_proxy_hops` unset / 0 / 1 / 2, and with a real reverse proxy in front (e.g. a tiny `aiohttp`/`starlette` proxy or `caddy`/`nginx` if installed) that appends the client address. Compare every cell against 0.10.0. Document precisely when client_ip is the peer address vs a forwarded address, and whether a spoofed XFF is ever trusted with hops=0/unset.
Also: HTTP routes (`app.api` / `rx.App(api_transformer=...)` with a FastAPI/Starlette route) — are the header fixes websocket-only? Check and document.
`App.modify_state("Bad.Path")` / `modify_state("token_only")` error messages.

## Combine it with
- Granian vs uvicorn backend if selectable; the header behavior must be the same.
- Prod mode.
