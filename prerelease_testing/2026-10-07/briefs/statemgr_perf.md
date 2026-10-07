# Cluster `statemgr_perf` — memory/disk state managers, expiry, durations, Redis pool under a real app, perf claims

Ports: frontend 3260-3279, backend 8260-8279. Work dir: $SB/apps/statemgr_perf/. DEST: /home/user/reflex/prerelease_testing/2026-10-07/statemgr_perf/ (venv under test: $SB/envs/alpha2 = reflex 0.10.0a2; baseline $SB/envs/stable)

## Why this cluster exists
Changelog (verbatim):
- (reflex, Bug Fixes) The memory and disk state managers now free expired session states right away instead of waiting for a garbage collection pass, and the disk state manager no longer keeps a lock for every expired session. (#7318)
- (reflex, Features) The duration settings read by the app and the state managers take a unit suffix: `SQLALCHEMY_POOL_TIMEOUT`, `REFLEX_SOCKET_INTERVAL` and `REFLEX_SOCKET_TIMEOUT` accept values such as `2m`, and `REFLEX_AUTO_RELOAD_COOLDOWN`, `REFLEX_OPLOCK_HOLD_TIME` and `REFLEX_STATE_MANAGER_DISK_DEBOUNCE` replace the `_MS`/`_SECONDS` names, which still work with a deprecation warning until 1.0. A bare number is read as seconds. (#7138)
- (reflex-base, Bug Fixes) Deprecation warnings no longer point at a pseudo-location such as `<string>` or `<frozen importlib._bootstrap>` when the deprecated call runs inside generated or frozen code; the location now names the first real user file. (#7138)
- (reflex, Features) Set `REFLEX_REDIS_MAX_CONNECTIONS` to cap each Redis client's connection pool ... requests wait up to `REFLEX_REDIS_POOL_TIMEOUT` (default 2s ...) for a free connection instead of opening new ones. (#7179)
- (reflex, Performance) Process events with less CPU on the backend: iterating, sorting and reading list and dataclass state values costs 25–75% less, and the redis state manager writes the changed states of a session in one round trip. (#7370)
- (reflex-base, Performance) Reading a state var is about 4x faster, and setting one about 7x faster (15x in prod mode) ... (#7312)
- (reflex-base, Performance) Building Vars (operations, comparisons, `rx.cond`, `rx.foreach`) is up to twice as fast, so pages that derive many Vars compile faster; the generated code is unchanged. (#7370)
- (reflex-base, Performance) Reuse unchanged memo-body analysis during module emission ... (#7123)
- (reflex, Performance) Skip the linked-client fan-out on events that changed nothing shared, so an app that defines an `rx.SharedState` no longer resolves the running `App` on every event. (#7237)
The previous campaign tested duration parsing and the Redis pool with a PROBE script, and Redis
recovery with an app; nobody drove the memory/disk managers' expiry with a real app, and nobody
measured any perf claim ("verify perf claims rather than trusting them").

## What to do
1. Expiry with a real app (memory manager, default): set `REFLEX_STATE_EXPIRATION=20` (seconds; check the
   exact env name in `reflex_base/config.py` of the published package — `grep -rn expiration $SB/envs/alpha2/lib/python3.12/site-packages/reflex_base/config.py`)
   and a short `REFLEX_STATE_MANAGER_...` GC interval if there is one. Open a tab, modify state (incl. a
   substate and a ComponentState), go idle > expiry, then: click again (expect a fresh state and a clean
   recovery, no traceback), reload. Measure backend RSS (`psutil`/`ps`) across 300 short-lived browser
   contexts (each sets state then closes) with expiry 5s: does memory return toward baseline after expiry?
   Compare the same on 0.9.12 (`$SB/envs/stable`). Also check the server log for lock warnings.
2. Disk manager: `REFLEX_STATE_MANAGER_MODE=disk` with `REFLEX_STATE_MANAGER_DISK_DEBOUNCE=250ms` (new name)
   and separately the deprecated `REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS=0.25`: confirm `.states/`
   files appear/are updated, state survives a backend restart, expired sessions' files/locks disappear
   promptly (#7318), and the deprecation warning is printed ONCE with a location that names a real user
   file (your rxconfig/app), not `<string>`/`<frozen ...>` (#7138). Try an invalid duration (`abc`, `-5s`,
   `5x`) → clear error. Try `REFLEX_AUTO_RELOAD_COOLDOWN_TIME_MS=500` (deprecated) with hot reload: edit the
   app file twice quickly and check behavior + warning.
3. Redis pool with an app under load: start your own redis-server; run the app with
   `REFLEX_REDIS_URL=redis://localhost:<port>`, `REFLEX_REDIS_MAX_CONNECTIONS=3`,
   `REFLEX_REDIS_POOL_TIMEOUT=500ms`; open 6 browser contexts and hammer events concurrently + a
   background task per context; look for pool timeouts in the log, dropped events, and whether the UI
   stays consistent. Then set the cap to 2 (invalid, must be >=3) and to a timeout longer than the lock
   expiration → expect clear startup errors. Also `REFLEX_SOCKET_INTERVAL=2m`/`REFLEX_SOCKET_TIMEOUT=10s`:
   does the compiled frontend socket config reflect the values (inspect `.web` output / websocket pings)?
4. Perf claims — build a benchmark app (same source on alpha and 0.9.12 venvs):
   a) compile time: a page deriving ~2,000 Vars (foreach over a 200-item list with cond/ops per item, 10
      memo components) — `time reflex export --frontend-only --no-zip` style or time the `reflex run`
      compile phase from the debug log; 3 runs each; report medians.
   b) backend event cost: a handler that iterates/sorts a 5,000-item list of dataclasses and updates 50
      vars — measure websocket round-trip latency from Playwright over 50 clicks; also run a pure-Python
      microbench with `asyncio` + `State.get_state`-style direct access if the public API allows (e.g.
      instantiate the state, time 100k reads/writes of a var) on both versions.
   c) Redis write round trips: count Redis commands per event (`redis-cli monitor` while clicking) on
      alpha vs stable with a 20-substate tree.
   d) SharedState fan-out: an app with an `rx.SharedState` defined but NOT used on the page — compare
      per-event latency vs the same app without the shared state (#7237).
   Report numbers in a table; a regression (alpha slower than stable by >20%) is a finding; a claim
   not met is an anomaly, not a defect.
