# events_await cluster — reflex 0.11.0a1 (#7673 / #7770 / #7782 / #7715 / #7752 / #7755 / #7754 / #7696 / #7412 / #7738)

## Status / resume here
- [x] awaitapp (await matrix + middleware + upload + on_load) written; dev + memory run done (`out/new_dev_mem.json`)
- [x] awaitapp prod + memory, dev + redis, prod + redis (identical to dev + memory except `sup_bg_await_x2`, see anomalies)
- [x] legacyapp (decorator stacking + failure paths) on 0.11.0a1 (dev mem, dev redis, prod redis) and 0.10.1 (dev mem, dev redis)
- [x] `probes/deco_matrix.py` on both versions; reflex-examples `overkey` import on both versions
- [x] typing module (pyright 1.1.414 + 1.1.411, mypy 2.4.1; 0.11.0a1 vs 0.10.1) — `typing/`
- [x] out-of-band `app.modify_state` + await (`scripts/drive_poke.py`), lock hygiene (`scripts/drive_locks.py`), module-level functions (`probes/module_level.py`), proxied-arg fix control (`probes/proxied_args.py`), hot-reload warning count
- [x] report written to `../reports/events_await.md`
- All servers and Redis (8199) stopped. Nothing left to resume; open follow-ups are listed under "Not covered".

All paths below are relative to `$SB/apps/events_await/` (scratch) = this directory (repo copy).
`$SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`. Ports: fe 3180-3199, be 8180-8199, redis 8199.

## How to rerun
```
scripts/srv.sh start new  $SB/apps/events_await/awaitapp dev  3180 8180 new_dev_mem          # dev, memory
scripts/srv.sh start new  $SB/apps/events_await/awaitapp prod 3181 3181 new_prod_mem         # prod, memory
scripts/srv.sh redis-start; scripts/srv.sh start new .../awaitapp dev 3182 8182 new_dev_redis redis
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/drive_await.py http://localhost:3180/ logs/new_dev_mem.log out/new_dev_mem.json [case ...|special]
scripts/srv.sh stop new_dev_mem
```
`srv.sh` starts `reflex run` under `setsid`, waits for 200, and `stop` sends SIGINT to the group and reports how long shutdown took.

legacyapp (runs on both versions; `legacyapp_prev/` is a byte-identical copy initialised with the 0.10.1 venv so the two `.web` dirs do not fight):
```
scripts/srv.sh start new  $SB/apps/events_await/legacyapp      dev 3184 8184 leg_new_dev_mem [redis]
scripts/srv.sh start prev $SB/apps/events_await/legacyapp_prev dev 3185 8185 leg_prev_dev_mem [redis]
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/drive_legacy.py http://localhost:3184 logs/leg_new_dev_mem.log out/leg_new_dev_mem.json [deco] [fail]
$SB/envs/driver/bin/python scripts/summ_legacy.py out/leg_new_dev_redis.json out/leg_prev_dev_redis.json
cd $SB && EXPECT_VENV=$SB/envs/new $SB/envs/new/bin/python -I apps/events_await/probes/deco_matrix.py    # and envs/prev
```

Setup from this directory's copy (the scratch dirs are gone after the session):
```
mkdir -p $SB/apps/events_await && cp -r awaitapp legacyapp scripts probes typing $SB/apps/events_await/ && cd $SB/apps/events_await
cp -r legacyapp legacyapp_prev
(cd awaitapp && REFLEX_TELEMETRY_ENABLED=false $SB/envs/new/bin/reflex init)
(cd legacyapp && REFLEX_TELEMETRY_ENABLED=false $SB/envs/new/bin/reflex init)
(cd legacyapp_prev && REFLEX_TELEMETRY_ENABLED=false $SB/envs/prev/bin/reflex init)
# reflex-examples overkey (FINDING A on a real app):
cp -r $SB/downloads/reflex-examples/overkey overkey_copy && cd overkey_copy && $SB/envs/new/bin/python -c "import overkey.overkey"   # and envs/prev
# more probes (neutral cwd = $SB):
EXPECT_VENV=$SB/envs/new $SB/envs/new/bin/python -I apps/events_await/probes/module_level.py
EXPECT_VENV=$SB/envs/prev $SB/envs/prev/bin/python -I apps/events_await/probes/proxied_args.py
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/drive_poke.py http://localhost:3180 http://localhost:8180    # awaitapp running; prod: same port twice
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/drive_locks.py http://localhost:3180 logs/new_dev_mem.log out/locks.json
```
`srv.sh` hard-codes `$SB/apps/events_await` for logs (`logs/<tag>.log`, `logs/<tag>.mw.jsonl`).

## Results

### FINDING A (HIGH, regression): any second `@rx.event` on a handler crashes the app at import
`probes/deco_matrix.py` (`out/deco_matrix_{prev,new}.txt`): on 0.10.1 all 18 patterns create the class. On 0.11.0a1:
| pattern (top / bottom) | 0.11.0a1 |
|---|---|
| `@rx.event` / `@rx.event` | `AttributeError: 'EventHandler' object has no attribute '__qualname__'` (state registration, `reflex_base/utils/format.py:448`) |
| `@rx.event` / `@rx.event(background=True)` (reflex-examples `overkey/overkey.py:164`) | same AttributeError |
| `@rx.event` / `@rx.event(throttle=300)` | same AttributeError |
| `@rx.event(background=True)` / `@rx.event` | `TypeError: Background task must be async function or generator.` |
| `@rx.event(throttle=300)` / `@rx.event` | `FrozenInstanceError: cannot assign to field '_rx_event_actions'` |
Real app: `overkey_copy/` (copy of reflex-examples `overkey` @ ebe19ff) — `python -c "import overkey.overkey"` imports on 0.10.1 (`tick` is background),
raises the AttributeError on 0.11.0a1. The changelog promises "A decorator stacked above `@rx.event` is deprecated: the method still runs and
registers under its own name, with a deprecation warning, until 1.0".
Cause (read from the installed wheel): `EventNamespace.__new__.wrapper` wraps whatever it is given in `EventHandler(fn=func)`; when `func` is already an
`EventHandler`, `BaseState._item_is_event_handler` skips it (`isinstance(value, EventHandler)`), and `format_event_handler` then reads `handler.fn.__qualname__`.

### Decorator stacking, other patterns (legacyapp `/`, both versions)
- `@logged` (functools.wraps) above `@rx.event`, sync / async / generator / with args: all still run on 0.11.0a1, event name unchanged (`...d.above`), state updated.
  One import-time `DeprecationWarning: Decorators above @rx.event ... \`above\` is decorated above @rx.event` and one call-time
  `Calling an event handler with a state instance ... \`D.above\`` per wrapper function, not per call (3 more clicks: no new log lines).
  LOW: the import-time warning is deduped on feature name + the `class D` line, so only the FIRST of 4 stacked methods is named; a user fixes one per run.
- `@staticmethod` above `@rx.event` (`D.static_over`, `Helper.static_over_event`): 0.10.1 returns `x * 2`; 0.11.0a1 silently returns an `EventSpec`, no warning
  (the changelog only covers `@rx.event` above `@staticmethod`, which warns and keeps working).
- `Helper.compute(Helper(), 3)` on a non-state class: 0.10.1 -> 9; 0.11.0a1 -> `EventHandlerTypeError: Arguments to event handlers must be Vars or JSON-serializable` (documented as unsupported).
- plain-python mixin method with `@rx.event` used as `on_click=D.mix_plain`: broken on both (0.10.1: `TypeError: super(type, obj)` at compile; 0.11.0a1: compiles,
  click logs `KeyError: 'No registered handler found for event: PlainMixin.mix_plain'`, nothing in the UI).
- module-level `@rx.event def helper_fn(x: int)`: stays a plain function on both, 0.11.0a1 warns once. Decentralized handlers (`state: D` and `state: "D"`) work on both.

### Failure paths (#7696 / #7412 / #7738) — legacyapp `/fail`, `scripts/summ_legacy.py`
| scenario | 0.10.1 memory | 0.10.1 redis | 0.11.0a1 memory | 0.11.0a1 redis (dev and prod) |
|---|---|---|---|---|
| `a=1; yield; b=2; raise` | b reaches the page only with the next event (1567 ms) | server rolled back to a=0 b=0 while the page shows a=1 | b=2 and its computed var at ~33 ms | same, server a=1 b=2 |
| `c=3; raise` (no yield) | with next event | lost | immediately | immediately, persisted |
| write to another state, raise | with next event | lost | immediately | immediately, persisted |
| `supersedes=True` handler cancelled after its last yield | writes kept | count=1, partial=[b] (first run's writes lost) | writes at cancel time | count=2, partial=[a,b], sent at cancel (1550 ms) |
| bg task: `async with linked` fails while loading | every later event hangs (no reply in 20 s) | 9 s (lock expiry) | 0.05 s | 0.05 s |
| bg task superseded while loading | hangs | 7.5 s / 10 s | 0.06 s | 0.05 s |
`srv.sh stop` after these scenarios: 1.5-2.6 s on every 0.11.0a1 run (no shutdown hang).
The bg scenarios use a test hook (`F.get_state` overridden with `_override_base_method`) to make loading `Other` slow or failing after the parent took the lock.

### Handler return values from the frontend (new in #7673)
`return self.a` (int), `return rx.redirect` (forgot the call) and `return self.chained` (bound method — the documented pitfall) raised
`TypeError: Your handler F.ret_value must only return/yield: None, Events or other EventHandlers referenced by their class...` on 0.10.1.
On 0.11.0a1 all three are silently accepted as "the handler's result": no log line, no toast, the event the user meant to chain never runs.

### Typing (#7715 / #7752 / #7755 / #7754) — `typing/run_typing.sh <new|prev> [file]`
Own venvs `$SB/envs/events_await-typing-{new,prev}` = frozen copies of the shared `new` / `prev` graphs + pyright 1.1.414 + mypy 2.4.1, Python 3.12
(`cd $SB && uv --no-config pip freeze --python envs/new/bin/python > f.txt && uv --no-config pip install --python envs/events_await-typing-new/bin/python --only-binary :all: -r f.txt pyright mypy`).
`typed_app.py` (a typed user module: handlers with 0-9 args, awaits, a dataclass holding a handler, `FunctionStringVar.create(_var_type=EventChain)`):
| checker | 0.10.1 | 0.11.0a1 |
|---|---|---|
| mypy 2.4.1 | 35 errors (`"EventNamespace" not callable` on every handler use) | 4 errors |
| pyright 1.1.414 | 16 errors | 3 errors |
#7715, #7752 (5-8 values), #7754 confirmed under mypy; #7755 confirmed (reading `holder.on_submit` gives `EventHandler` under both).
Left on 0.11.0a1 (`typing/out_new.txt`): `S.no_args` is not assignable to an `EventHandler`-typed field/parameter (both checkers, same on 0.10.1);
`spec: EventSpec = S.one(1)` fails under mypy only (`EventCallback[()]` vs `EventSpec`); a fully applied 9-argument call has no overload (both).

### FINDING B (MEDIUM, regression): pyright loses every bare-`@rx.event` handler's argument types on Python 3.11-3.13
`typing/reveal2.py`, `typing/strict_app.py`; outputs `typing/out_reveal2_{new,prev}.txt`, `typing/out_strict_{new,prev}.txt`.
- 0.10.1, pyright 1.1.414, Python 3.12: `S.via_rx` is `EventCallback[int]`; `S.via_rx("not an int")`, `S.via_rx(1, 2, 3)` and
  `rx.input(on_change=S.via_rx)` (int handler on a str trigger) are errors.
- 0.11.0a1, same checker: `S.via_rx` is `EventCallback[*tuple[Unknown, ...]]`, `S.via_rx(1)` is `Unknown`, `self.via_rx` is `(*Unknown) -> Any`; none of the
  three mistakes is reported. `@rx.event()` (with parentheses) and `@rx.event(throttle=...)` keep `EventCallback[int]`. mypy is correct.
- `# pyright: strict` on a plain 0.10-style app (`strict_app.py`): 4 errors on 0.10.1, 18 on 0.11.0a1 (14 new `reportUnknownMemberType` /
  `reportUnknownArgumentType` / `reportUnknownVariableType` on every handler reference).
- Version dependent: `pyright --pythonversion 3.14` gives `EventCallback[int]` again (and 4 strict errors); 3.11, 3.12, 3.13 give Unknown. pyright 1.1.411
  (the version in the tag's `uv.lock`) behaves the same. The tag's own `tests/type_checking/event.py` (`typing/upstream_event_test.py`) run against the
  installed wheel on Python 3.12: 15 errors with pyright 1.1.411, 24 with 1.1.414.
- Cause, confirmed on a scratch copy of `reflex_base` put first on `extraPaths`: `EventNamespace` now declares `EventCallback: TypeAlias = EventCallback`
  (`reflex_base/event/__init__.py:3502`, from #7715). Inside the class body that name shadows the module-level class in the `__new__` overload's return
  annotation `-> EventCallback[*P]`; pyright resolves it to Unknown unless annotations are deferred (3.14). Commenting out that one line restores
  `EventCallback[int]` on 3.12. (`EventDecorator`, used by `@rx.event()`, lives at module scope, which is why the parenthesised form is unaffected.)

### Await matrix (#7673 / #7782) — awaitapp, `scripts/drive_await.py` (52 single-click cases + 14 multi-step "special" scenarios)
Run on 0.11.0a1 in dev+memory, prod+memory, dev+Redis, prod+Redis (8 granian workers): identical visible outcome in all four except one scenario
(`sup_bg_await_x2`, FINDING E). `evidence/await_matrix_*.txt`, `evidence/await_matrix_cmp.txt`. Every case is followed by a `ping` round trip
(40-70 ms everywhere: no case leaves the state locked). No browser console errors or failed requests other than the favicon 404 in prod.
| case | observed |
|---|---|
| sibling (`add_twice`, the docs example) | `5 then 10`, toast shown |
| substate handler `await Sub.bump(2)` | returns 2, then 5; `Sub.n` updates in the page |
| parent handler from a substate: `await Main.add(3)`, `await type(self).add(3)`, `await Sub.add(3)` | 3, 6, 9 — all three spellings run the parent's handler |
| unrelated state: `await Other.record("x")`, and `Other` awaiting `Main.add` | works both ways, both states' deltas reach the page; `self.router.url.path` is right inside the awaited handler |
| mixin handler, ComponentState handler, zero-arg `await Main.no_args` (no call) | work; two ComponentState instances stay independent |
| awaited sync generator | yields send deltas (progress 1,2,3 seen as separate frames); `await` returns the generator's `return` value |
| awaited async generator | deltas per yield; `await` returns None |
| handler returning `rx.toast(...)` / `[rx.toast(...), Main.add(100)]` | `await` returns None; toast shows; `Main.add(100)` runs after the caller finishes (caller sees total=0, page ends at 100) |
| handler returning `[]`, a dict holding a `datetime` and a dataclass | returned as-is (objects, not JSON) |
| `await rx.toast(...)`, `await rx.redirect(...)` | `EventHandlerTypeError: \`_call_function\` is a frontend-only event, so it cannot be awaited; yield or return it instead.` |
| awaited handler raises, caller catches | exception propagates, partial write (total=1000) kept, no toast |
| awaited handler raises, caller does not catch | error toast, caller's and callee's writes (last_added=-1, total=1000) reach the page at once and are persisted (memory and Redis) |
| recursion `fact(10)` | 3628800; unbounded self-await: `RecursionError` at depth ~319, catchable, state fine (every level goes through middleware: 319 preprocess calls) |
| `@rx.event(throttle=)/(debounce=)/(supersedes=True)` handlers awaited inline; `.throttle(500)` / `.stop_propagation` on the awaited spec | event actions are ignored by `await`; values returned |
| `asyncio.gather` of 4 handlers (two states) | `[1, 11, 'slow_done', 1]` |
| `asyncio.ensure_future(Main.slow(0.5))` not awaited | lock stays held until the task is done, its deltas arrive |
| `asyncio.create_task(Main.add(1))` | `TypeError: a coroutine was expected, got EventSpec(...)` (use `ensure_future`; the docs only mention the latter) |
| `asyncio.wait_for(Main.slow(5), 0.2)` | `TimeoutError`, the cancelled handler's write (progress=1) is sent, lock released |
| arguments | `"5"` -> int 5, kwargs ok, dataclass and `datetime` pass by reference, dict -> dataclass, ISO string -> datetime; `Main.add("abc")` logs a warning and runs the handler with the str; `Main.add(1, 2)` silently drops the extra value; a list/dict argument is detached (callee mutations do not reach the state) |
| proxied dict then proxied list (#7673 bugfix) | works on 0.11.0a1; control `probes/proxied_args.py` raises `EventHandlerTypeError ... Got MutableProxy` on 0.10.1 |
| foreground `await Main.bg_worker(1)` / inside `async with self` | `EventHandlerTypeError: Background event handler ... cannot be awaited while the state lock is held ...; yield it instead.` |
| background, outside `async with self`: await a handler, an async generator, a background handler, `gather` | queued and awaited; values returned (`7`, None, `'worker2'`, `[1, 11, 1]`) |
| background, inside `async with self` | runs inline (`7,1,1` across three states) |
| upload handler awaiting two handlers (2 files) | `sizes=[5, 1005] other=1`; `await Main.handle_upload(rx.upload_files("u1"))` -> `EventHandlerTypeError: Upload event ... cannot be awaited` |
| `on_load` awaiting two handlers (client navigation and hard load, dev and prod) | runs once per load |
| natural mistakes | `await self.add(5)`: the handler RUNS (total=5) and then `TypeError: object int can't be used in 'await' expression`; `await self.async_handler()` works but skips middleware; `await other_state.record(..)` after `get_state`: same TypeError after running; `Main.add(5)` in a sync handler builds an EventSpec and does nothing (as before); in a background task `await self.add(1)` outside the lock: `ImmutableStateError` |

Middleware (#7782; `awaitapp/awaitapp/mw.py`, registered with `app.add_middleware(...)`, `rx.Middleware.preprocess(app, state, event)`):
- an awaited event reaches `preprocess` with the handler's full name, its payload (`{'amount': 5}`) and `router_data`; `state` is the root `State` as for queued events.
- blocked (`secret_add`, logged out): handler does not run (`secret_runs=0`), `await` returns None, the middleware's delta + toast reach the page — foreground,
  background outside the lock, background inside the lock, `app.modify_state`, and a direct click. After `login`: runs and returns 5 / 10.
- a middleware that rewrites `event.payload` (amount x10) affects the awaited handler exactly like the clicked one (30 in both).
- a middleware that raises: the exception propagates into the awaiting handler (`RuntimeError: middleware exploded`), catchable.
- `self.secret_add(5)` (plain method) bypasses middleware, as documented.
- upload events were already gated by middleware on 0.10.1 (legacyapp `gated_upload`, blocked on both) — no behaviour change there.

### FINDING C (MEDIUM): `await State.handler()` in an API route outside `app.modify_state` does not raise; it runs on a shared session with an empty token
`scripts/drive_poke.py` + `curl localhost:<backend>/poke/<anything>` (route `poke` in `awaitapp.py`). The docs (`docs/events/chaining_events.md`) say
"Only inside an event handler (or `app.modify_state`); awaiting a handler anywhere else raises an error." In a Starlette route mounted through
`api_transformer`, `await Main.add(1)` after the `modify_state` block returns 1, then 2, 3, 4 on later requests (different tokens in the URL, different
workers in prod): the event is enqueued on the event processor's root context, whose token is `''`. Server log: `Attempting to send delta to disconnected
client ''`. With Redis the state is stored under `_reflex___state____state` / `_reflex___state____state.awaitapp___awaitapp____main` and shared by every caller.
Inside `app.modify_state(rx.BaseStateToken(ident=token, cls=Main))` awaiting works as documented (deltas reach the page, middleware gates, background handler refused).

### FINDING D (LOW-MEDIUM, diagnostics regression): see "Handler return values from the frontend" above.

### FINDING E (LOW): memory manager — a background task awaiting a `supersedes=True` handler gets `CancelledError` for a run that completed
`evidence/supersedes_bg_await_trace.txt`. Two clicks 150 ms apart on `c_bg_supersedes` (background task: `r = await Main.search(q)`, `search` is
`supersedes=True`, sleeps 0.6 s). Memory (dev and prod, 4/4 runs): `search(bgfirst)` runs to its end and commits `query=bgfirst`; the second task starts in the
same millisecond, enqueues `search(bgsecond)`, and the FIRST task's `await` raises `CancelledError` although its handler finished. Redis (dev and prod):
the first task gets `'BGFIRST'`. A background task that does not catch `BaseException` just stops there, silently.

### Other observations (anomalies, low)
- Background task + awaited handler that raises (enqueue path): the exception reaches the awaiting task AND the app's backend exception handler (error toast +
  `[Reflex Backend Exception]`), even when the task catches it (`c_bg_boom`). The foreground inline await only propagates (`c_boom_caught`: no toast).
- Prod, hard load of `/onload`: `self.router.url.path` is `/onload/` (trailing slash); dev and client-side navigation give `/onload`. Not baselined on 0.10.1.
- Import-time deprecation warnings appear twice at `reflex run` start (CLI + backend) and once per hot reload; call-time ones once per wrapper. Not noisy.
- `deprecation_version` is `"0.11.0"` in all five new `console.deprecate` calls of the installed wheel (the planning note about `"0.10.2"` does not apply to
  what shipped); CHANGELOG and docs contain no leftover "stateless handler" text (`git grep -i stateless v0.11.0a1 -- docs CHANGELOG.md`).
- Lock hygiene (`scripts/drive_locks.py`, dev+memory and prod+Redis): gather with one failing handler, `ensure_future` then raise, a `supersedes=True` handler
  or background task superseded while awaiting inline, `wait_for` timeout inside `async with self`, page reload during an awaited 2 s handler — the next event is
  served as soon as the remaining inline work ends (0.05-0.7 s, or the 2.5 s the superseding run legitimately holds the lock). No stuck lock.
- First driver run only: removing sonner toast nodes by hand from the driver crashed React (`insertBefore`/`removeChild` NotFoundError). Driver artifact, fixed
  by observing toasts with a MutationObserver instead; not a framework issue.

### Not covered
`ty`; Python 3.11 / 3.13 / 3.14 runtimes; reflex-enterprise `AuthMiddleware` with awaited handlers; SharedState / linked states with await; chunked upload
handlers; a real store failure for #7738 (a `get_state` override stands in for it); client disconnect mid-await other than a page reload.
