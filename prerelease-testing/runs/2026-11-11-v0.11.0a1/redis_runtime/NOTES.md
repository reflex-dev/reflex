# redis_runtime — 0.11.0a1 (redis locks / redis-py 8 / bg-task cancel / hot reload / spawn)

## Status / resume here
- DONE: load/correctness matrix (A). NEXT: fault injection (B: lost notify, kill -9, redis restart, SIGSTOP), Chromium
  cancellation driver (C: #7412/#7696/#7738), dev hot reload #7616 + spawn #7590 (D), py3.11 shutdown (E), EVT-04/STATE-20 (F).
- Helpers: `$SB/apps/redis_runtime/bin/lib.sh` (start_app/stop_app/redis_up/wait_up; pids via `setsid sh -c 'echo $$ > pidfile; exec ...'`
  — plain `setsid cmd & echo $!` records the wrong pid in this shell because setsid forks).

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
