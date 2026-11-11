CLUSTER: events_await
SUMMARY: Awaitable handlers (#7673), middleware on awaited handlers (#7782) and the failed/cancelled-handler fixes (#7696, #7412, #7738) behave as the changelog says in Chromium across dev and prod, memory and Redis (64 await scenarios identical in all four combinations bar one; every 0.10.1 control for the failure paths reproduced and is fixed). Two regressions need a decision before the final: any second `@rx.event` on a handler (five stacking patterns, including the one in reflex-examples `overkey`) now crashes the app at import, and pyright on Python 3.11-3.13 no longer sees the argument types of any bare-`@rx.event` handler. Three smaller defects in the new await feature and two low-severity decorator items are listed below. All servers and Redis are stopped.
ARTIFACTS: /home/user/reflex/prerelease-testing/runs/2026-11-11-v0.11.0a1/events_await/
TESTS:
- [pass] await matrix, 0.11.0a1 dev+memory / prod+memory / dev+Redis / prod+Redis: 51 single-click cases + 13 multi-step scenarios (sibling, substate, parent via three spellings, unrelated state both ways, mixin, ComponentState, sync/async generators, returned events, raising handlers, recursion, event actions, gather / ensure_future / wait_for, argument conversion, background inside and outside `async with self`, upload, on_load). Same visible outcome in all four; a `ping` after every case returns in 40-70 ms; no console errors or failed requests besides the prod favicon 404. `evidence/await_matrix_*.txt`
- [pass] await semantics as documented: sync generator's `return` value is the await result, async generator gives None, yields send one delta each; returned events chain after the caller and the await gives None; frontend-only events, upload specs and (under the lock) background handlers raise a clear `EventHandlerTypeError`
- [pass] exception from an awaited handler: propagates to the caller; uncaught, both handlers' writes reach the page at once and are persisted (memory and Redis)
- [pass] recursion: `fact(10)` = 3628800; unbounded self-await raises a catchable `RecursionError` at depth ~319, state stays usable
- [pass] middleware (#7782): awaited event reaches `preprocess` with the right name, payload and router_data; a blocked handler does not run and the await returns None (foreground, background in and out of the lock, `app.modify_state`); payload rewritten by a middleware applies to the awaited handler; a raising middleware propagates into the awaiter
- [pass] upload gated by middleware: blocked on 0.11.0a1 and on 0.10.1 alike (the planning note's "behaviour change for uploads" is not confirmed)
- [pass] #7696 / #7412: `a=1; yield; b=2; raise`, raise without a yield, write to another state then raise, `supersedes=True` handler cancelled after its last yield — writes reach the page in ~33 ms / at cancel time and the server keeps them on Redis (dev and prod). `evidence/failure_paths_summary.txt`
- [pass] #7738: background task whose `async with linked` fails or is superseded while loading the linked state — next event in 0.05 s (0.10.1: never on memory, 7.5-10 s on Redis). Uses a `get_state` override as the slow/failing store
- [pass] shutdown after every scenario set: SIGINT to the group ends in 1.5-2.6 s, including prod + Redis
- [pass] lock hygiene around awaits (`scripts/drive_locks.py`, dev+memory and prod+Redis): gather with one failing handler, `ensure_future` then raise, handler or background task superseded while awaiting inline, `wait_for` timeout under the lock, page reload during an awaited 2 s handler — no stuck lock
- [pass] #7673 bugfix (proxied dict then proxied list as handler arguments): works; control on 0.10.1 raises `EventHandlerTypeError ... Got MutableProxy`
- [pass] single decorator above `@rx.event` (functools.wraps logging decorator; sync, async, generator, with args): still runs, event name unchanged, one import-time and one call-time warning per wrapper, not per call
- [pass] module-level functions (#7770): plain helper stays a function and warns; `state: S` and `state: "S"` register as before; `deprecation_version` is "0.11.0" in the shipped wheel; no leftover "stateless" text in CHANGELOG or docs. `evidence/module_level_*.txt`
- [pass] mypy 2.4.1 on a typed user module: 35 errors on 0.10.1, 4 on 0.11.0a1 (#7715, #7752, #7754, #7755 confirmed). `typing/out_*.txt`
- [fail] double `@rx.event` stacking: class creation fails for 5 patterns on 0.11.0a1, all work on 0.10.1; reflex-examples `overkey` no longer imports. `evidence/deco_matrix_*.txt`, `evidence/overkey_import.txt`
- [fail] pyright 1.1.414 / 1.1.411, Python 3.12: bare `@rx.event` handlers are `EventCallback[*tuple[Unknown, ...]]`; strict mode goes from 4 to 18 errors on an unchanged app. `typing/out_reveal2_*.txt`, `typing/out_strict_*.txt`
- [fail] `await State.handler()` in an API route outside `app.modify_state` runs on a shared empty-token session instead of raising
- [anomaly] returning a non-event value from a clicked handler is now silent (0.10.1 raised a TypeError naming the fix)
- [anomaly] memory manager: background task awaiting a `supersedes=True` handler gets `CancelledError` for a run that finished; Redis returns the value. `evidence/supersedes_bg_await_trace.txt`
- [anomaly] background task that catches an awaited handler's exception still triggers the backend exception handler (error toast + log); the foreground inline await does not
- [anomaly] `@staticmethod` above `@rx.event` silently returns an `EventSpec` instead of the result (0.10.1 returned the result), no warning
- [anomaly] "Decorators above @rx.event" names only the first of several stacked methods in a class (deduped on the class line)
- [anomaly] `await self.handler()` on a sync handler runs the handler and then raises `TypeError: object int can't be used in 'await' expression`; `asyncio.create_task(State.h())` raises `a coroutine was expected` (only `ensure_future` works)
- [anomaly] prod hard load: `self.router.url.path` is `/onload/`, dev and client navigation give `/onload` (not baselined on 0.10.1)
- [skipped] `ty`; Python 3.11 / 3.13 / 3.14 runtimes; enterprise AuthMiddleware with awaited handlers
REVERIFIED:
- EVT-15 (reflex#7476): fixed — mutate-then-raise delta arrives at ~33 ms on 0.11.0a1; 0.10.1 control delivers it only with the next event (1567 ms)
- EVT-08 (reflex#7248): fixed — Redis, superseded handler: count=2, partial=[a,b] on 0.11.0a1; 0.10.1 control count=1, partial=[b]
- EVT-16 (comment on reflex#6122): fixed — Redis server view equals the page after a failed or superseded event; 0.10.1 control shows page a=1 vs server a=0
- EVT-17 (reflex#6122): changed — a superseded handler's writes after its last yield are now flushed in their own delta at cancel time (1548 ms), just before the superseding run's first delta (1549 ms)
- EVT-13: changed — fully applied 5-8 argument calls type-check under mypy and under pyright with Python 3.14 semantics; a 9-argument call still has no overload; on Python 3.11-3.13 pyright sees Unknown (issue 2); `ty` not run
ISSUES:
- TITLE: A second `@rx.event` on a handler crashes the app at import (five stacking patterns; breaks reflex-examples `overkey`)
  SEVERITY: high
  REGRESSION: yes
  REPRO: cd $SB && EXPECT_VENV=$SB/envs/new $SB/envs/new/bin/python -I apps/events_await/probes/deco_matrix.py (same with envs/prev: all 18 patterns create the class). Real app: cp -r $SB/downloads/reflex-examples/overkey /tmp/x && cd /tmp/x && $SB/envs/new/bin/python -c "import overkey.overkey". Minimal: a state with `@rx.event` directly above `@rx.event(background=True)` on an async method.
  EVIDENCE: `@rx.event`/`@rx.event`, `@rx.event`/`@rx.event(background=True)` (overkey/overkey.py:164), `@rx.event`/`@rx.event(throttle=300)` -> `AttributeError: 'EventHandler' object has no attribute '__qualname__'` at reflex_base/utils/format.py:448 during state registration; `@rx.event(background=True)`/`@rx.event` -> `TypeError: Background task must be async function or generator.`; `@rx.event(throttle=300)`/`@rx.event` -> `FrozenInstanceError: cannot assign to field '_rx_event_actions'`. The changelog promises such a method "still runs and registers under its own name, with a deprecation warning, until 1.0". evidence/deco_matrix_new.txt, evidence/deco_matrix_prev.txt, evidence/overkey_import.txt
- TITLE: pyright loses the argument types of every bare-`@rx.event` handler on Python 3.11-3.13
  SEVERITY: medium
  REGRESSION: yes
  REPRO: cd $SB/apps/events_await/typing && ./run_typing.sh new reveal2.py && ./run_typing.sh prev reveal2.py; ./run_typing.sh new strict_app.py vs prev. (Venvs: frozen copies of envs/new and envs/prev plus pyright 1.1.414 and mypy 2.4.1, Python 3.12; build line in NOTES.md.)
  EVIDENCE: 0.10.1: `S.via_rx` is `EventCallback[int]`; wrong-type call, too many arguments and an int handler on `on_change` are errors. 0.11.0a1: `EventCallback[*tuple[Unknown, ...]]`, `S.via_rx(1)` is `Unknown`, `self.via_rx` is `(*Unknown) -> Any`, none of the three mistakes reported; `# pyright: strict` on an unchanged app goes from 4 to 18 errors. `@rx.event()` with parentheses is unaffected; mypy is correct; `pyright --pythonversion 3.14` is correct, which is why the tag's own tests/type_checking/event.py passes in CI but gives 15 (pyright 1.1.411) / 24 (1.1.414) errors against the installed wheel on 3.12. Cause confirmed on a scratch copy: `EventCallback: TypeAlias = EventCallback` inside `class EventNamespace` (reflex_base/event/__init__.py:3502, from #7715) shadows the name in the `__new__` overload's return annotation; removing that line restores `EventCallback[int]`. typing/out_reveal2_new.txt, typing/out_strict_new.txt
- TITLE: `await State.handler()` in an API route outside `app.modify_state` does not raise; it runs on one shared session whose token is the empty string
  SEVERITY: medium
  REGRESSION: no
  REPRO: scripts/srv.sh start new $SB/apps/events_await/awaitapp dev 3180 8180 t; for i in 1 2 3; do curl -s --noproxy '*' localhost:8180/poke/any-$i; done (route `poke` in awaitapp/awaitapp/awaitapp.py: `res["outside"] = await Main.add(1)` after the modify_state block). Browser variant: scripts/drive_poke.py http://localhost:3180 http://localhost:8180
  EVIDENCE: "outside" returns 1, 2, 3, 4 on successive requests with different tokens (and across workers in prod + Redis). Server log: `Warning: Attempting to send delta to disconnected client ''`. Redis keys `_reflex___state____state` and `_reflex___state____state.awaitapp___awaitapp____main`. docs/events/chaining_events.md: "Only inside an event handler (or `app.modify_state`); awaiting a handler anywhere else raises an error."
- TITLE: A clicked handler that returns a non-event value is now silently accepted; `return self.other_handler` and `return rx.redirect` lose their explanatory TypeError
  SEVERITY: low
  REGRESSION: yes
  REPRO: legacyapp `/fail`, buttons ret_value (`return self.a`), ret_garbage (`return rx.redirect`), ret_self_handler (`return self.chained`): scripts/drive_legacy.py http://localhost:3184 logs/<tag>.log out/x.json fail on envs/new and envs/prev
  EVIDENCE: 0.10.1 log: `TypeError: Your handler F.ret_self_handler must only return/yield: None, Events or other EventHandlers referenced by their class (i.e. using type(self) or other class references). Returned events of types <class 'method'>`. 0.11.0a1: no log line, no toast, `chained` never runs (b stays 0). evidence/failure_paths_summary.txt
- TITLE: Memory state manager: a background task awaiting a `supersedes=True` handler gets `CancelledError` although that run completed
  SEVERITY: low
  REGRESSION: no
  REPRO: awaitapp, click "c_bg_supersedes a" then "c_bg_supersedes b" 150 ms apart (driver: scripts/drive_await.py <url> <log> out.json special, scenario sup_bg_await_x2), memory manager, dev or prod
  EVIDENCE: TRACE lines: `search(bgfirst) start` ... `search(bgfirst) end` at 493.208, `c_bg_supersedes(bgsecond) task started` at 493.208, `search(bgsecond) start` at 493.209; page history `c_bg_supersedes: bgfirst -> CancelledError` then `bgsecond -> BGSECOND`. With Redis the first task gets `BGFIRST`. 4/4 memory runs (dev and prod), 0/2 Redis runs. evidence/supersedes_bg_await_trace.txt
- TITLE: `@staticmethod` above `@rx.event` now returns an `EventSpec` instead of calling the function, with no warning
  SEVERITY: low
  REGRESSION: yes
  REPRO: legacyapp import results (`D.static_over(3)`, `Helper.static_over_event(3)`), shown on the `/` page and in evidence/deco_page_new_vs_prev.txt
  EVIDENCE: 0.10.1: `6`. 0.11.0a1: `EventSpec(event_actions={}, handler=EventHandler(... fn=<function D.static_over ...>), ...)`. The changelog covers only `@rx.event` above `@staticmethod` (warns, unchanged).
- TITLE: "Decorators above @rx.event" deprecation names only the first stacked method of a class
  SEVERITY: low
  REGRESSION: no
  REPRO: legacyapp: `class D` has four methods with `@logged` above `@rx.event` (above, above_args, above_async, above_gen); start `reflex run` and read the log
  EVIDENCE: one line: "Decorators above @rx.event has been deprecated in version 0.11.0. `above` is decorated above @rx.event ... (legacyapp/legacyapp.py:77)" — the dedupe key is the feature name plus the `class D` line, so the other three surface one per fix-and-restart.
- TITLE: A background task that catches an awaited handler's exception still shows the app error toast
  SEVERITY: low
  REGRESSION: no
  REPRO: awaitapp button c_bg_boom (`try: await Main.boom(1000) except Exception` outside `async with self`); compare c_boom_caught (foreground)
  EVIDENCE: result `c_bg_boom: ValueError: boom total=1000` and toast "An error occurred. ValueError: boom" plus `[Reflex Backend Exception]` in the log; c_boom_caught shows no toast. evidence/await_matrix_new_dev_mem.txt
NOT_COVERED: `ty` (not installed; EVT-13's ty half is open); Python 3.11 / 3.13 / 3.14 runtimes (everything ran on 3.12; the pyright version dependence was checked with `--pythonversion`); reflex-enterprise AuthMiddleware with awaited handlers (enterprise cluster); SharedState / linked states and multi-tab with await; chunked upload handlers; a genuine store failure for #7738 (a `get_state` override stands in for a slow or failing load); client disconnect mid-await other than a page reload; the prod trailing-slash `router.url.path` was not baselined on 0.10.1.
