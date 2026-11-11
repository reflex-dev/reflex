# events_await cluster — reflex 0.11.0a1 (#7673 / #7770 / #7782 / #7715 / #7752 / #7755 / #7754 / #7696 / #7412 / #7738)

## Status / resume here
- [x] awaitapp (await matrix + middleware + upload + on_load) written; dev + memory run done (`out/new_dev_mem.json`)
- [x] awaitapp prod + memory, dev + redis, prod + redis (identical to dev + memory except `sup_bg_await_x2`, see anomalies)
- [x] legacyapp (decorator stacking + failure paths) on 0.11.0a1 (dev mem, dev redis, prod redis) and 0.10.1 (dev mem, dev redis)
- [x] `probes/deco_matrix.py` on both versions; reflex-examples `overkey` import on both versions
- [x] typing module (pyright 1.1.414 + 1.1.411, mypy 2.4.1; 0.11.0a1 vs 0.10.1) — `typing/`
- [ ] report written to `../reports/events_await.md`

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

## Results so far

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
