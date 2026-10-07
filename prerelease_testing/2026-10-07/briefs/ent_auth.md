# Cluster `ent_auth` — finish enterprise OIDC/MCP/maps on 0.10.0a2 + offline wheel, under Redis and in prod

Ports: frontend 3340-3359, backend 8340-8359 (redis 8349, mock OIDC provider 8358). Work dir: $SB/apps/ent_auth/. DEST: /home/user/reflex/prerelease_testing/2026-10-07/ent_auth/
Venv: $SB/envs/alpha2-ent. Baselines on failure: reflex 0.9.12 + the offline wheel (own venv), $SB/envs/alpha + wheel.
CI=true REFLEX_TELEMETRY_ENABLED=false; AUTHLIB_INSECURE_TRANSPORT=1 and the OIDC_* env vars as in the previous apps.

Read first: $SB/CAMPAIGN_STATE.md, /home/user/reflex/prerelease_testing/2026-10-06/FINDINGS.md "Partial clusters → ent_auth_mcp_redis", /home/user/reflex/prerelease_testing/2026-10-06/briefs/ent_auth_mcp_redis.md,
/home/user/reflex/prerelease_testing/2026-10-06/ent_auth_mcp_redis/partial/ (apps, drivers, logs — reuse), and /home/user/reflex/prerelease_testing/2026-10-05/enterprise/
(apps/auth_min, mock_oidc.py, drive_auth_min.py, check_mcp*.py; the a4 auth matrix drivers under enterprise/a4/auth).

## Do
1. OIDC on Redis, dev then PROD (single port): login Alice → protected event → reload → logout → login Bob on the same
   browser → no Alice data; background task on a protected state mutating an inherited list persists through Redis;
   extra_scopes variant; protected sync + async computed vars after public navigation + reload (the #252 fix) under Redis.
   Because #7460 changed how client-storage/computed-var writes are delivered during hydration and enterprise auth keeps
   tokens in cookies/storage: check that a protected page load never writes an EMPTY/default token to the browser, and
   that a computed var that invalidates a bad token during hydration takes effect (inject a garbage token cookie, reload).
2. Re-run the previous campaign's full auth browser matrix (the 22-case driver from .../2026-10-05/enterprise and the
   a4 enhanced flows) on alpha2 + offline wheel; report the pass count vs the 36/36 recorded for a1.
3. Expiry/revocation: shorten token lifetime at the mock provider or enterprise session TTL; expired → redirect to login
   (no traceback); restart the mock provider (all sessions invalid) and observe.
4. MCP on Redis: finish the partial — OAuth + anonymous flows passed in dev; run them in PROD (use `/_reflex/mcp/`, the
   no-slash 405 is known/deferred), plus two parallel MCP sessions hammering the same state (Redis lock contention), a tool
   that triggers a background event, rate limiting, scope denial.
5. Maps: marker dragging (on_drag_end → State), layers control, geolocation denied, 200 markers from a State list updated by
   a background task every second, in prod.
Copy artifacts to DEST as you go.
