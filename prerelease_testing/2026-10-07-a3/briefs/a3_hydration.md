# Item `a3_hydration` — core boot/hydration regressions from reflex#7493 (client storage through get_delta at boot) on 0.10.0a3

Ports: frontend 3140-3159, backend 8140-8159 (redis 8149). Work dir: $SB/apps/a3_hydration/.
DEST: /home/user/reflex/prerelease_testing/2026-10-07-a3/a3_hydration/
Venvs: $SB/envs/a3 (under test), $SB/envs/alpha2 (previous alpha), $SB/envs/stable (0.9.12). Make your own venvs for third-party packages.

Read first: ../CAMPAIGN_STATE.md, ../AGENT_BRIEF.md, ../../2026-10-07/reverify_hydration/NOTES.md (drivers/, src/, probes/, srv.sh — COPY them),
../../2026-10-07/FINDINGS.md cluster summary `reverify_hydration` and F-002/F-003 rows of the re-verification table. Read reflex#7493's diff
(`git -C /home/user/reflex diff v0.10.0a2 555b667c1 -- reflex/state.py`) to understand exactly what is re-marked dirty and when.

## Do
1. Re-run the whole reverify_hydration suite on a3 dev + prod (f1combo/f1plain F-002 write-back checks with f1_check.py, mini_writeback,
   cvstore F-003 computed-var rewrites, csbox ComponentState storage, hyd_driver.py groups, token_leak_check.py, prenav/preconnect,
   reconnect_driver.py) and put the results next to the a2 column. Every a2 pass must still pass; F-002 and F-003 must stay fixed.
2. #7493-specific: (a) a fresh browser must NOT get any client-storage default written (localStorage, sessionStorage, cookies) on
   first load, dev and prod, Redis and memory, for plain states, substates, ComponentState, `rx.Cookie` with path/max_age/same_site,
   `sync=True` LocalStorage; (b) a `get_delta` override (`rx.state._override_base_method` pattern from
   ../../2026-10-07/ent_auth/verification/coregd_app) sees boot-time storage values once — count calls and deltas per page load vs a2
   and 0.9.12; (c) boot delta size and frame count vs a2 (no duplicate storage echoes, no extra round trip); (d) a computed var that
   depends on a storage var is correct right after boot; (e) a storage value the server changes in on_load wins over the browser's;
   (f) many tabs + `storage` events (sync=True) do not ping-pong; (g) >1 MB storage (F-008) unchanged.
3. Third-party packages that keep auth in client storage: reflex-local-auth and reflex-google-auth (google_auth_demo in src/) —
   login, reload, logout, second tab — on a3 vs alpha2 vs 0.9.12.
Write one inbox file per finding. Copy artifacts to DEST as you go; commit per the protocol.
