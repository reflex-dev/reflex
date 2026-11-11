# redis_runtime — 0.11.0a1 (redis locks / redis-py 8 / bg-task cancel / hot reload / spawn)

## Status / resume here
- DONE (all sections A-F below). Final report: `../reports/redis_runtime.md`. All servers/redis stopped.
- To rerun from this directory: copy `bin/` to `$SB/apps/redis_runtime/bin/` and `apps/{lockapp,devapp}` to
  `$SB/apps/redis_runtime/src/` (scripts hard-code those paths via `bin/lib.sh`); each script's docstring/usage line has
  the command. Drivers: `redis_runtime-drv` venv (python-socketio[asyncio_client], aiohttp, redis) and shared `driver`.

## Environment
- `SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`; ports fe 3220-3239, be 8220-8239, redis 8236-8239.
- A stock `pip install reflex==0.11.0a1` (no `--pre`) resolves **redis 8.1.0** (final), reflex-components-lucide 1.1.1,
  reflex-hosting-cli 0.2.1 (`pip --dry-run --report`, logs/pip_report.json). uv needs `--prerelease=allow` (reflex-base
  pre pin is transitive), which pulls **redis 8.2.0b1** (a beta) — that is what the shared `new` venv has. Users of
  `uv pip install --prerelease=allow` get a redis-py beta; pip users get 8.1.0.
- Venvs (all PyPI, `--only-binary :all:`, cwd=$SB, `--no-config`):
  - `redis_runtime-stock`: py3.12, reflex[db]==0.11.0a1, redis==8.1.0, lucide 1.1.1, hosting-cli 0.2.1 (= pip stock graph)
  - `redis_runtime-r7`: same + redis==7.4.1
  - `redis_runtime-py311`: py3.11.18, redis 8.1.0; `redis_runtime-py311r7`: py3.11, redis 7.4.1
  - `redis_runtime-drv`: python-socketio[asyncio_client], aiohttp, redis (raw socket.io load clients)
  - shared: `new` (redis 8.2.0b1), `prev` (0.10.1, redis 7.4.1), `driver` (playwright)

## Apps and scripts (copied to DEST `apps/`, `bin/`)
- `apps/lockapp`: Counter state (incr, incr_async, slow, bg_incr, `supersedes=True` sup, raise_mid, linked #7738 bg task with
  armed unpickle failure / redis CLIENT PAUSE from inside the parent's unpickle to open a cancel window), Other state;
  Starlette `api_transformer` routes `/api/bump` (app.modify_state, lands on any granian worker), `/api/get` (locked read via
  modify_state; `&unlocked=1` = state_manager.get_state), `/api/cancel` (cancels the token's linked bg task in this worker), `/api/pid`.
- `apps/devapp`: cached vars (`label`, `label2` depends on `label`, `Child.child_label`), `state_auto_setters=True` input.
- `bin/load.py` (drv venv): raw python-socketio clients (own token each), seq (wait for each delta = frontend behaviour) or
  pipelined events + concurrent bg_incr + `/api/bump` on the same token; checks final count == expected via locked read.
- `bin/matrix.sh OUT "<venvs>" "<oplock 0 1>" "<workers>"`: prod + Redis 8236 on 3220, per config 4 loads, then SIGTERM time.
- `bin/summ.py OUT.jsonl` prints the table.

## A. Lock correctness + latency matrix (prod, Redis 7.0.15 server, GRANIAN_WORKERS 1/2/4, oplock off/on)
Rerun: `bash $SB/apps/redis_runtime/bin/matrix.sh $W/logs/matrix.jsonl "redis_runtime-stock prev new redis_runtime-r7" "0 1" "1 2 4"`
(≈20 min). Raw: `logs/matrix.jsonl` + `logs/matrix_op1_rerun.jsonl` (the first run's oplock rows for stock/prev used an
unlocked read for the final check -> stale under oplock by design; rerun with the locked read).
- **Correctness: every config, every version: final count exact** (8x50 seq, 4x50 seq + bg100 + api50, 8x50 pipelined +
  bg40 + api40, 1x300 pipelined + bg200 + api200 on ONE token). No lost update, no timeout, no server error.
- Uncontended event latency (seq8x50, ms p50/p99): ~equal across 0.10.1 / 0.11.0a1 / redis 7 / 8 (e.g. w4 op0: prev 3.6/17.7,
  stock 3.3/8.7, new 3.0/7.6, r7 3.6/9.1). **No latency regression.**
- oplock OFF, contended: api p99 < 300 ms everywhere, both versions.
- **oplock ON, >=2 workers, contended:** 0.10.1: api p99 5000-10000 ms (the stall #7534 fixes; total run 10-16 s).
  0.11.0a1 (redis 7 and 8 alike): p99 ~1000-2000 ms, run 2-4 s. Big improvement, but residual ~1 s stalls remain -> see ISSUE
  "oplock: second waiter on an instance passed over" below.
- SIGTERM stop of the prod tree: 0.5 s in every config (no hang, no "different loop" or redis errors in the logs).

### Residual oplock stall (investigated)
`bin/load.py BASE --clients 1 --events 300 --mode pipe --api 100 --api-conc C` on stock, oplock on, 2 workers, 6 runs each
(`logs/conc_new_op1_w2.jsonl`): C=1 -> 0/6 runs with an api wait > 500 ms; C=2 -> 3/6; C=4 -> 4/6 (each ~1010-1040 ms =
lock_expiration/10 re-check). Debug log (`REFLEX_STATE_MANAGER_REDIS_DEBUG=true --loglevel debug`, `logs/dbg-op1.log`):
a lease is created ("obtained lock" + "lease breaker") while a waiter on the other worker is still waiting, and nothing
happens until that waiter's 1 s "wait timeout" re-registers it as a contender ("OPLOCK CONTEND - lease break task cancelled").
Mechanism (source, v0.11.0a1 `reflex/istate/manager/redis.py`): contenders are a redis SET of *instance ids*
(`_register_lock_contender` SADD `self._instance_id`); every waiter's `_request_lock_release` exit does
`SREM <lock>_waiters <instance_id>`, so when the first of two waiters on worker B gets the lock, B is removed from the set
although its second waiter is still queued; the holder on worker A then sees `_n_lock_contenders == 0` and starts a new
lease, and B's second waiter is passed over until its 1 s re-check. (0.10.1 had the same SREM but waited a full
lock_expiration; #7534's 1/10 re-check caps it at ~1 s.) Note also `SMR = f"[SMR:{os.getpid()}]"` is computed at import, so
forked workers all log the supervisor's pid (debug-only cosmetic).

## B. Fault injection (prod, 2 workers, oplock off; `bin/faults.sh <venv> 0 2 OUT [scenarios]`, prod 3221, redis 8237)
Raw: `logs/faults_lost.jsonl`, `faults2.jsonl`, `faults3.jsonl`, `faults4.jsonl`, `kill9.jsonl`.
- **Lost lock-release notification (#7534 claim)** — `slow(2000)` holds the lock on worker A, 10 `/api/bump` wait (some on
  worker B); at +1.9 s `CONFIG SET notify-keyspace-events ""` (all release notifications lost):
  0.11.0a1: worker-B waiters finish **0.33 s** after the release (1 s re-check); 0.10.1: **8.35 s** (waits a full
  lock_expiration). FIXED as claimed. `CLIENT KILL TYPE pubsub` at +1.9 s: both versions fine (subscriber reconnects in time).
- **SIGSTOP redis-server 10 s** (half-open-like): both versions: events and API calls hang silently (no error, no toast)
  for the whole stop and complete 2 ms after SIGCONT; count exact. `socket_timeout=None` (#7757) = same as 0.10.1+redis 7.
  A real black-holed TCP connection (no RST) would hang until TCP keepalive; iptables not available to test.
- **redis-server SHUTDOWN SAVE, 10 s down, restart (same dump)**: both versions: event during the outage -> error toast
  "An error occurred." (ConnectionError) and the event is dropped; `/api/bump` -> 500; first event after restart 2 ms.
  **But** each worker's RedisTokenManager pubsub tasks give up after 5 failures in 60 s
  (`_subscribe_lost_and_found_updates: task exceeded exception limit 5 within 60.0s`, same for
  `_subscribe_socket_record_updates`) and are only re-created by a NEW socket connecting to that worker. After the restart,
  updates for an existing client produced on another worker are silently dropped: 10 bumps -> api deltas received =
  10 - bumps_on_other_worker in all 3 runs (stock 6/10 with 4 on B, prev 9/10 with 1, r7 5/10 with 5). Same on 0.10.1. ISSUE.
- **kill -9 of one granian worker mid-event**: granian logs `[ERROR] Unexpected exit from worker-1` and **the whole prod server
  stops** ("Info: Reflex app stopped."), both versions (no worker respawn). Restarting the server at once and reconnecting the
  same token: the server answers `new_token` (the dead worker's socket record is still in redis) -> the client's session is
  replaced by a fresh state (count back to 0). Lock left by the dead worker (PTTL 9.5 s) is never waited on because the token
  changed. Both versions. Relates to registry HYD-07 (token reassigned after an unclean stop): reproducible on demand this way.

## E. Shutdown with events in flight (`bin/shutdown.sh OUT "<venvs>" "INT-group TERM-pid" prod`)
4 socket clients pipelining incr_async x300, bg_incr(2000), 100 api bumps, 3 `slow(2000)` holders; signal at +1.5 s.
- Python 3.11.18 + redis 8.1.0 / 7.4.1, Python 3.12 + redis 8.1.0 / 7.4.1, 0.10.1: **every stop 1.0-1.8 s, no hang** (16 runs).
- Anomaly (1/7 SIGINT runs on stock 3.12 + redis 8.1.0, 0/6 on 0.10.1): 3 `[Reflex Backend Exception]` tracebacks at shutdown:
  `CancelledError` in `get_state` -> `mget`, then during handling, `_lock` finally -> `_release_lock` -> `self.redis.eval` ->
  `pool.get_connection()` -> `connection.connect()` -> `asyncio/selector_events.py writelines -> self._write_ready()`
  `TypeError: 'NoneType' object is not callable` (the shielded re-release of #7534 opens a new connection while the loop's
  transports are being torn down). Log overwritten by a rerun (tag reuse, fixed since); excerpt recorded here.

## C. Cancellation / failed handlers in Chromium (`bin/drive_cancel.py BASE OUT SHOTS`; prod + Redis 8237, 1 worker, 3221)
Rerun: `REFLEX_REDIS_URL=redis://localhost:8237 REFLEX_API_URL=http://localhost:3221 GRANIAN_WORKERS=1 reflex run --env prod --frontend-port 3221 --backend-port 3221`
in a copy of `apps/lockapp`, then `$SB/envs/driver/bin/python bin/drive_cancel.py http://localhost:3221 out.json shots/`.
| check | 0.11.0a1 (stock, redis 8.1.0) | 0.10.1 |
|---|---|---|
| raise_mid (`r1+=1; yield; r2+=1; raise`): UI and server r1=r2=1, survives reload | PASS | FAIL: UI r1=1/r2=0, server r1=0/r2=0 (rollback; EVT-16) |
| `supersedes=True` twice (2nd cancels 1st after 0.75 s): first call's progress kept, UI == server | PASS (calls 2, progress 8, done 1) | FAIL: server calls 1 / progress 5 (first invocation's writes lost; EVT-08) |
| #7738 linked `get_state` load fails, then incr | 0.055 s | 0.055 s (control does not reproduce, see below) |
| #7738 cancel while the linked state loads (redis CLIENT PAUSE 3 s opened from inside the parent's unpickle; `paused_at` confirms), then incr | 0.06 s | 0.06 s |
| bg task (50 increments) while navigating / -> /other -> / | PASS | PASS |
| close the tab mid `slow(3000)`, reopen same token | event completed server-side; next event 4 ms | same |
Console: only the favicon 404. 0.10.1 server log also shows `RuntimeError: aclose(): asynchronous generator is already running`
after the raise path (first driver version re-entered `self`).
#7738 note: in a real app the 0.10.1 bug is masked: once the bg task ends (or even while it lives on, `linked_hold.py
fail_hold`, 0.02 s), the leaked parent context is finalized by the loop's async-generator hook and the lock released.
The armed failure first fired at SAVE time (`__getstate__` deep-copies defaults) — fixed by `Bomb.__deepcopy__`; the final
variant's second load did not raise at all (Other apparently not re-unpickled), so the true linked-load failure path
was only reached through the cancel variant. Positive control never reproduced -> #7738 "verified no regression", not
"verified fixed".

## D. Dev hot reload #7616 and auto setters #7590 (`bin/drive_dev.py BASE APP_DIR LOG OUT [--setter-only]`, apps/devapp)
- #7616 (dev, 3222/8222): bump n to 3, edit `CODE_VERSION = "V1"` -> `"V2"`, reload the page (same token):
  0.11.0a1 disk manager and Redis: label `V2:3`, label2 `L2[V2:3]` (cached var depending on a cached var), child
  `child-V2:3`, fields n=3 / name kept. FIXED. 0.10.1 disk and Redis: still `V1:3` 110 s after the edit (stale until the
  next write). Note: 0.11.0a1 restarts the worker on reload (pid changes), 0.10.1 kept the pid.
- #7590 `state_auto_setters=True` + `on_change=S.set_name`:
  | mode | 0.11.0a1 | 0.10.1 |
  |---|---|---|
  | prod `REFLEX_BACKEND_START_METHOD=spawn GRANIAN_WORKERS=2` | PASS | FAIL `KeyError: 'No registered handler found for event: ...s.set_name'` + frontend "state schema" mismatch warning |
  | dev `REFLEX_STRICT_HOT_RELOAD=1` | PASS | FAIL (same) |
  | dev `REFLEX_BACKEND_START_METHOD=spawn` | PASS | FAIL (same) |
  | Python 3.14.6 dev default / prod 2 workers (STATE-26) | PASS / PASS | PASS (dev default; control does not reproduce on Linux) |
- Docs/Dockerfiles: `docker-example/*/Dockerfile` and `docs/hosting/*.md` only use `reflex run`; no hard-coded
  `app:app` granian/uvicorn targets, so the `reflex.utils.exec:_backend_app` factory change breaks nothing documented.

## F. Registry re-verification
- EVT-04 (`bin/drive_evt04.py`, prod + Redis, DEFAULT workers = 8): 6 Chromium tabs each start bg_incr(50) and get 10
  `/api/bump` from all 8 workers: 6/6 tabs show bg 50 / api 10 / count 60, both 0.11.0a1 and 0.10.1.
- STATE-20: `fixtures/class_state/bin/n004_redis_chain.sh prev redis_runtime-stock prev redis_runtime-stock` (overrides:
  `W=$SB/apps/redis_runtime/cs REDIS_PORT=8238 CHAIN_PORT=3224 PORT_LO_F=3220 PORT_HI_F=3239 PORT_LO_B=8220 PORT_HI_B=8239`):
  one token survives 0.10.1 -> 0.11.0a1 -> 0.10.1 -> 0.11.0a1 (limit 10->11->12->13->14, items/mixin carried), no server errors.
  `n004_matrix.sh` (stock, new, prev, py311): schema hashes identical everywhere (HBase=2efae263… HChild=f2d2a961…
  HCfg=472cb6c5… HSd=cb3b6199…), all 32 save/load pairs LOADED, including Python 3.11 <-> 3.12 (STATE-21 not reproduced
  for these shapes).
- EVT-08 / EVT-16 (supersedes / raise rollback under Redis): fixed (table C).
- HYD-07 (token reassigned after an unclean stop): reproducible on demand: kill -9 a worker -> restart -> `new_token` (B).

## Misc
- `REFLEX_REDIS_URL=...?socket_timeout=2` overrides Reflex's `socket_timeout=None` (URL query wins in redis-py
  `from_url`; checked on redis-py 7.4.1 / 8.1.0 / 8.2.0b1) — a usable mitigation for half-open connections.
- No "attached to a different loop", "Task was destroyed", "never awaited" in any server log (#7751; dev hot reload +
  Redis and multi-worker prod both fine).
- Table C with `REFLEX_OPLOCK_ENABLED=true`, 2 workers: 0.11.0a1 raise/supersedes/reload/bg/disconnect PASS; 0.10.1:
  raise_mid UI r2=0 while the server has r2=1 (client/server divergence, #7696 fixed). The #7738 rows are not meaningful
  under oplock (the lease serves the cached state, so the armed unpickle never runs; the left-over armed CLIENT PAUSE then
  fires on a later load and delays that event 3 s — a harness artifact, not a finding).


## ISSUES (details for the report)
1. **Redis outage > ~5 s silently breaks cross-worker delivery to existing clients until a new socket reaches that worker**
   (MEDIUM, not a regression: 0.10.1 identical). Repro: `bash bin/faults.sh redis_runtime-stock 0 2 out.jsonl redis_restart`
   (prod, GRANIAN_WORKERS=2, redis 8237: one raw socket client, `SHUTDOWN SAVE`, 10 s down, restart same dump, then 10
   `/api/bump` on fresh connections). Result field `cross_worker_after_restart.api_deltas_received` = 10 -
   `bumps_other_worker` in every run (stock 6/10, r7 5/10, 0.10.1 9/10 with 1 on the other worker); server log:
   `_subscribe_lost_and_found_updates: task exceeded exception limit 5 within 60.0s` and the same for
   `_subscribe_socket_record_updates` (`logs/redis_restart-*-server-excerpt.txt`). The tasks are only re-created by
   `on_connect` / `link_token_to_sid` on that worker, so a single long-lived tab never gets background/out-of-band updates
   produced on another worker again (state is updated server-side; the UI is stale). `reflex/utils/tasks.py` `_run_forever`
   (exception_limit=5 in 60 s, 1 s delay) + `reflex/utils/token_manager.py` `ensure_lost_and_found_task`.
2. **kill -9 of one granian worker stops the whole prod server, and the restarted server gives the returning client a new
   token (session lost)** (MEDIUM, not a regression). Repro: `bash bin/kill9.sh redis_runtime-stock 2 out.jsonl` (prev
   identical). Log: `[ERROR] Unexpected exit from worker-1` / `Info: Reflex app stopped.` (`logs/kill9-stock-server-tail.txt`);
   resume run: `new_token` on connect, count back to 1 (`logs/kill9.jsonl`). The dead worker's
   `token_manager_socket_record_<token>` key outlives it, so duplicate-tab detection fires. Relates to HYD-07.
3. **Oplock (`REFLEX_OPLOCK_ENABLED=true`, >= 2 workers): a second waiter on the same instance is passed over by the next
   lease and waits ~1 s (lock_expiration/10)** (LOW: opt-in, 5-10x better than 0.10.1, but contradicts the #7534
   changelog "events waiting on other instances are no longer passed over by the next lease"). Repro:
   `REFLEX_OPLOCK_ENABLED=true GRANIAN_WORKERS=2` prod + Redis, then
   `load.py BASE --clients 1 --events 300 --mode pipe --api 100 --api-conc 2` x6: 3/6 runs have an api wait of
   1010-1040 ms; `--api-conc 1`: 0/6. Mechanism: per-instance contender SET + SREM on every waiter exit (section A).

## VERIFICATION
Independent verifier `verify_rds` (2026-11-11). Own PyPI venvs, `--only-binary :all:`, cwd=$SB, `--no-config`:
`$SB/envs/vrds-new` = reflex 0.11.0a1 + reflex-base 0.11.0a1 + redis 8.1.0 + granian 2.8.7 (`--prerelease=allow`, redis pinned);
`$SB/envs/vrds-prev` = reflex 0.10.1 + redis 7.4.1 + granian 2.8.7 (no `--prerelease`); `$SB/envs/vrds-drv` = python-socketio,
aiohttp, redis; Chromium checks with the shared `driver`. Ports: prod 3720-3722, Redis 8733. Scripts, the app (with
test-only hooks, each env-gated and off by default) and trimmed evidence: `../verify_rds/` (`bin/`, `apps/lockapp`, `respawn_hook/`, `logs/`).
To rerun: copy `../verify_rds/bin` to `$SB/apps/verify_rds/bin` and `../verify_rds/apps/lockapp` to `$SB/apps/verify_rds/src/lockapp`
(paths are hard-coded in `bin/lib.sh`, as in the reporter's scripts).

**Gaps in this NOTES.md that the repro needed filled in:** (1) scripts hard-code `$SB/apps/redis_runtime`, ports 3220-3239/8236-8239
and the `redis_runtime-drv` venv name (assert); a stranger must sed all three. (2) `faults.sh` cannot set the outage length
(`--down` exists only in faults.py, and the `during` wait hard-codes 3 s, so the outage is never shorter than ~4 s). Verifier copy: `DOWN=<s>`.
(3) The kill9 numbers depend on which worker the socket lands on; nothing says so. (4) The issue 1 mechanism is incomplete (below).

### V1. Oplock "second waiter on the same instance passed over" -> NARROWED to a wider root cause, low, not a regression
Root cause at v0.11.0a1, confirmed with a probe route (`/api/iid`, `bin/iid.sh`, 60 requests across 4 workers):
**every forked granian worker shares ONE `StateManagerRedis._instance_id`** (`logs/iid.jsonl`: fork -> 4 pids, 1 state-manager id,
4 token-manager ids; `REFLEX_BACKEND_START_METHOD=spawn` -> 4 / 4 / 4; 0.10.1 fork -> 4 / 1 / 4).
- `reflex/istate/manager/redis.py:261` picks `_instance_id` once per manager. The manager is created in `App._setup_state` (`reflex/app.py:753`),
  and that runs in the supervisor when prod fork preloads the app (`reflex/utils/exec.py:1118` `prerequisites.get_app()` via `_preload_for_fork`, called at :1148).
  Forked workers inherit it. `App._setup_event_processor` (`app.py:898-900`) resets only the *token manager's* id per worker.
- The oplock contender registry is a Redis SET of that id: SADD at `redis.py:1161`, SREM on every waiter exit at `redis.py:1146`, SCARD at
  `:1123`, consulted at `:697-700` (single update vs lease) and `:880-884` (lease creation). Lease breaking reacts only to a `sadd` keyspace event (`:988`).
  With one shared id: a waiter on worker B whose id is already in the set does a no-op SADD. Redis emits no `sadd` event, so the lease is not broken. A waiter exiting
  on ANY worker deregisters ALL workers. A queued waiter is then invisible until its `lock_expiration/10` re-check re-registers it (`:1251`), so
  it stalls ~1 s.
- The reporter's same-instance SREM mechanism is real but secondary. A 2x2 on the real app (`bin/oplock.sh`, prod, oplock on, 2 workers,
  `load.py --clients 1 --events 300 --mode pipe --api 100`, 6 runs per api-conc, plus 3 spot loads; `logs/oplock.jsonl`). The figures count runs with any api wait over 500 ms:
  | start method / test-only SREM patch | conc1 | conc2 | conc4 | spot (8x50+bg+api etc.) |
  |---|---|---|---|---|
  | fork (default) / unpatched | 1/6 | 4/6 | 5/6 | 3/3 |
  | fork / patched (`RDS_PATCH_SREM=1`: SREM only when this is the instance's last local waiter) | 0/6 | 3/6 | 6/6 | - |
  | spawn (distinct ids) / unpatched | 0/6 | 0/6 | 1/6 | 3/3 |
  | spawn / patched | - | 0/6 | 0/6 | 0/3 (max 182 ms) |
  Every stall measured 1009-1074 ms, and every final count was exact. On fork the patch cannot help, because "another instance" is the same id.
  Debug trace (`logs/oplock-fork-stall-trace-excerpt.txt`, records tagged with the worker pid by the `RDS_LOG_PID=1` hook): worker 10173 takes a 5 s lease ("obtained lock" -> "lease breaker ... sleeping for 5.0s") while worker 10171's
  single api waiter is queued. That waiter's "wait timeout" fires 1.0 s later, then "OPLOCK CONTEND - lease break task cancelled", and then it acquires.
  The reporter's conc1 = 0/6 does not hold: 1/6 here, which the SREM theory cannot explain (one api waiter at a time).
- Changelog #7534 sentence "events waiting on other instances are no longer passed over by the next lease": **false as written for the
  default Linux prod deployment (fork, >=2 workers)**. Waiters on other workers are passed over by the next lease. #7534's 1/10 re-check
  only bounds the wait to ~1 s, down from the 5 s hold. It holds only under spawn (macOS/Windows default) with one waiter per worker.
- 0.10.1 shares the id too (fork) and stalls 5-10 s (reporter's matrix) -> not a regression. Severity low: oplock is opt-in, the stall is bounded at 1 s, and no update is lost.
  Fix shape: give each worker its own `StateManagerRedis._instance_id` (reset it next to `_token_manager._reset_instance_id()` in
  `_setup_event_processor`, or after fork). Also count contenders per waiter, e.g. SET members `instance_id:lock_id` or a hash counter, so an
  exit removes only itself. Or reword the changelog.
- Side observation (in-process only, `bin/oplock_pass_over.py --stream 1 --a-events 1000 [--no-oplock]`, `logs/barging.jsonl`): two managers
  in one loop. Manager A does 1000 back-to-back modifies with no gap. Manager B's single waiter is starved for the whole loop on 0.11.0a1 (3.9-4.8 s, oplock on and off)
  and on 0.10.1 waits only 0.03-0.22 s. The cause is `_wait_lock` "instaque" barging (`redis.py` `_wait_lock`: an instance with no *local* waiters
  SET-NXes at once, ahead of remote waiters that are still being notified; trace `logs/inprocess-barging-trace-head.txt`, 277 instaque wins vs 1).
  A 3 ms gap between A's modifies removes it entirely (0/20 rounds stalled), and the reporter's real-app matrix (oplock off, contended) shows p99 < 300 ms on
  both versions. Recorded as an anomaly to follow up, not as an issue: not reproduced in an app.

### V2. Cross-worker updates lost after a Redis outage > ~5 s -> CONFIRMED (narrowed), medium, not a regression
`DOWN=<s> bash bin/faults.sh <venv> 0 <workers> logs/rr_matrix.jsonl redis_restart` (prod, SHUTDOWN SAVE, restart on the same dump):
| venv, workers, outage | after restart: bumps on other worker -> deltas received (of 10) | `exceeded exception limit` lines |
|---|---|---|
| new w2 10 s | 4 -> 6 | 2 |
| new w4 10 s (x2) | 8 -> 2, 9 -> 1 | 2, 2 |
| new w2 3.3 s | 4 -> 10 | 0 (6 suppressed) |
| prev w4 10 s (x2) | 6 -> 4, 9 -> 1 | 2, 2 |
| prev w2 3.3 s | 5 -> 10 | 0 |
The invariant "received = 10 - bumps that landed on another worker" held in every >5 s run on both versions. The reporter's prev 9/10 vs
stock 6/10 is only the random bump distribution (1 vs 4 bumps on the other worker), not a behaviour difference.
- Narrowing: recovery needs a new socket on the *same* worker as the stale client. In the `after_new_client` phase with 4 workers, 3 of 4 runs recovered only partly
  (3 -> 7, 6 -> 4, 5 -> 5), because the new client landed elsewhere. A busy app reconnects often and self-heals quickly. A low-traffic app, or one tab per worker,
  stays broken.
- Root cause (code byte-identical between v0.10.1 and v0.11.0a1: `diff` of `reflex/utils/tasks.py` and `reflex/utils/token_manager.py` is empty):
  `reflex/utils/tasks.py:44-53` re-raises after `exception_limit` (default 5, `:67`) suppressed errors with `exception_delay=1 s`.
  `RedisTokenManager.ensure_lost_and_found_task` (`token_manager.py:438-453`) and `_ensure_socket_record_task` (`:306-313`) use those defaults.
  They are re-created only from `on_connect` (`app.py:2349-2351`) and `link_token_to_sid` (`token_manager.py:332`). Note `:38-41`: the first error
  after a long healthy run resets the counter, so a long-running worker tolerates ~6 failures; separate short blips within 60 s add up.
  A dead `_subscribe_socket_record_updates` also stops `_handle_socket_record_del` re-storing expiring records (reasoned, not tested).
- Fix shape: run these long-lived pubsub subscribers without an exception limit (capped backoff), and/or `ensure_*` them from the
  emit / `emit_lost_and_found` path. After a resubscribe, re-store the worker's own socket records, since keyspace events were missed while it was down.

### V3. kill -9 of one worker stops the server and the client gets a new token -> RECLASSIFIED into two parts, not a regression
`bash bin/kill9.sh <venv> 2 logs/kill9.jsonl` reproduces on both versions: `[ERROR] Unexpected exit from worker-2` / `Info: Reflex app stopped.`, resume -> `new_token`, count 1.
Separating the parts (`bin/kill9b.sh vrds-new 2 logs/kill9b.jsonl <mode>`):
| mode | server alive 3 s after | stale socket record | resume |
|---|---|---|---|
| `respawn`: test-only `respawn_hook/sitecustomize.py` forces granian `respawn_failed_workers=True` | **yes** | 1 | **new_token**, count 1 |
| `delrec`: server stopped; DEL `token_manager_socket_record_<tok>` before restart | no | deleted | **same token, count 2** |
| `clean`: SIGTERM with the socket connected, restart | no | 0 | same token, count 2 |
- (a) "Whole server stops" is **granian's default**, not reflex code: `granian/server/common.py:125` `respawn_failed_workers=False`, and at `:549` the supervisor
  breaks its serve loop on a child exit. Reflex builds `Granian(...)` (`reflex/utils/exec.py:1152-1161`, same in 0.10.1) without that option. The
  `GRANIAN_RESPAWN_FAILED_WORKERS` env var is read only by granian's click CLI (`cli(auto_envvar_prefix='GRANIAN')`); `Server()` reads no env.
  So a `reflex run --env prod` user has no knob. Low/medium: fail-fast is acceptable behind a process supervisor. Fix shape: pass
  `respawn_failed_workers=True` (granian has crash-loop detection, 5.5 s) or expose an env/config option.
- (b) The session loss is **reflex's own** and happens even when the server survives (respawn row): the dead worker's socket record
  (TTL `redis_token_expiration`, default 3600 s, `token_manager.py:225`) makes `link_token_to_sid` treat the returning tab as a duplicate
  (`token_manager.py:342-346` `if token_exists_in_redis: token = new_token`). Every client of a crashed or OOM-killed worker that returns within
  1 h loses its state. Medium, not a regression (HYD-07 on demand). Fix shape: a per-instance liveness key (heartbeat with a short TTL). On
  link, take over a record whose instance is dead instead of issuing a new token, or keep socket records on a short TTL refreshed by the owner.

### V4. PASS spot-checks -> CONFIRMED
- Lock correctness, oplock on, 2 workers, new (fork and spawn, patched and unpatched): every load reached the exact final count, server-side
  (locked `/api/get`) and in the client's delta stream: 75/75 loads in `logs/oplock.jsonl`, including `pipe8x50+bg40+api40` 8/8,
  `pipe1x300+bg200+api200` 1/1 and `seq4x50+bg100+api50` 4/4 in each of the 3 spot runs (fork, spawn, spawn+patch).
- #7412 under Redis (Chromium, prod, 1 worker, `bin/cancel.sh <venv> 0`, `logs/cx-*.json`): new: raise_mid r1=r2=1 (UI == server),
  `supersedes=True` calls 2 / progress 8 / done 1, kept after reload. 0.10.1: raise_mid server r1=r2=0 (UI r2=0), supersedes calls 1 / progress 5
  (first call's writes lost) -> control fails as claimed. `linked_fail_then_event` reports FAIL on BOTH versions because the armed failure never
  fires (status "ok"). That is the reporter's known harness limitation, not a finding.
