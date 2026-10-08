# Brief: a4_hydration — re-verify A3-11 / A3-12 on 0.10.0a4 and hunt #7505 regressions

Read first: `/home/user/reflex/prerelease_testing/2026-10-08-a4/AGENT_BRIEF.md` (hard rules), then
`/home/user/reflex/prerelease_testing/2026-10-08-a4/CAMPAIGN_STATE.md` (what a4 changed). Your artifacts go to
`/home/user/reflex/prerelease_testing/2026-10-08-a4/a4_hydration/`; scratch under `$SB/apps/a4_hydration/`.
Ports: frontend 3140-3159 / backend 8140-8159, plus 3660-3679 / 8660-8679 for the verifier's latency-proxy scenarios.
Redis, if needed: a port from your backend range.

## Part 1 — re-run the ORIGINAL failing repros (positive control on a3 FIRST, same machine, same load, back to back)
The a3 pass's assets are under `/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_hydration/` (COPY them out, never run
in place): `NOTES.md` (rerun commands), `src/bootecho`, `src/syncstamp`, `scripts/run_storm.sh`, `scripts/run_stamp.sh`,
`drivers/` (`stamp_storm.py`, `sync_race.py`, `latency_proxy.py`, ...), `verification/` (the verifier's own app, drivers
and scenarios: 3 restored tabs + one click, 100 ms RTT proxy, Playwright 7 restored tabs, 4 quiet `/doc/<slug>` tabs + dev
backend reload, prod + Redis 9 workers), and `pr7505/` (the fix validation: `scripts/matrix.sh`, `scripts/vh_matrix.sh`,
`results/`). The pr7505 matrix ran against a patched build; on a4 the fix is in the published package itself, so point the
scripts at `$SB/envs/a4` and `$SB/envs/a3`.

1. **A3-11** (boot-echo storm): explorer storm driver (`run_storm.sh <ver> dev 8 <FP> <BP> S 6` or equivalent) and the
   verifier's 3-restored-tabs + click scenario through the 100 ms RTT proxy, dev and prod (prod + Redis with several
   workers at least once). a3 must storm first (positive control); then a4. Report storms/runs, frame counts per 5 s,
   final values in every tab and in localStorage (must be the user's LAST value).
2. **A3-12** (on_load stamp loop): `run_stamp.sh` `/stamp` with 4–6 tabs, the `/same` control, and the verifier's quiet
   `/doc/<slug>` tabs + one dev backend reload. a3 must loop first; then a4. Report frames per 5 s and whether all tabs
   end on ONE value.
Give each a pass/fail table (a3 vs a4, dev vs prod, runs).

## Part 2 — #7505 regression hunt (real-world, end to end, dev AND prod)
Build one small app (or extend bootecho) that combines: `rx.LocalStorage` with `sync=True` and `sync=False`,
`rx.SessionStorage`, `rx.Cookie` (with `max_age`), storage vars on a substate and in an `rx.ComponentState`, a `get_delta`
override (or computed var) that SANITISES a storage value (e.g. lowercases/clamps it) so the server-changed value must be
written back, handlers that set a storage var to the value it already has, to "" and back, to unicode / JSON-looking /
long strings, an `on_load` that writes a storage var, a background task that writes one inside `async with self`, and
`yield`ed event chains. Drive with 1, 2 and 3 tabs: reload, close/reopen, navigate between pages, change in tab A and check
tab B (sync=True must follow, sync=False must NOT follow), change quickly in both tabs (must converge to ONE value, and the
last writer should win), back-to-back clicks. Specific must-checks:
- the review bug: a `sync=False` LocalStorage var written by a handler must be persisted (reload shows it) — including when
  the written value equals the one the tab sent at boot, and when another tab wrote the same key meanwhile;
- a sanitising server-side change to a value the tab just sent must reach localStorage (the override's output, not the
  echo) — this is the one thing #7505's echo skipping could break;
- F-002 / F-003 stay fixed: a FRESH browser profile gets no storage keys written on first load (dev, prod, prod/Redis);
- cookies: still rewritten at boot (max_age renews) — compare with a3; SessionStorage: per-tab, never synced;
- reflex-local-auth 0.5.0 (`$SB/downloads/reflex-local-auth`, see the a3 notes for how it was run): register/login/logout,
  two tabs logged in, logout in one tab, reload; google-auth bogus-token clearing (`a3_hydration/scripts/run_gauth.sh`).
Inspect all four channels every run (server log, console errors+warnings, failed requests, websocket frame counts).
Anything that differs from a3 → re-run on a3 AND 0.9.12 to classify (regression vs a3 / vs 0.9.12 / pre-existing).

Known and filed, do NOT report again: several `sync=True` vars sharing one storage `name` sync only the last (reflex#7506);
F-008 (>1 MB storage storm); A3-13 (storage-dependent computed vars run twice per load).

Report in the structured format of AGENT_BRIEF.md, with `REVERIFIED:` lines for A3-11 and A3-12.
