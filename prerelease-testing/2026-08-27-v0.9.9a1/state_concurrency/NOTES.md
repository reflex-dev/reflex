# state_concurrency cluster — reflex 0.9.9a1 pre-release testing

Changelog items covered: #6920 (background-task delta race), #6830 (state manager
lock isolation), #6734 (emit_update task wrapper removal / flush tick).

Result: **all checks pass on 0.9.9a1** (dev and prod mode). The 0.9.8 baseline
reproduces the pre-#6920 lost-delta bug with a metronomic 1-lost-update-per-
background-completion signature, and 0.9.9a1 eliminates it completely. No
regressions found; two benign observations recorded below.

## App

`concur_app/` — three pages (reflex init --template blank, then
`concur_app/concur_app.py` replaced):

- `/` (RaceState): foreground counter (`inc` sync handler, `inc_io` async
  handler that awaits 25ms AFTER the write — the realistic pre-#6920 loss
  shape), a one-shot background task `bg_once` (two `async with self` writes,
  30ms apart, then a 50ms unlocked tail, then a final locked write), a
  long-running background `run_poller` (40 ticks at 10 Hz), an **uncached async
  computed var** `window` (sleeps 20ms during every delta resolution while
  `widen=True`, widening any unlocked snapshot->clean window, mirroring the
  #6920 unit regression test), and an `rx._x.client_state` ClientStateVar
  (`csclicks`) incremented client-side on the same clicks as the server counter.
- `/noctx` (NoCtxState): `bg_nudge` background handler that never enters
  `async with self` (uncached computed var `heartbeat` shows whether a delta
  flushed); `bg_illegal_write` mutates without the context (expected error).
- `/stream` (StreamState): sync generator handler yielding progress 1..10 with
  `time.sleep(0.12)` after each yield (deliberately blocking the event loop so
  only the post-emit flush tick can get interim packets out).

## How to rerun

```bash
# venvs: reflex==0.9.9a1 in envs/smoke, reflex==0.9.8 in a second venv;
# driver venv needs playwright (chromium at /opt/pw-browsers/chromium)
cd concur_app
REFLEX_TELEMETRY_ENABLED=false <venv>/bin/reflex run \
    --frontend-port 3180 --backend-port 8180 --loglevel debug

# race hammer (20 rounds); 4th arg = button: btn-inc-both (sync handler)
# or btn-inc-both-io (async handler with await after write)
<driver>/bin/python drive_race.py http://localhost:3180/ <shotdir> 20 btn-inc-both-io
<driver>/bin/python drive_noctx.py  http://localhost:3180 <shotdir>
<driver>/bin/python drive_stream.py http://localhost:3180 <shotdir>
<venv>/bin/python check_lock_isolation.py   # run from OUTSIDE the reflex checkout

# prod mode: frontend and backend must share one port
reflex run --env prod --frontend-port 8181 --backend-port 8181
# 0.9.8 baseline: copy app sources (not .web) to a fresh dir, run with the
# 0.9.8 venv on other ports, run the same drivers.
```

drive_race per round: fire `bg_once`, click the increment button (~8 clicks)
until `bg_runs` shows the round completed plus 3 trailing clicks, then wait
for quiescence and assert the DOM counter reaches the exact cumulative click
count. A MutationObserver on `#counter` records every rendered value; after 20
rounds the script reports `counter_values_never_rendered` — counter values
whose delta never reached the DOM. Then a poller phase: `run_poller` (40 ticks,
10 Hz) with ~35 clicks spread across it, asserting exact final counts and that
`window` == bg_ticks + poller_ticks.

## Results

### #6920 race (dev + prod, 0.9.9a1): PASS
- sync handler, 20 rounds, dev: 151/151 clicks rendered, 0 stale rounds,
  bg_ticks 40/40, poller 35/35 + 40/40 ticks, client_state == server counter.
- prod (`--env prod`, single port): 152/152, same exactness.
- **io handler (await after write), dev: 159/159 clicks,
  `counter_values_never_rendered: []`** — every intermediate value reached the
  DOM (raw output: `race_io_099a1_dev.json.txt`).

### 0.9.8 baseline comparison (identical app + driver): FAILS as expected
`race_io_098_dev.json.txt`: 162 clicks, final value correct, but
`counter_values_never_rendered: [4, 12, 20, 28, 36, 44, 53, 61, ...158]` —
**exactly 20 lost deltas in 20 rounds, exactly one per background-task
completion, evenly spaced ~8 clicks apart** (matches the changelog's "eats
roughly 1 in 8 foreground updates that land near a poll tick"). The UI showed
e.g. 3 -> 5, skipping 4, every round. The final value is only correct because
later clicks re-send the cumulative counter; any update that is the LAST write
stays invisible until the next write — the reported UI-stale symptom.
With the purely synchronous `inc` handler 0.9.8 shows no loss (the loss needs
a suspension point between the foreground write and its delta snapshot), which
is why the io variant exists.

### Background handler without `async with self` (#6920 follow-up): PASS
Semantics verified against PR #6920 (commit d02e452d5): a background handler
that never enters `async with self` cannot write (writes raise
ImmutableStateError), but after it returns the processor performs one
compatibility delta flush **under the state lock** (refreshing uncached
computed vars, and any preamble-dirty vars like router_data).
- `bg_nudge`: exactly **1** heartbeat DOM update per click, in dev and prod.
- `bg_illegal_write`: server logs `[Reflex Backend Exception]` +
  `ImmutableStateError: Background task StateProxy is immutable outside of a
  context manager`; no UI change, no delta, app stays fully responsive.
  Note: when the handler *raises*, no compatibility flush is emitted (the
  exception propagates before the flush) — same as pre-fix behavior.

### #6734 streaming flush tick: PASS (dev, prod, and 0.9.8 identical)
`/stream`, MutationObserver timestamps of `#progress`: all 10 interim values
rendered individually, gaps 141-142ms each (120ms handler sleep + 20ms of the
armed `window` var per delta), span ~1.28s, on 0.9.9a1 dev, 0.9.9a1 prod, and
0.9.8. No batching — the sleep(0) flush tick fully preserves the old task
wrapper's interim-update behavior even with a sync handler blocking the loop
right after each yield.

### #6830 lock isolation: PASS (script-level)
`check_lock_isolation.py` on 0.9.9a1: Memory/Disk/Redis state managers all
declare `_state_manager_lock` with `default_factory`; two StateManagerMemory
instances hold distinct Lock objects.

### client_state mixing: PASS
`cs_clicks` (client-side) and `counter` (server-side) driven from the same
button stayed equal through every hammer phase (151, 152, 159, 162 clicks) —
no interference between client-var patches and racing server deltas.

## Benign / environment observations

- Granian logs `[ERROR] Unexpected exit from worker-1` on plain SIGTERM
  shutdown of `reflex run` (dev). Also present on 0.9.8 — longstanding
  cosmetic noise, not a regression (`server_dev2.log`, `server_098b.log`).
- Dev mode uses StateManagerDisk (shared in-process state tree), so the #6920
  race scenario applies to the default dev setup, not just explicit memory
  manager.
- Environment gotcha (not reflex): overriding `NO_PROXY=localhost,127.0.0.1`
  clobbers this sandbox's default no-proxy list (which includes
  registry.npmjs.org), sending bun through the agent proxy where large
  installs die with `error: ConnectionClosed downloading package manifest`.
  Run reflex with the default proxy env instead.
- 20-run Playwright harness output files: `race_io_*.json.txt`,
  `stream_098_dev.json.txt`; screenshots in `shots_dev/`, `shots_prod/`,
  `shots_098/`.
