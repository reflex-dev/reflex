# Verification of events-cluster claims E-1 and E-2 (reflex 0.10.0a2, 2026-10-07)

Independent verifier run, 2026-10-07 12:35-13:50 UTC (all times UTC). Claims under test: explorer `../NOTES.md`, issues **E-1** (a foreground
handler that mutates state and then raises sends no delta, disk/memory manager) and **E-2** (Redis manager discards a failed or
superseded event including changes it already delivered). E-3 (cancelled call's post-yield changes ride in the superseding
call's delta) was exercised as the disk-side counterpart of E-2(b).

Everything below was produced with **my own fixture and driver**, written before I opened the explorer's `src/mini` or
`driver/`; afterwards I ran the explorer's unmodified mini app + `drive_mini.py` on my ports (section 9) and got the same facts.

## 1. Verdicts

| claim | verdict | regression? (vs 0.9.12 and 0.10.0a1) | my severity |
|---|---|---|---|
| **E-1** | **CONFIRMED** (three wording corrections, section 4) | **no**: 0.9.12 = a1 = a2 in every case. Context: *yes vs 0.8.x*, the behaviour appeared with the 0.9.0 event-processor rewrite (0.8.26 sends the delta in the same frame as the error toast) | medium |
| **E-2** | **NARROWED** (a) and (c) confirmed exactly; (b) confirmed but the divergence is only permanent if the superseding call does not rewrite the same var; applies to the *default* Redis config (oplock off); "data loss" is really browser/server divergence of per-session state | **no**: 0.9.12 = a1 = a2. (a) exists since 0.9.0, (c) since at least 0.8.26 (upstream #6122), (b) since `supersedes` exists (upstream #7248, fix PR #7412 still open) | medium for divergence, low as durable data loss |

Neither is an a2 regression; neither is a release blocker for the train. E-1 is a genuine, user-visible defect that no upstream
issue tracks yet (the equivalent background-task gap was fixed upstream in #6995 / #6982 with the rationale "the client gets the
same refresh regardless of how the task ended"). E-2's pieces are tracked upstream (#6122, #7248).

## 2. Method

* Fixture `app/evv/evv.py`: one root-level state `V` with `status`, `spinner`, `pings`, `log`, `other`, `load_note` (+ a backend var) and
  handlers that mutate then raise: `direct_raise` (sync), `async_raise`, `raise_clean` (control: raises without mutating),
  `backend_raise` (backend var), `chain_a` -> `chain_b` (A returns B, B raises), `gen_raise` / `agen_raise` (yield once, then raise),
  `spinner_finally` (the documented loading-flag pattern: `spinner="on"; yield; try: ...raise; finally: spinner="off"`),
  `caught` (control: exception handled), background tasks `bg_raise_inside` / `bg_two_blocks` / `bg_raise_after`, two
  `supersedes=True` handlers (`sup_same` rewrites the same list, `sup_split` leaves `log` untouched in the superseding call), and an
  `on_load` that raises (`/onload`, reached by initial load and by client navigation). `backend_exception_handler` is a custom
  function whose behaviour is switchable at runtime: default toast, `window_alert`, `None`, or `[toast, V.flush_noop]`.
* Driver `driver/drive_verify.py` (Playwright 1.63, Chromium 141, headless): **fresh browser context per case** (fresh client
  token), real mouse clicks, an in-page recorder (WebSocket send/recv with `performance.timeOrigin`-based epoch timestamps,
  click times, MutationObserver on every displayed var and on sonner toast nodes) **plus** Playwright's CDP frame capture as a
  second independent source (232 recorded cases: both sources agree on frame counts in every one, `out/crosscheck_frames.txt`),
  console/pageerror/requestfailed/4xx-5xx capture, screenshots.
* Checkpoints per case: `before`; **t1** = 3 s after the failing event, *no other event sent*; **t2** = after an unrelated `ping`
  click; **t3** = after a page reload of the same tab = what the server holds (hydrate returns the full state).
* Matrix (one server at a time, ports FE 3640 / BE 8640, prod single port 8641, redis 8659; server logs at `--loglevel debug`):
  0.10.0a2 dev {disk, memory, redis, redis+OPLOCK}, 0.10.0a2 prod {disk, redis 1 worker, redis 9 workers (default `2*cpu+1`)},
  0.10.0a1 dev {disk, redis}, 0.9.12 dev {disk, redis} and prod {disk, redis 1 worker} (7 key cases); extra history points 0.9.0 dev {disk, redis} and 0.8.26 dev {disk, redis}.
  The default case list (16 cases) was run on every a2/a1/0.9.12 combination; subsets on the others.
* Venvs: shared read-only `alpha2`, `alpha`, `stable`, `driver`; I created two more **from PyPI** (never from a checkout):
  `$SB/envs/verify_events_0-r0826` (`reflex==0.8.26`) and `$SB/envs/verify_events_0-r090` (`reflex==0.9.0` + `reflex-base==0.9.0`);
  both needed `greenlet` added by hand (N-001: SQLAlchemy 2.1 made it optional, `reflex.model` imports `sqlalchemy.ext.asyncio`).
  Every server asserts at import time that `reflex` comes from the expected venv (`EVV_VENV`), the driver asserts it runs in the
  `driver` venv, and every log starts with `EVV boot reflex==<ver> file=<path>`.

## 3. Headline numbers (ms after the click; `out/timings.md`, from in-page frames)

On every 0.9.0..0.10.0a2 run the toast frame arrives within 5-60 ms (about 300 ms for `spinner`, whose handler sleeps 0.3 s before raising), and the
frame that finally carries the mutated value arrives **only with the next event**, 10-12 ms after the unrelated `ping` click:

| run | case | toast frame | frame with the final value | ping click |
|---|---|---|---|---|
| 0.8.26 dev disk | direct | 15.2 | **15.2 (same frame as the toast)** | 3123 |
| 0.9.12 dev disk | direct | 13.3 | 3107.3 | 3095.6 |
| 0.10.0a1 dev disk | direct | 11.1 | 3106.1 | 3095.2 |
| 0.10.0a2 dev disk | direct | 5.6 | 3103.9 | 3092.1 |
| 0.10.0a2 prod disk | direct | 12.4 | 3136.8 | 3125.5 |
| 0.10.0a2 dev memory | direct | 10.3 | 3037.0 | 3026.5 |
| 0.10.0a2 dev disk, **no further event for 40 s** | direct | 13.6 | **40058.9** | 40048.9 |

(the full table, 5 cases x 7 runs, is `out/timings.md`). The error toast itself is never late; only the state is.

## 4. E-1 (disk / memory manager): what is confirmed, and three corrections

Confirmed on 0.10.0a2 dev/disk, dev/memory, prod/disk, and identically on 0.10.0a1 dev/disk and 0.9.12 dev/disk + prod/disk, for sync, async,
chained (A returns B, B raises), `yield` once then raise (sync and async generator) and the `finally`-reset pattern:

* the raising handler's delta is never sent with the error. The only frame after the click is the toast (`_call_function`);
* the mutation stays in the server's state object and arrives with the next event of any kind (a `ping` that touches an
  unrelated var carries `status` too: frame `{"status":"direct-partial","pings":1}`);
* a reload shows the mutated value (server truth), so browser and server disagree until the next event.

User-visible form (screenshot `out/alpha2_dev_disk/spinner_t1.png`): error toast on screen, page still says `spinner: on`
although the handler's `finally` set it to `off` on the server. On 0.8.26 the same click shows `off` immediately.

Corrections to the explorer's wording:

1. **"persisted" only means "retained in the running server's in-memory state object".** `probe_disk_write.py`: a successful control
   event reaches the `.pkl` files after the 2 s debounce; the failing event's mutation is **not** on disk 0.5 s, 4 s or 12 s later,
   and appears on disk only after the *next successful event* (here the reload's hydrate) does `set_state`
   (`out_extra/disk_write_alpha2_dev.json`). Also `reflex run` deletes `.states` at every start
   (`reflex/reflex.py:642`, `reset_disk_state_manager()`), so the disk manager gives no cross-restart durability for any event; my
   restart probe (`out_extra/restart_alpha2_dev_disk.json`) is therefore uninformative by design (even the control event is gone).
2. **The delay is unbounded, not "~3 s".** With no further event the stale value was still stale after 40 s
   (`out/alpha2_dev_disk_idle40`, server log `logs/alpha2_dev_disk_idle.log`, `backend_exception_handler mode=default`); engine.io
   keep-alives carry no state.
3. **`on_load` "delivers immediately" only because the framework chains `set_is_hydrated(True)` after it**, whose own delta flushes
   the dirty vars: frames on the initial load are `delta {is_hydrated:true, load_note:"load-partial"}` at +202.8 ms, then the toast
   at +204.0 ms (client navigation: +61.6 / +63.4 ms). It is the same mechanism, not a counterexample. Background tasks flush in
   `StateProxy.__aexit__` even when the body raised (`bg_inside`: delta +9.2 ms, toast +11.1 ms).

Other E-1 observations:

* **Handler variants behave identically** (`direct_alert`, `direct_none`, in `out/alpha2_dev_disk_run2`): `rx.toast` default, custom
  `window_alert` (dialog captured), and a custom handler returning `None` (the browser then receives **no frame at all** after the
  failing event, yet later events work) all leave the delta undelivered. A custom `backend_exception_handler` that returns
  `[default_toast, SomeState.noop_event]` delivers the delta ~9 ms after the toast (`direct_chain`, `gen_chain`, `spinner_chain`):
  a working user-side mitigation on disk/memory (not on Redis, section 5).
* Controls behave: `raise_clean` (nothing mutated) and `caught` (exception handled) show no anomaly; a second full run
  (`alpha2_dev_disk_run2`) reproduced run 1 case for case.
* Memory manager == disk manager (`alpha2_dev_memory`, 8 cases).
* No console errors/warnings except the known-benign prod `/favicon.ico` 404 (the console message's `location.url` is `/favicon.ico`, `driver/probe_404.py`);
  no page errors, failed requests or 5xx responses in 232 cases.

Compact matrix (cell = class of t1/t2/t3 against the 0.8.26 behaviour as the ideal; generated by `driver/make_table.py --compact`;
raw triples in `out/summary_table.md`). OK = delivered and persisted; STALE = delivered only with the next event;
DROPPED = never delivered and not persisted; DIVERGED = browser shows a value the server does not hold:


#### disk/memory

| case (primary var) | 0.8.26 dev disk | 0.9.0 dev disk | 0.9.12 dev disk | 0.10.0a1 dev disk | 0.10.0a2 dev disk | 0.10.0a2 dev disk (run 2) | 0.10.0a2 dev memory | 0.10.0a2 prod disk | 0.9.12 prod disk |
|---|---|---|---|---|---|---|---|---|---|
| direct (`status`) | OK | STALE | STALE | STALE | STALE | STALE | STALE | STALE | STALE |
| async (`status`) | OK | - | STALE | STALE | STALE | STALE | - | STALE | - |
| chain (`log`) | OK | STALE | STALE | STALE | STALE | STALE | STALE | STALE | STALE |
| gen (`status`) | OK | STALE | STALE | STALE | STALE | STALE | STALE | STALE | STALE |
| agen (`status`) | OK | - | STALE | STALE | STALE | STALE | - | STALE | - |
| spinner (`spinner`) | OK | STALE | STALE | STALE | STALE | STALE | STALE | STALE | STALE |
| bg_inside (`status`) | OK | OK | OK | OK | OK | OK | OK | OK | OK |
| bg_two (`status`) | OK | - | OK | OK | OK | OK | - | OK | - |
| onload_initial (`load_note`) | OK | OK | OK | OK | OK | OK | OK | OK | OK |
| sup_split (`log`) | - | - | `a:start,a:after-yield` | `a:start,a:after-yield` | `a:start,a:after-yield` | `a:start,a:after-yield` | `a:start,a:after-yield` | `a:start,a:after-yield` | `a:start,a:after-yield` |
| sup_same (`log`) | - | - | `a:start,a:after-yield,b:start,b:after-yield,b:end` | `a:start,a:after-yield,b:start,b:after-yield,b:end` | `a:start,a:after-yield,b:start,b:after-yield,b:end` | `a:start,a:after-yield,b:start,b:after-yield,b:end` | `a:start,a:after-yield,b:start,b:after-yield,b:end` | `a:start,a:after-yield,b:start,b:after-yield,b:end` | - |

#### redis

| case (primary var) | 0.8.26 dev redis | 0.9.0 dev redis | 0.9.12 dev redis | 0.10.0a1 dev redis | 0.10.0a2 dev redis | 0.10.0a2 prod redis (1 worker) | 0.10.0a2 prod redis (9 workers) | 0.9.12 prod redis (1 worker) | 0.10.0a2 dev redis + OPLOCK |
|---|---|---|---|---|---|---|---|---|---|
| direct (`status`) | OK | DROPPED | DROPPED | DROPPED | DROPPED | DROPPED | DROPPED | DROPPED | STALE |
| async (`status`) | OK | - | DROPPED | DROPPED | DROPPED | DROPPED | - | - | - |
| chain (`log`) | OK | - | DROPPED | DROPPED | DROPPED | DROPPED | - | DROPPED | STALE |
| gen (`status`) | OK | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | STALE |
| agen (`status`) | OK | - | DIVERGED | DIVERGED | DIVERGED | DIVERGED | - | - | - |
| spinner (`spinner`) | OK | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | STALE |
| bg_inside (`status`) | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | OK |
| bg_two (`status`) | DIVERGED | - | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | - | OK |
| onload_initial (`load_note`) | OK | - | DROPPED | DROPPED | DROPPED | DROPPED | - | DROPPED | OK |
| sup_split (`log`) | - | `a:start,a:after-yield,a:end` | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | `a:start,a:after-yield` |
| sup_same (`log`) | - | - | `b:start,b:after-yield,b:end` | `b:start,b:after-yield,b:end` | `b:start,b:after-yield,b:end` | `b:start,b:after-yield,b:end` | `b:start,b:after-yield,b:end` | - | `a:start,a:after-yield,b:start,b:after-yield,b:end` |

## 5. E-2 (Redis manager): confirmed pieces and the narrowing

Reproduced on 0.10.0a2 dev, **prod with 1 worker and with the default 9 workers** (the explorer had not covered Redis in prod),
and identically on 0.10.0a1 dev and 0.9.12 dev + prod (1 worker) (`/_health` shows `"redis":true`; `redis-cli --scan` shows the per-token keys):

* **(a) generator that yields, then raises**: `gen`: browser `gen-flushed` (delta +8.0 ms, toast +9.6 ms) at t1 *and* t2; reload (t3) `idle`.
  `agen` (async generator) likewise. Server never held the value the page shows.
* **(c) raise inside `async with self` in a background task**: `bg_inside`: browser `bg-inside-partial` (delta +8.8 ms, before the toast),
  reload `idle`. `bg_two` (two blocks, the second raises): browser `bg-block2-partial` + `log=bg-2`; reload `bg-block1-committed`, `log` empty:
  block 1 (exited normally) was persisted, block 2 (delivered, then raised) was not. `bg_after` (raise outside the block) is consistent.
* **(b) superseded handler**: `sup_split` (superseding call touches only `other`): browser `log=a:start` at t1 and t2, reload `log=""`
  (permanent until reload). **Narrowing:** in `sup_same` (the usual latest-wins shape, the superseding call rewrites the same
  list) the browser briefly shows `a:start`, then b's delta replaces the list: it converges to `b:start,b:after-yield,b:end`; a's entries
  are simply gone from server and client alike. Disk/memory instead keep `a:start,a:after-yield` (this is E-3, confirmed on all versions).
* **The stuck spinner is worse on Redis than on disk**: `spinner_finally` leaves `spinner=on` in the browser at t1, **still `on` at t2 after
  an unrelated ping**, and `off` only after a reload (server truth). On disk the ping repairs it.
  Screenshots: `out/alpha2_dev_redis/spinner_t2.png`, `spinner_t3.png`.

Narrowings:

1. **Non-yielding failures are consistent, not divergent.** `direct`, `async`, `chain` (B's part), `backend` var, and `on_load`: the changes
   are never delivered and never persisted (DROPPED): the failed event is atomic, client and server agree. Divergence appears only when a delta
   was already flushed before the failure (a `yield`, a finished `async with self` block, a cancelled handler that had yielded).
   So "discarded entirely" is accurate for the server, and the harm is *flush-then-rollback*.
2. **Only the default Redis configuration.** With `REFLEX_OPLOCK_ENABLED=true` (`alpha2_dev_redis_oplock`) the in-process cached state object is
   reused and written back at lease end, so Redis behaves like disk: E-1-style STALE results appear for `direct`/`chain`/`gen`/`spinner`, and
   `bg_inside`/`bg_two`/`sup_split` no longer diverge. The same app therefore gets different semantics from a single env var.
3. **No handler-level workaround exists for the flushed-then-failed cases on Redis**: the chain-a-flush-event custom handler (section 4) does not help
   (`gen_chain`: browser `gen-flushed`, reload `idle`; `spinner_chain`: browser `on`, reload `off`). Catching the exception inside the handler does.
4. **History (own PyPI venvs, `out/r0826_dev_*`, `out/r090_dev_*`)**: 0.8.26 + Redis: all foreground cases OK (delta delivered and persisted),
   but `bg_inside`/`bg_two` DIVERGED already (that is upstream #6122). 0.9.0 (first release containing `reflex_base/event/processor/`)
   + Redis already shows `gen`, `spinner` DIVERGED and `direct` DROPPED; 0.9.0 + disk already shows E-1. So foreground E-1/E-2(a) were
   introduced by the 0.9.0 event-processor rewrite.

## 6. Severity judgement

**E-1: medium, real and user-visible, not "expected".** After an error toast the page can show state the server no longer has, with no bound on
how long (40 s idle test), and the loading-flag idiom (`docs/events/yield_events.md`: `show_progress=True; yield; await ...; show_progress=False`; or its `try/finally`
variant, which the post-yield cleanup never delivers; the `try/except/finally` variant in `page_load_events.md` catches the error and is unaffected) leaves a spinner/disabled button up after the error. It silently commits a partial mutation on the server (disk/memory)
that the UI does not show, so a retry can duplicate it. It regressed vs 0.8.x, contradicts the docs' "StateUpdate for every yield / when the handler
finished" mental model, and the maintainers already treated the background-task twin as a bug (#6982 -> #6995). Mitigated in practice because any
later backend event flushes it; not a data-integrity problem.

**E-2: medium as UI/server divergence in production, low as "data loss".** Redis is the production manager, and the divergent patterns are ordinary
ones: loading flag then failure after a `yield`, background-task progress updates followed by a raise inside the block. What is lost is per-session
state, never database rows; but the page shows values the server does not have (a counter or list the user sees but a later handler will not),
and there is no client-visible signal and no recovery short of a reload. Single-shot handlers, which are most handlers, are atomic and consistent.
It is a known upstream design gap (#6122: "important to not have a behavior difference between memory/disk and redis state managers"; #7248).

Neither blocks 0.10.0a2 (identical on 0.9.12 and a1). Worth filing E-1 (new) and linking E-2 to #6122/#7248; note that PR #7412 explicitly keeps
"the existing write-discarding behavior for non-cancellation errors" (`test_modify_exception_does_not_persist_state`), so E-2(a)/(c) would stay.

## 7. Root cause (published 0.10.0a2 source under `$SB/envs/alpha2/lib/python3.12/site-packages`)

One mechanism produces both: **an exception thrown inside the state-manager context skips both the delta flush and the write-back.**

* `reflex_base/event/processor/base_state_processor.py:460` `async with ctx.state_manager.modify_state_with_links(...)`; `:509-515` the foreground
  `await process_event(...)` runs inside it. A raise leaves the `async with`.
* The only places that emit a delta are `chain_updates(..., root_state=...)` (`:231-243`: `if root_state is not None:` get delta, emit, `_clean()`),
  called after each `yield` and once at the normal end (`:330-363`). The raise path skips them.
* `event_processor.py:925-965` `_resolve_future` sees the failed task and spawns `_handle_backend_exception` in a **new task** after the lock is
  released; `base_state_processor.py:569-590` calls `chain_updates(events=events, handler_name=...)` **without `root_state`**, so only the toast event goes out.
* Disk/memory: `istate/manager/disk.py:446-447` (`yield state` then `set_state`) skips the write, but the cached object (`self.states[token]`)
  is the one already mutated and still *dirty*; `istate/manager/memory.py:209-261` shares the one object. The next event's `chain_updates`
  includes the stale dirty vars in its delta: E-1. (E-3 is the same thing for a cancelled handler.)
* Redis: `istate/manager/redis.py:535-537` (also `:569-570`, `:595-596`) `yield state` then `set_state(..., lock_id=...)`: skipped on any exception
  (cancellation included, upstream #7248); the state object is discarded and re-read from Redis next event, i.e. rolled back, while deltas already sent
  at yields (`chain_updates`) or at `StateProxy.__aexit__` (`istate/proxy.py:295-304`: delta emitted *before* `self._self_actx.__aexit__(*exc_info)`)
  are on the wire: E-2. With oplock the cached object survives (`redis.py:627+`, `do_flush` `:713-729`).
* Background tasks (E-1's "delivered immediately") flush in `StateProxy.__aexit__` (`proxy.py:281-306`) and, for tasks that never entered the
  context, in the `finally` at `base_state_processor.py:537-566` (the #6995 fix).

Fix directions (not implemented, for the maintainers): mirror #6995 in the foreground branch (flush the delta, then re-raise), and make the Redis manager
commit on exception like #7412 does for cancellation, or make failure semantics transactional by sending a corrective delta for rolled-back vars. Doing
only the first makes the Redis flush-then-rollback divergence *larger*.

## 8. Upstream context (GitHub, read-only)

* #6122 (open, maintainer): raise inside `async with self` under Redis loses the changes but the delta was sent; asks for uniform managers = E-2(c).
* #7248 (open) + PR #7412 (open): cancelled `supersedes=True` handler loses writes under Redis = E-2(b); PR keeps discarding on non-cancellation exceptions.
* #6982 / PR #6995 (merged 2026-09-02): background handler that raises got no delta; fixed with a `finally` flush = the E-1 twin for background tasks.
* No upstream issue found for the foreground E-1 behaviour.

## 9. The explorer's repro, run on my ports

The written repro (NOTES section "Issues" + `src/mini`, `drive_mini.py`) was sufficient: I ran their **unmodified** mini app and driver copies
(`bin/start_mini.sh`, `theirs_driver_on_my_ports/*.gz`) against 0.10.0a2 dev disk and dev Redis on ports 3640/8640. Identical conclusions:
disk `direct_raises`/`async_raises`/`gen_yield_then_raise`: the post-error partial values (`direct-partial`, `async-partial`, `items=gen-partial`; `status=gen-flushed` was yielded and is visible at once) are not visible with the error and are visible after the next event and after reload; `bg_*` and
`onload_*` pass; `sup_cancel`/`sup_split` leak `a:after-yield` (E-3). Redis: `gen_yield_then_raise` and `bg_raise_inside` `client_server_diverged: true`,
`sup_split` reload `log=""`, `direct_raises` never delivered or persisted, `onload` never delivered. Wording gaps in their NOTES are the three
corrections in section 4 and the narrowing in section 5 (the `sup_same` convergence, the oplock dependency, "persisted"). Their `bin/*.sh` use ports outside my range, hence my own scripts.

## 10. Rerun

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_events_0           # copy app/ driver/ bin/ from this directory to $W (run dirs are created under $W/run)
# ports: dev FE 3640 / BE 8640, prod single port 8641, redis 8659.  Never run python with a checkout as cwd.
bash $W/bin/redis.sh start                                          # redis-server --port 8659 --save '' --appendonly no
bash $W/bin/start.sh alpha2 dev disk && bash $W/bin/wait_up.sh dev   # venv: alpha2 | alpha | stable ; mode: dev | prod ; sm: disk | memory | redis
cd $W/driver && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python -I drive_verify.py --base http://localhost:3640 --label alpha2_dev_disk --out $W/out/alpha2_dev_disk
$SB/envs/driver/bin/python -I analyze.py $W/out/alpha2_dev_disk/alpha2_dev_disk_report.json            # timelines
bash $W/bin/stop.sh alpha2_dev_disk
bash $W/bin/redis.sh flush; bash $W/bin/start.sh alpha2 dev redis && bash $W/bin/wait_up.sh dev      # E-2 (`/_health` -> "redis":true)
#   ... same driver with --label alpha2_dev_redis; extra env is appended: `start.sh alpha2 dev redis REFLEX_OPLOCK_ENABLED=true`
#   prod: `start.sh alpha2 prod redis GRANIAN_WORKERS=1` (omit it for the default 9 workers), driver --base http://localhost:8641
#   cases: --cases direct,async,clean,backend,chain,gen,agen,spinner,caught,bg_inside,bg_two,bg_after,sup_same,sup_split,onload_initial,onload_nav,
#          idle40,direct_alert,direct_none,direct_chain,gen_chain,spinner_chain      (add --set-mode to always reset the handler mode)
$SB/envs/driver/bin/python -I make_table.py $W/out --compact ; $SB/envs/driver/bin/python -I make_timings.py $W/out ; $SB/envs/driver/bin/python -I crosscheck_frames.py $W/out/*/*_report.json
$SB/envs/driver/bin/python -I probe_disk_write.py alpha2 dev                                           # disk durability probe (server must be running, disk)
bash $W/bin/redis.sh stop
```
By hand (no driver): `start.sh alpha2 dev disk`, open http://localhost:3640/, click **direct raise**: toast appears, `status` stays `idle`; click **ping**: `status`
becomes `direct-partial`. Click **spinner finally**: toast, `spinner` stays `on`. With `start.sh alpha2 dev redis`, click **gen yield+raise**: `status` shows
`gen-flushed`; reload: `idle`. Standalone handlers (the whole repro is these three, plus `ping` and text vars `status`/`spinner`):

```python
class S(rx.State):
    status: str = "idle"; spinner: str = "off"
    @rx.event
    def direct_raise(self): self.status = "direct-partial"; raise RuntimeError("boom")          # E-1 (disk/memory), dropped on redis
    @rx.event
    async def spinner_finally(self):                                                              # stuck spinner: stale (disk), stuck until reload (redis)
        self.spinner = "on"; yield
        try: await asyncio.sleep(0.3); raise RuntimeError("boom")
        finally: self.spinner = "off"
    @rx.event
    def gen_raise(self): self.status = "gen-flushed"; yield; self.status = "gen-after"; raise RuntimeError("boom")   # E-2(a)
```

## 11. Files

`app/` fixture; `driver/drive_verify.py` (case driver), `analyze.py` (timelines), `make_table.py`, `make_timings.py`, `crosscheck_frames.py`, `probe_disk_write.py`,
`drive_restart.py` (restart probe, see section 4 point 1), `bin/` server/redis lifecycle and copy scripts; `out/<label>/` per run: `<label>_report.json.gz`
(timeline + CDP frames + snapshots), `<label>.analysis.txt` (human-readable), `*_rows.json.gz` (raw in-page rows, headline runs only), a few screenshots;
`out/summary_table.md`, `out/summary_compact.md`, `out/timings.md`, `out/crosscheck_frames.txt`; `logs/<label>.log.gz` (full server logs) and
`logs/<label>.interesting.txt` (`EVV` markers + backend exception lines); `out_extra/` (probes); `theirs_driver_on_my_ports/` (explorer's driver on my ports).
Run labels: `<venv>_<dev|prod>_<disk|memory|redis>[_suffix]`; `r0826_*` = reflex 0.8.26, `r090_*` = 0.9.0; `alpha2_dev_disk_x` = idle40 + handler variants (run 1);
`alpha2_dev_disk_run2` = full repeat; `alpha2_dev_disk_idle40` = the clean 40 s idle test (verified `mode=default`); `stable_dev_disk_rerun_sup` = rerun of two cases.

## 12. Caveats / not covered

* The server log of run 1 (`alpha2_dev_disk`) was overwritten by later restarts under the same label; `alpha2_dev_disk_run2` is a full repeat with its log. A first
  idle test inside run 2 was discarded: the handler mode is a process-global switch and the `chain` variant cases had leaked into it (the
  server logs prove which mode each failure ran under: every default-mode case logged `mode=default`); the clean idle test was repeated on a fresh server.
* The first 0.9.12 `sup_same` run hit a scheduling hiccup (the superseded call never reached its post-yield code, `a` started 2 ms before `b`); the rerun
  (`stable_dev_disk_rerun_sup`) matches a2; `out/summary_table.md` uses the rerun.
* Not run: prod mode on 0.10.0a1 (0.9.12 prod and 0.10.0a2 prod are identical; the failure is backend-side), the memory manager in prod, Redis cluster/sentinel,
  multi-process contention on one token, websocket-drop mid-event. The 0.8.26 / 0.9.0 venvs are single data points for history, with greenlet added by hand.
* `--loglevel debug` was on for all servers; machine shared with other agents (4 CPUs), only one reflex server (or redis) of mine ran at a time.
