# Brief: a5_hydration_router — #7360 router-data change on 0.10.0a5, plus hydration regressions re-run

Read first: `/home/user/reflex/prerelease_testing/2026-10-08-a5/AGENT_BRIEF.md` (hard rules), then
`/home/user/reflex/prerelease_testing/2026-10-08-a5/CAMPAIGN_STATE.md`. Artifacts →
`/home/user/reflex/prerelease_testing/2026-10-08-a5/a5_hydration_router/`; scratch `$SB/apps/a5_hydration_router/`.
Ports: frontend 3140-3159 / backend 8140-8159 and 3660-3679 / 8660-8679. Redis: a port from your backend range.

Read reflex-dev/reflex#7360 (GitHub MCP `pull_request_read`: description, commits, review threads) and its diff
(`git -C /home/user/reflex show beef0aead`) before testing, so you test what it was FOR and what it could break.

## Part 1 — #7360 regression hunt (a5 vs a4 back to back; 0.9.12 for anything that differs)
Build one app that exercises the router everywhere users touch it:
- `on_load` handlers (single, list, chained via `yield Other.handler` / returned events, an `on_load` that starts a
  background task, an `on_load` that `rx.redirect`s, `on_load` on a dynamic route `/post/[slug]` and a catch-all
  `[[...splat]]`) that record what they see in `self.router`: `page.path`, `page.raw_path`, `page.full_path`,
  `page.params`, `url`, `url.query_parameters`, `headers.host` / `origin` / `user_agent` / `cookie` (server-side),
  `headers.raw_headers`, `session.client_token`, `session.session_id`, `session.client_ip` — and regular event handlers
  reading the same after load. Check on first load, reload, client-side navigation (`rx.link`), back/forward, query-string
  changes, a redirect chain, two tabs, and in dev, prod and prod + Redis with several workers (the EventContext must carry
  the right view across workers). Any value that differs from a4 is a finding until explained.
- Frontend rendering: `State.router.page.path` / `.params` / `.url`, `State.router.headers.user_agent`, the deprecated
  `State.router.headers.cookie` and `State.router.headers["cookie"]` (must render "" and warn once — where does the
  deprecation warning appear, compile log only?), `State.router.headers.raw_headers` (rendered via `rx.foreach` / `.to_string()`),
  `State.router.session.client_ip`, computed vars over `self.router`.
- **Security claim**: send cookies (incl. an HttpOnly cookie set by a server route) and an `Authorization` / `X-Forwarded-Access-Token` /
  `Cf-Access-Jwt-Assertion` header (via a tiny forwarding proxy, or Playwright `extra_http_headers` on the websocket upgrade)
  and capture EVERY websocket frame and the prerendered HTML in dev and prod: a4 must leak (positive control), a5 must not
  — including in on_load event payloads, `update_vars_internal`, background-task deltas, and after a reconnect. The backend
  must still see them (`self.router.headers.cookie` / `raw_headers["authorization"]` in a handler), also after a Redis
  round trip on another worker.
- reflex-local-auth 0.5.0 and reflex-google-auth 0.2.0 flows (they use on_load guards / redirects): login, logout,
  protected-page redirect and back, two tabs — dev and prod.

## Part 2 — re-run the identified-and-fixed hydration regressions on a5 (positive control first)
- **F-002** (fresh profile writes no storage keys): control on `$SB/envs/alpha` (0.10.0a1) must write; a5 dev, prod,
  prod + Redis must write nothing (`2026-10-07-a3/a3_hydration/scripts/run_f002.sh` or the a4 h4mix C1 check).
- **F-003** (computed var rewriting storage at hydration reaches the browser; google-auth bogus token cleared):
  control a1; a5 (`run_gauth.sh`, cvstore cases).
- **A3-11 / A3-12** (sync=True storms): one explorer storm series and one `/stamp` series, a3 control then a5, dev and
  prod (`2026-10-08-a4/a4_hydration/` scripts; 0 storms, convergence expected).
Each with a pass/fail table.

Report in the structured format of AGENT_BRIEF.md with `REVERIFIED:` lines for F-002, F-003, A3-11, A3-12 and a
security verdict for #7360. Classify every issue as regression vs a4 / vs 0.9.12 / intended (documented) / pre-existing.
