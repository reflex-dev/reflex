# Cluster `reverify_hydration` — re-verify F-002/F-003/F-008/F-010/F-017 on 0.10.0a2 and regression-sweep #7460

Ports: frontend 3220-3239, backend 8220-8239 (redis on 8239). Work dir: $SB/apps/reverify_hydration/. DEST: /home/user/reflex/prerelease_testing/2026-10-07/reverify_hydration/
Venv under test: $SB/envs/alpha2. Before/after: $SB/envs/alpha (0.10.0a1), $SB/envs/stable (0.9.12).

Read first: $SB/CAMPAIGN_STATE.md, /home/user/reflex/prerelease_testing/2026-10-06/FINDINGS.md FINDING-002/003/008/010/017, /home/user/reflex/prerelease_testing/2026-10-06/hydration/NOTES.md (incl. VERIFICATION),
/home/user/reflex/prerelease_testing/2026-10-06/thirdparty/NOTES.md "VERIFICATION — client-storage rewritten during hydration". COPY scripts out before running.

## Re-verify
1. F-002: /home/user/reflex/prerelease_testing/2026-10-06/hydration/verification/f1-client-storage-defaults/apps/f1combo + drivers/f1_check.py (prod, then dev) and
   /home/user/reflex/prerelease_testing/2026-10-06/hydration/mini_writeback + scripts/mini.sh + drivers/mini_writeback_check.py: fresh profile must NOT get
   localStorage/sessionStorage/cookie defaults written; returning visitor must see a changed default. Capture the first
   websocket delta frames: is `is_hydrated_rx_state_: false` now present in the root of the diffed boot delta, or did
   the fix take another route (read the published alpha2 `reflex/state.py` hydrate_and_load/_diff_against_initial_state
   and `.templates/web/utils/state.js` applyClientStorageDelta; give file:line)?
2. F-003: /home/user/reflex/prerelease_testing/2026-10-06/thirdparty/verification/clientstorage-hydrate (cvstore app, bin/start.sh, drivers/drive_cvstore.py; run the
   whole variant table a–h, PYTHONHASHSEED=0 and 4, dev + prod) and the reflex-google-auth demo
   (/home/user/reflex/prerelease_testing/2026-10-06/thirdparty/apps/google_auth_demo + drivers/drive_google_auth.py, inject-bogus-token step): the computed-var
   rewrite must now reach the browser (#7460 "Deliver changes to client-storage and other state vars made by computed
   vars during hydration"). Also variant (g) (computed var writing a different plain var) — fixed too? And the
   uncached-computed-var stale-UI side note.
3. Full regression sweep of the hydration probe app: /home/user/reflex/prerelease_testing/2026-10-06/hydration/hydapp + drivers/hyd_driver.py (all scenarios s1–s12),
   dev and prod on alpha2; compare against the saved alpha/stable results in /home/user/reflex/prerelease_testing/2026-10-06/hydration/results/. Any scenario that
   passed on 0.10.0a1 and fails on 0.10.0a2 is a NEW regression (high priority). Watch especially: sync=True two-tab
   behaviour, reconnect (memory + redis), client-storage reset via remove_local_storage, on_load ordering, the
   is_hydrated gate, and the s8 "defaults that differ from compiled defaults" first paint.
4. F-008 (s5 big value storm), F-010 (prenav_test.py with the 2 s hold; plus the verifier's f6_natural.py at D=800 for the
   redirect case), F-017 (reconnect_driver.py --manager redis, run the restart loop 6×): fixed / unchanged?
5. Timing: repeat the hydration timing comparison (alpha2 vs alpha vs stable) from /home/user/reflex/prerelease_testing/2026-10-06/hydration/drivers (80 ms RTT proxy)
   once; report medians.
Copy artifacts to DEST as you go.
