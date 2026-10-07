CLUSTER: ent_auth
SUMMARY: Enterprise OIDC, MCP and maps on reflex 0.10.0a2 + the offline reflex-enterprise 0.9.7a4 wheel, Redis (and memory) state manager, dev and prod (1 and 9 workers), baselined on 0.9.12 + wheel and 0.10.0a1 + wheel. New HIGH regression since a1: logging out in one tab leaves other tabs signed in (#7064's single hydrate_and_load bypasses the enterprise OIDCAuthState.get_delta hash reconciliation; deterministic stale-hash probe 0/3 on a2 vs 2/2 on 0.9.12). HIGH pre-existing: prod + Redis + default 9 workers answer 405 on /_reflex/cookies/sync on most workers so token cookies are lost in 3/4 logins. Everything else passes (10-05 a4 matrix 36/36, MCP, maps, #252, #7312, #7460 × auth) or is identical on 0.9.12.
ARTIFACTS: prerelease_testing/2026-10-07/ent_auth/ (NOTES.md; apps/entauth, apps/mapsapp, apps/a4auth; scripts/ incl. xtab_probe.py, stale_hash_probe.py, prod_sync_probe.py, bglive_probe.py, expiry_matrix.sh; logs/ (>40 KB gzipped); screenshots/). Work dir $SB/apps/ent_auth2/.
TESTS:
- [pass] OIDC on Redis dev + prod (1 worker): login, sync/async protected events, reload from Redis, end_session logout; Bob after Alice sees no Alice data in page, storage or Redis keys.
- [pass] #7312 background append to an inherited protected list persists through Redis (0.9.12 loses it).
- [pass] #252 protected sync/async computed vars survive public navigation + 2 reloads, dev and prod.
- [pass] extra_scopes (offline_access, address): sent at authorize, refresh works, reload keeps the session.
- [pass] #7460 × enterprise auth: no empty/default latest_access_token_hash_ls write, no token-cookie deletion on protected loads/reloads/new tabs (F-002 fixed from this angle).
- [anomaly] garbage token cookies ignored at boot (read only on cookie sync); identical on 0.9.12.
- [fail] cross-tab logout: tab 1 logged out a2 redis dev 3/7, a2 memory dev 3/5, a2 redis prod 3/5, a1 2/6, 0.9.12 6/6 (N-032).
- [fail] stale_hash_probe: stale localStorage hash at boot corrected 0/3+0/3 on a2, 0/2+0/2 on a1, 2/2+2/2 on 0.9.12; via storage event corrected everywhere (N-032 root cause).
- [pass] 10-05 a4 auth matrix on a2 36/36 (+ a4 MCP OAuth and anonymous checks), no page/HTTP errors.
- [pass] MCP on Redis dev, prod 1 worker, prod 9 workers: OAuth metadata/registration/consent/deny/PKCE/refresh rotation+replay/revoke; anonymous 401, upload tickets, rate limits, 429; background tool, multi-yield; 2×20 parallel bumps = 40. Matches a1.
- [anomaly] MCP handler denied by scope check returns is_error=false, delta={} (N-037; a1 same).
- [pass] proactive refresh with 75 s tokens: logged in after 120 s.
- [anomaly] expiry/revocation: expired token without refresh still authorizes; revocation noticed at next refresh only; IdP key rotation breaks logins until restart — all identical on 0.9.12 (N-035, N-036).
- [fail] prod + Redis + 9 granian workers: /_reflex/cookies/sync 405 on most workers; 3/4 logins without token cookies; 0.9.12 identical (N-033).
- [anomaly] background-task deltas on protected states withheld (placeholder values); workaround: load AuthUserState in every async with self (N-034).
- [pass] maps dev, prod (9 workers), 0.9.12: 16/17 each — 200 markers/s from a background task, drag → State, reload, base-layer/overlay switching, geolocation.
- [anomaly] maps: on_layeradd never fires; LayersControl.BaseLayer/Overlay not exposed and generate invalid JS; rxe.map(id) sets no DOM id — all versions (N-038).
- [anomaly] reflex run --backend-only refuses to start with frontend_port in rxconfig; granian "Unexpected exit from worker-1" on every shutdown — both versions.
REVERIFIED:
- F-002 fixed (enterprise-auth angle).
- 10-06 ent_auth_mcp_redis partial lead: MCP unchanged from a1; the unsummarised cross-tab runs are the N-032 regression.
ISSUES:
- N-032 (HIGH, regression since a1) cross-tab logout leaves tabs signed in — verifier running.
- N-033 (HIGH, pre-existing) multi-worker prod cookie sync 405 — verifier running.
- N-034, N-035, N-036 (MEDIUM, pre-existing); N-037, N-038 (LOW, pre-existing).
NOT_COVERED: two-provider variant (AUTH_MULTI=1); a4 matrix in prod; Redis restart mid-session; iframe flows outside the a4 dev drivers. Servers, redis, mock IdP and browsers stopped; 3340-3359/8340-8359 free.
