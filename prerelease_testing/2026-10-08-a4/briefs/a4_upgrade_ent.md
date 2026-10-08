# Brief: a4_upgrade_ent — upgrade, third-party and enterprise spot check on 0.10.0a4

Read first: `/home/user/reflex/prerelease_testing/2026-10-08-a4/AGENT_BRIEF.md` (hard rules), then
`/home/user/reflex/prerelease_testing/2026-10-08-a4/CAMPAIGN_STATE.md` (what a4 changed). Your artifacts go to
`/home/user/reflex/prerelease_testing/2026-10-08-a4/a4_upgrade_ent/`; scratch under `$SB/apps/a4_upgrade_ent/`.
Ports: frontend 3600-3639 / backend 8600-8639 and 3460-3479 / 8460-8479. Redis: a port from your backend range.

This is a SPOT CHECK, not a full campaign: a4 changed only #7505 (state.js storage echo), #7516 (state metaclass refuses
assignment over a state var) and #7513 (docs). Re-run the a3 pass's flows that exercise those two code paths in real apps,
compare with a3 (same machine, back to back), and report only real differences. The a3 pass's assets are under
`/home/user/reflex/prerelease_testing/2026-10-07-a3/` (`a3_upgrade/`, `a3_ent_auth/`, `a3_ent_grid/`, `a3_events_tp/`;
each has a NOTES.md with rerun commands) — COPY them out, never run in place.

1. **In-place upgrades.** Pick three reflex-examples apps from `a3_upgrade` (e.g. form-designer, github-stats or
   twitter with prod/Redis, and one using a third-party package such as reflex-local-auth). For each: build the app on
   0.9.12 in its own venv, drive its real flows, then upgrade the SAME venv + app dir in place to `reflex[db]==0.10.0a4`
   (`--prerelease=allow`, keep `.web/` and `reflex.lock/`), re-drive, then one cold run (`rm -rf .web`). Also one a3 → a4
   in-place upgrade (only reflex + reflex-base must move; diff `.web/package.json`). Watch the first a4 run's log: an app
   that assigns a state var through its class at import time now fails with TypeError (#7516, documented breaking change)
   — if any example app does, record it (which app, which line, is the error clear) and classify it as "documented
   breaking change hits real code", not a bug. 0.9.12- and a3-pickled Redis sessions must load on a4.
2. **Third-party sweep (imports + key flows).** Re-run the a3 sweep's resolver + import step on a4
   (`a3_events_tp/NOTES.md` lists the 22 packages and how they were installed): every package that imported on a3 must
   import on a4; any new import failure (especially a TypeError from the state metaclass) is a finding. Run the
   reflex-local-auth and reflex-magic-link-auth flows the a3 sweep ran (register/login/logout, 2 tabs) on a4 dev + prod.
3. **Enterprise a5 on a4** (`$SB/envs/a4-ent`, `CI=true`): first grep the wheel (`$SB/downloads/enterprise_wheel_a5/x/`)
   for class-level writes to state vars (`<State>.<var> =`, `setattr(` on state classes, `__fields__`) and note any that
   #7516 could hit. Then: N-032 re-check (`a3_ent_auth` verifier drivers `vdrv.py away|stale|xtab`, dev Redis, 3 runs
   each) — must stay fixed; the auth matrix / login-logout / cross-tab logout flows (enterprise auth keeps tokens in
   browser storage, so #7505 is in play); N-025 AG Grid quick re-check (`a3_ent_grid` `entv` fixture, prod: state grid
   headers + cells, memo grid, detail grid); dnd / flow / mantine / maps route smoke. Compare anything odd against
   `$SB/envs/a3-ent` and `$SB/envs/s912-ent-a5`.

Known and filed, do NOT report again: A3-07, A3-08, A3-09 (enterprise redirect after reconcile), A3-10 (enterprise#274),
N-033 (enterprise#262), F-009 reflex-chat leak, reflex-clerk `set_clerk_session` TypeError, reflex-chakra / community
reflex-ag-grid import failures, AG Grid demo model 24/29, flow 20/22, maps `on_layeradd`.

Report in the structured format of AGENT_BRIEF.md, with `REVERIFIED:` lines for N-032 and N-025 (still fixed?) and one
line per upgraded app.
