CLUSTER: a3_hydration
SUMMARY: On reflex 0.10.0a3 F-002 and F-003 stay fixed. The full reverify_hydration suite (f1combo, mini, cvstore a–j, hydapp s1–s13, reconnect, restart, token leak, prenav, preconnect, csbox) matches a2 field by field in dev, prod and prod+redis, and the positive controls still catch the 0.10.0a1 bugs. #7493 works as designed and restores 0.9.12's boot semantics, with no extra frame compared with a2: `get_delta` overrides see the browser's storage values once, sanitised values reach storage, a fresh browser gets nothing written, computed vars are correct at boot and on_load values win. One new medium regression against a2 (not against 0.9.12): a booting tab echoes the stale sync=True value it read at CONNECT time, which starts an endless cross-tab storage ping-pong (a2 0/15 runs, a3 11/17, 0.9.12 9/10). A related, generic sync=True ping-pong exists on all versions. reflex-local-auth and reflex-google-auth behave identically on a3, a2 and 0.9.12.
ARTIFACTS: /home/user/reflex/prerelease_testing/2026-10-07-a3/a3_hydration/
TESTS:
- [pass] positive controls: f1_check catches 0.10.0a1's default write-back (8 keys); drive_cvstore catches a1's F-003 (a/b/g, byte-identical to the saved run); google-auth driver catches 0.9.12 seed 4; the storm drivers catch 0.9.12's ping-pong
- [pass] F-002 f1combo a3 prod + dev: fresh ×2 writes nothing; v1→v2 returning visitor sees all v2 defaults; f1_sync_tabs converges with no storage event (same as a2)
- [pass] mini_writeback a3 prod: fresh {} and no cookie; returning visitor gets the new default; user choice blue + consent cookie kept
- [pass] #7493 (a) bootecho dev/prod/prod+redis: fresh /, /plainload write nothing (LS, SS, Cookie path/max_age/same_site, sync=True LS, substate, 2 ComponentState instances); /onload writes only its on_load values
- [pass] #7493 (b) get_delta overrides: a3 sees the browser values once, in the final boot delta (Prefs 3 / SubPrefs 1 / Guard 1 calls; a2: never; 0.9.12: once, 4/1/1 calls); a sanitising override now reaches localStorage (a2 did not)
- [pass] #7493 (c) frames: returning user boot = 4 frames / 2 deltas on a3 = a2 (0.9.12: 6 / 4); fresh boot bytes identical to a2
- [anomaly] #7493 (c) bytes, by design: every browser storage value is sent twice at boot (snapshot + echo), +826 B (+24 %) for bootecho, auth_token 2× in local-auth (a2: 1×; 0.9.12: 2×)
- [anomaly] #7493 side effects shared with 0.9.12, not a2: every returning visit rewrites every storage value. Cookie expiry with max_age slides (+5–8 s after a 3 s wait); raw cookie values set outside reflex get URL-encoded (`{"a":1}` becomes `%7B%22a%22%3A1%7D`) (drivers/cookie_raw.py)
- [pass] #7493 (d) computed vars over storage vars correct at the first H:yes (T:BLUE, N:5:hello, subval+blue), dev and prod
- [pass] #7493 (e) on_load value beats the browser's value on /onload (dev, prod, prod+redis)
- [fail] #7493 (f) sync=True many tabs: a value changed while other tabs boot starts an endless storage ping-pong on a3 (dev 6/9 + 3/3 long runs, prod 2/5; a2 0/15; 0.9.12 9/10). With 2 tabs and inbound messages held, a3 shows a transient revert (1/2; a2 0/2) → a3_hydration-1
- [fail] sync=True var written by several tabs at once (on_load stamp, 3–6 tabs): endless ping-pong on a3, a2 and 0.9.12 (pre-existing) → a3_hydration-2
- [pass] #7493 (g) F-008: >1 MB storage still storms, unchanged (774 dev / 741 prod websocket opens in 22 s)
- [pass] F-003 cvstore a–j, a3 dev seeds 0/4, prod seeds 0/4, prod+redis seed 0 (9 workers): summaries line for line identical to a2; i/j pass
- [pass] F-003 google-auth bogus token cleared on the first reload: a3 dev seeds 0/4/10, prod seed 4; full report 12/13 = a2
- [anomaly] pre-existing, unchanged: client-nav cv storage rewrite is seed-dependent (N-015, seed 0 a/b/e/f/g FAIL); uncached cv shows its hydrate-time value until the next reload (N-016)
- [pass] hydapp s1–s13 dev + prod: identical statuses to a2 (s4/s10 anomalies pre-existing); cmp_hyd shows only timing, port and id differences
- [pass] reconnect prod+redis (token same, counter and LS kept), memory --default-change (NEWDEFAULT reaches the returning visitor), redis_restart_loop 5/5, token_leak 2/2 clean
- [anomaly] F-010 prenav unchanged (the left page's on_load still runs); preconnect click is processed after on_load, same as a2
- [pass] csbox: ComponentState plain-default instance now persists in a new tab (N-005 e2e fixed); instances that declare the same name share the key
- [pass] reflex-local-auth 0.5.0: a3 dev/prod/prod+redis 36/38 (known demo pitfall, same on a2 and 0.9.12) + 14/14 storage checks (fresh writes nothing, login/reload/second tab, cross-tab logout after reload, bogus token → anonymous, clean console)
- [pass] server logs: no tracebacks except intentional hydapp ones; `[ERROR] Unexpected exit from worker-1` at SIGTERM is pre-existing
REVERIFIED:
- F-002: fixed — the positive control catches a1's 8-key write-back; a3 dev/prod/prod+redis fresh profiles write nothing (f1combo, mini, bootecho incl. ComponentState/cookie options/sync, hydapp s1b, local-auth, google-auth); returning visitors see changed defaults; user choices persist
- F-003: fixed — cvstore a–j identical to a2 on seeds 0/4 in dev, prod and prod+redis (the a1 control fails as before); the google-auth bogus token is cleared on every seed
- F-008: still-broken (unchanged, pre-existing) — 1.2 MB LS: 774/741 reconnects in 22 s
- F-010: still-broken (unchanged, pre-existing) — prenav 4/4 same traces as a2
- F-017: not reproduced — 5/5 restarts kept token and state, no panic
ISSUES:
- TITLE: sync=True LocalStorage: the #7493 boot echo writes the stale value a tab read at CONNECT, so a change made in another tab during its boot starts an endless cross-tab storage ping-pong
  SEVERITY: medium
  REGRESSION: no (0.9.12 storms in 9/10 runs; regression vs 0.10.0a2: yes, a2 0/15)
  REPRO: copy prerelease_testing/2026-10-07-a3/a3_hydration/{src,drivers,scripts,srv.sh} to $SB/apps/a3_hydration; `$W/scripts/run_storm.sh a3 dev 8 3142 8142 S 6` (src/bootecho; tab0 sets the synced `be_theme` 5× 250 ms apart while 6 more tabs load in the same context; correct = all tabs show s5 and the websocket goes quiet). Compare `run_storm.sh alpha2 dev 8 ...` and `stable`. Long form: `drivers/sync_race.py http://localhost:3142 out.json 2500 6 S 60`. Two-tab transient form: `run_storm.sh a3 dev 2 3142 8142 R`.
  EVIDENCE: a3_hydration/results/sync/storm_*.json, storm_long_a3_dev_{1,2,3}.json (8k–39k frames per 5 s for 60 s, tabs stuck on mixed s2–s4, backend ~50–70 % CPU), race_*.json; trimmed/st-long-1.trimmed.log; board/findings-inbox/a3_hydration-1.md. Root cause: reflex/state.py:2401 + 2420-2422 (re-marks applied browser values dirty) → state.js:896/1076 setItem → state.js:1267 storage → update_vars_internal loop.
- TITLE: sync=True LocalStorage written concurrently by several tabs (e.g. an on_load that stamps a synced var, browser session restore) loops forever between the tabs
  SEVERITY: medium
  REGRESSION: no (pre-existing on 0.9.12, 0.10.0a2 and 0.10.0a3)
  REPRO: `$W/scripts/run_stamp.sh a3 dev 4 3142 8142 /stamp 6` (src/syncstamp: `Stamp.last = rx.LocalStorage("", name="ss_last", sync=True)` set to a per-tab value in /stamp's on_load; 6 tabs goto /stamp at once); also alpha2/stable, 3 tabs; control `/same` (same value from every tab) stays quiet.
  EVIDENCE: a3_hydration/results/stamp/stamp_*.json (a3 41k–234k, a2 118k–137k, 0.9.12 40k–64k frames per 5 s; a2 3 tabs 2/3; the volume crashed the Playwright node driver in 4/12 runs); board/findings-inbox/a3_hydration-2.md
NOT_COVERED: real Google OAuth login/logout (sandbox network; dummy client id only); Python versions other than 3.12 and browsers other than Chromium; 80 ms RTT timing for a3 vs a2 (frame counts equal, not re-measured); dev hot reload (hmr_desync) not re-run on a3; ent_auth's enterprise get_delta filters (covered by a3_ent_auth).
