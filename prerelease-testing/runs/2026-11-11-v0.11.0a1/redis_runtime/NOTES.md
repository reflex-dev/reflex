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
