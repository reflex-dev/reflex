# Cluster `ent_auth_mcp_redis` — enterprise auth/MCP/maps under Redis + multi-worker + uncovered MCP paths

Ports: frontend 3340-3359, backend 8340-8359. Work dir: $SB/apps/ent_auth_mcp_redis/. DEST: /home/user/reflex/prerelease_testing/2026-10-06/ent_auth_mcp_redis/

## Why this cluster exists
The previous campaign validated OIDC login/logout/protected events/iframe/cookies and MCP OAuth/anonymous
flows on 0.9.7a4 + 0.10.0a1, all with the in-memory state manager and a single worker. Its stated gaps:
Redis / multiple workers, multi-provider auth, provider-side expired/revoked sessions, callable field
authorization, MCP scope-denial/consent-denial/rate-limit/upload/background-event combinations, map
marker dragging and layer controls. 0.10.0a1 changed state serialization (descriptors, #7312), Redis
write batching (#7370), hydration (#7064) and the oplock race (#7372) — all of which matter with Redis.
Read: `/home/user/reflex-enterprise/demos/oidc`, `/home/user/reflex-enterprise/reflex_enterprise/auth/`,
`/home/user/reflex-enterprise/reflex_enterprise/mcp/` (read-only), the previous campaign's
`/home/user/reflex/prerelease_testing/2026-10-05/enterprise/` apps/drivers (`apps/auth_min`,
`mock_oidc.py`, `drive_auth_min.py`, `check_mcp*.py`) — COPY and reuse them (they used
`oidc-provider-mock==0.4.2` as a local IdP; `AUTHLIB_INSECURE_TRANSPORT=1`, `OIDC_ISSUER_URI`,
`OIDC_CLIENT_ID/SECRET` env vars, `CI=true`).

## Setup
Own venv: `cd $SB && uv --no-config venv --python 3.12 $SB/envs/ent_auth && uv --no-config pip install --python $SB/envs/ent_auth/bin/python --prerelease=allow 'reflex==0.10.0a1' 'reflex[db]==0.10.0a1' 'reflex-enterprise[mcp]==0.9.7a4' 'pydantic<2.14' oidc-provider-mock mcp`.
Start your own `redis-server --port 8349` and run the app with `REFLEX_REDIS_URL=redis://localhost:8349`.

## What to do
1. OIDC auth app (reuse `auth_min`/the oidc demo) on Redis, dev then PROD. In prod run with TWO
   backend workers if the CLI/granian allows it (`reflex run --env prod --backend-only` is single; check
   `REFLEX_GRANIAN_WORKERS`/`--workers`-style options in the published package: `grep -rn workers $SB/envs/ent_auth/lib/python3.12/site-packages/reflex/reflex.py`
   and `reflex_base/config.py`) — otherwise run two separate `--backend-only` processes behind nothing
   and alternate them by restarting: the point is that auth state round-trips through Redis pickles
   written by the new descriptor-based states. Flows: login as Alice, protected event, reload, logout,
   login as Bob on the same browser, check NO Alice data remains; background task on a protected state
   that mutates an inherited list (the #7312 fix) and persists through Redis; auth with `extra_scopes`;
   a protected computed var (sync and async) after public navigation + reload (the #252 fix) under Redis.
2. Token/session expiry: shorten the mock provider's token lifetime or the enterprise session TTL if
   configurable; let it expire; next protected action must redirect to login, not traceback; refresh token
   flow if enabled. Revoke at the provider (restart the mock provider = all sessions invalid) and observe.
3. MCP plugin (anonymous + OAuth) on Redis: tools that trigger a BACKGROUND event, a handler that
   yields several times, an upload-backed resource if the plugin exposes any, two MCP sessions in
   parallel hammering the same state (lock contention via Redis), scope denial (request a scope the
   client was not granted), consent denial at the mock provider, rate limiting (hit the resource read
   limit quickly) — record the exact responses. Note: `POST /_reflex/mcp` (no trailing slash) returns
   405 in prod — KNOWN and deferred, use `/_reflex/mcp/`; do not re-report it, but DO note if dev now
   differs from what the previous report says.
4. Maps (`rxe.map`): marker dragging (`draggable=True`, `on_drag_end` → State), layers control
   switching base layers, polygon editing if supported, geolocation denied (`context.grant_permissions([])`),
   many markers from `rx.foreach` over a State list that updates every second (background task),
   in prod. Baseline on 0.9.12 + enterprise 0.9.6 only where something fails.
For each failure record which combination fails (core alpha vs enterprise alpha vs Redis vs memory).
