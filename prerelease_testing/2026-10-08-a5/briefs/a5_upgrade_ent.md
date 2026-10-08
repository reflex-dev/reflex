# Brief: a5_upgrade_ent — enterprise, install/upgrade and third-party re-verification on 0.10.0a5

Read first: `/home/user/reflex/prerelease_testing/2026-10-08-a5/AGENT_BRIEF.md` (hard rules), then
`/home/user/reflex/prerelease_testing/2026-10-08-a5/CAMPAIGN_STATE.md`. Artifacts →
`/home/user/reflex/prerelease_testing/2026-10-08-a5/a5_upgrade_ent/`; scratch `$SB/apps/a5_upgrade_ent/`.
Ports: frontend 3600-3639 / backend 8600-8639 and 3460-3479 / 8460-8479. Redis: a port from your backend range.
The a4 pass's assets for this item are in `/home/user/reflex/prerelease_testing/2026-10-08-a4/a4_upgrade_ent/` (NOTES.md
has rerun commands for every run: `up/`, `tp/`, `ent/auth/`, `ent/grid/`) — COPY them out and re-run on a5, with a4 back
to back as the baseline.

## Part 1 — enterprise a5 on reflex a5 (`$SB/envs/a5-ent`, `CI=true`): #7360 is the risk
reflex-dev/reflex#7360 stops copying `router_data` onto on_load events and drops cookies / credential headers from the
frontend router data. reflex-enterprise auth depends on the router: page guards redirect to
`login_url_for(str(state.router.url))`, `auth/cookie.py:225` parses `instance.router.headers.cookie` server-side,
`enforcement._event_client_token` falls back to `event.router_data`, `oidc/state.py` reads `self.router.url` /
`url.query_parameters` (`redirect_to`, `state`) and `session.session_id`, `plugins/api_tokens.py` persists router data
(see `$SB/downloads/enterprise_wheel_a5/x/`). Re-run on a5 vs a4: the entauth suites (drive_auth_redis cycle, pubnav,
twotab, xtab), `vdrv.py stale|away|xtab` (N-032, 3 runs each, dev + Redis and prod 1 worker), the 10-05 auth matrix
(36 checks + MCP OAuth + anonymous MCP), the expiry / proactive-refresh flows, login on a deep link with a query string
(must return to the same URL after login), logout from a protected page, protected client-side navigation, and the
api-token / event-handler-API plugin path if the demos cover it. N-025: `entv` prod (state grid, memo grids, detail
grid) + aggrid_min. dnd / mantine / flow / map route smoke. Anything that differs from a4 → re-run on a4 and 0.9.12
(`s912-ent-a5`) to classify.

## Part 2 — install paths and upgrades (identified-and-fixed regressions)
- N-001: fresh `reflex[db]==0.10.0a5` venvs on Python 3.11 and 3.14 with uv AND pip, nothing added by hand: greenlet
  resolves through the extra; `import reflex.model`, `reflex db init / makemigrations / migrate`, prod CRUD work.
- F-005: sqlmodel resolves ≥ 0.0.45; migrations apply on a fresh database.
- F-006: a fresh `pip install reflex==0.10.0a5` WITHOUT `--pre` resolves the full train (exact pin pulls the alphas).
- F-014: `reflex component init` exits 1 with the wrapping-docs pointer.
- In-place upgrades: twitter prod + Redis a4 → a5 and 0.9.12 → a5 (pickled sessions load; only reflex + reflex-base move
  from a4), form-designer (reflex[db] + local-auth) 0.9.12 → a5 — same per-check results as a4.

## Part 3 — third-party
- Grep the 36 downstream wheels the a4 pass collected (`2026-10-08-a4/a4_class_state/logs/downstream/` lists them) and
  `$SB/downloads/` packages for frontend uses of `router.headers.cookie`, `headers["cookie"]`, `raw_headers` and
  `router_data` that #7360 changes; exercise any hit.
- 22-package import sweep on a5 = a4; reflex-local-auth (36/38 known), magic-link (10/11 known), google-auth (12/13
  known) flows on a5 dev + prod.

Known and filed, do NOT report again: A3-07, A3-08, A3-09, A3-10, A3-13, A4-03, N-026, N-028, N-033, F-009, reflex-clerk,
reflex-chakra / community reflex-ag-grid import failures, AG Grid demo model 24/29, flow 20/22, maps `on_layeradd`.

Report in the structured format of AGENT_BRIEF.md with `REVERIFIED:` lines for N-032, N-025, N-001, F-005, F-006, F-014
and one line per upgraded app. Classify every issue as regression vs a4 / vs 0.9.12 / intended (documented) / pre-existing.
