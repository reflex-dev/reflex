# verify_net: verification of server_net issues (reflex 0.11.0a1)

Venvs: `$SB/envs/vnet-new` (reflex==0.11.0a1 + fastapi/uvicorn, PyPI) and `$SB/envs/vnet-prev` (reflex==0.10.1). Both
use starlette 1.10.0 and python-engineio 4.15.1. Scripts are in `verify_net/bin/`, evidence in `verify_net/evidence/`;
details and commands are in `server_net/NOTES.md` under `## VERIFICATION`. All processes were stopped and ports
3840-3855 / 8840-8855 are free.

| # | Issue | Verdict | Severity | Regression | Root cause @ v0.11.0a1 | Fix shape |
|---|---|---|---|---|---|---|
| 1 | Documented split deployment: websocket 403 | **CONFIRMED + WIDER** | **high** (was medium) | yes | `reflex/app.py:512-515` returns `None` in prod without `deploy_url`, passed to `AsyncServer` at `app.py:761-766`; engine.io's same-origin check is `{ASGI scheme}://{Host}` plus X-Forwarded-Proto/Host (`engineio/base_server.py:284-300`, `async_server.py:227-236`) | Docs before final: put `REFLEX_DEPLOY_URL`/`REFLEX_CORS_ALLOWED_ORIGINS` on the backend in self-hosting.md (split L63-71, API URL L89-109, static export L135-152), scaling.md L62-72 and app-platform-backend README L58-67; reverse-proxy section: forward `X-Forwarded-Proto`/Host; docker-example/production Caddyfile: `trusted_proxies`. Code: Reflex-side origin callable that also accepts `https://{Host}` behind a TLS proxy. Do not revert the security default |
| 2 | CORS rejection shown as "server unreachable" | **NARROWED** | low | no for the message (banner.py identical at v0.10.1); new exposure via #7641 | `reflex_components_core/core/banner.py:80-91,107-110` generic text; one engine.io WARNING line then INFO; no Reflex hint anywhere | A Reflex origin callable that logs one WARNING naming the origin, what the backend saw, and `deploy_url`/`cors_allowed_origins`/`X-Forwarded-Proto`; optional frontend `fetch(ping,{mode:"no-cors"})` after N failures to switch the toast to "reachable but refused" |
| 3 | `/Foo` + `/foo` accepted silently | **NARROWED** | low | no | `reflex/app.py:1295` exact-string route check; `_check_routes_conflict` (`app.py:1594`) only checks slugs; `reflex/route.py:185` `re.IGNORECASE`, first match wins (route.py:198-208) | `RouteValueError` on a casefold collision in `_register_prepared_page` (casefolded dict, O(1)) |
| 4 | `rx.App()()` returns `_RootMiddleware`, filed under Performance | **CONFIRMED** | low | yes (API shape), by design | `reflex/app.py:1010-1023`, class at `app.py:364`; CHANGELOG L69 (Performance) | Changelog/upgrade note in Breaking pointing to `api_transformer` / `app._api`. Downstream reliance is unlikely: the rxe 0.9.11 wheel only uses `app._api` (still Starlette) and the lifespan `starlette_app`; the docs at v0.10.1 and v0.11.0a1 and reflex-examples never use `app()` |
| 5 | FastAPI lifespan skipped behind a middleware that breaks on lifespan scopes | **CONFIRMED (anomaly)** | low | no (same result as 0.10.1, where the lifespan never ran); a new feature degrades | `reflex/app_mixins/lifespan.py:120-132` turns any startup exception into an INFO "appears unsupported" (uvicorn auto-mode parity); `app.py:987-1007` sends the lifespan only to the outermost callable-wrapped app | WARNING with the exception, naming the inner Starlette transformer(s) whose lifespan will not run, or fall back to sending lifespan directly to those transformers; upgrade-guide line. The docs' updated `scope.get("path")` example **works** (hello/connected, start + stop) |

Key evidence:
- V1 doc-literal: `split_new` (0.11.0a1) gives count=0 and 13 websocket 403s; `split_prev` (0.10.1) gives count=2.
  With backend `REFLEX_DEPLOY_URL` or `REFLEX_CORS_ALLOWED_ORIGINS`, count=2.
- V1 new: same-origin single-port prod behind a TLS terminator that sends no X-Forwarded-*: 0.11.0a1 gives count=0
  with 403s (`evidence/tls_new.png`), 0.10.1 gives count=2. Raw handshake: `Origin https://H` + `Host H` gives 403;
  adding `X-Forwarded-Proto: https` gives 101; `X-Forwarded-Proto: http` gives 403.
- docker-example/production behind a Render/Heroku TLS edge is very likely broken: Caddy replaces an untrusted
  X-Forwarded-Proto with `http`, and that combination gives 403 above. Caddy itself was not run (binary download
  refused in this sandbox). production-compose is OK, since Caddy terminates TLS itself.
