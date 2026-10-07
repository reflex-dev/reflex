# Item `a3_ent_auth` — N-032 (reflex#7493) on 0.10.0a3 + enterprise 0.9.7a5, OIDC/MCP regression sweep

Ports: frontend 3340-3359, backend 8340-8359 (redis 8349, mock OIDC provider 8358). Work dir: $SB/apps/a3_ent_auth/.
DEST: /home/user/reflex/prerelease_testing/2026-10-07-a3/a3_ent_auth/
Venvs: $SB/envs/a3-ent (under test), $SB/envs/s912-ent-a5 (baseline), $SB/envs/alpha2-ent (a2 + a4: the a2-pass state, for before/after),
$SB/envs/a3 / alpha2 / stable for the core-only fixture. CI=true REFLEX_TELEMETRY_ENABLED=false AUTHLIB_INSECURE_TRANSPORT=1 + OIDC_* as before.

Read first: ../CAMPAIGN_STATE.md, ../AGENT_BRIEF.md, ../../2026-10-07/FINDINGS.md "N-032", "N-033", ../../2026-10-07/ent_auth/NOTES.md and
../../2026-10-07/ent_auth/verification/NOTES.md (vauth app, drivers/vdrv.py modes xtab|stale|away|logins|storm, coregd_app + coregd_drv.py,
bin/). COPY everything you run. reflex#7493 (merged): client-storage vars applied by `hydrate_and_load` are re-marked dirty after the
guarded snapshot, so the boot delta passes through `get_delta` overrides (read the PR with mcp__github__pull_request_read).

## Do
1. N-032 original repros, same counts as the a2 pass, on a3-ent: `vdrv.py away` (3 reps) dev Redis, prod Redis (1 worker), dev memory;
   `vdrv.py stale` (the deterministic probes: anonymous tab with bogus hash corrected, signed-in tab re-asserting its hash, cookies
   cleared + hash "" ends signed out); `vdrv.py xtab` (two-tab race; report the rate next to a2's and 0.9.12's);
   ent_auth/scripts/stale_hash_probe.py and xtab_probe.py; coregd_app (core-only `get_delta` override must see the boot value on a3
   like 0.9.12). Expected: fixed everywhere.
2. Regression hunt for #7493: boot deltas now carry client-storage vars through `get_delta`. Check: a fresh anonymous browser gets NO
   token hash / cookie / localStorage default written (F-002 from the auth angle); protected-field withholding at boot
   (`enforcement.install_delta_filter`) still withholds; no duplicate cookie-sync POSTs or reconcile loops (count `/_reflex/cookies/sync`
   requests and `update_vars_internal` frames per page load vs a2); `storm` mode; login → reload → logout → login Bob on the same
   browser; proactive refresh; prod with 1 and with default granian workers (N-033 is expected unchanged: say whether the 405 rate moved).
3. Re-run the 10-05 a4 auth matrix (ent_auth/scripts/a4_matrix.sh; 36/36 on a2) and the MCP OAuth + anonymous checks
   (check_mcp_oauth_redis.py, check_mcp_anon.py) on a3-ent, dev and prod.
4. Maps (drive_maps.py) one pass dev + prod.
Write one inbox file per finding (N-032 reverify, N-033 status, anything new). Copy artifacts to DEST as you go; commit per the protocol.
