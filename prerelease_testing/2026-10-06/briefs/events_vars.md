# Cluster `events_vars` — event-loop semantics (supersedes/background/nested lists), var operations, state API edge cases

Ports: frontend 3460-3479, backend 8460-8479. Work dir: $SB/apps/events_vars/. DEST: /home/user/reflex/prerelease_testing/2026-10-06/events_vars/

## Why this cluster exists
The previous core/state campaign verified the main descriptor behaviors (shadowing, inherited vars,
background mutation, ComponentState, client_state, deep_equals, slices, download, ABC, pickle). This
cluster is a second, adversarial pass over the event loop and Var machinery that changed in 0.10.0a1,
targeting the combinations it did not list. Changelog (verbatim):
- (reflex-base, Perf) Lower the CPU cost of every backend event: cached computed var reads, field reads and writes, event dispatch and the JSON encoding of state deltas are faster. A computed var returning a value of the wrong type is now logged once per computed value instead of on every read, and `EventHandler.is_background` and `EventHandler.supersedes` are read once per handler, so mark the function before the handler is first used. (#7370)
- (reflex-base, Perf) Reading a cached computed var no longer re-validates its return type, and in production mode state var assignments and computed var results check only the outer type instead of walking every element. The type checks only log errors ... (#7353)
- (reflex-base, Bug Fixes) Flatten nested client event lists before dispatch and keep processing queued events after one event fails. (#7319)
- (reflex-base, Perf) Reduce event-queue overhead when prepending events and processing events with a connected socket. (#7053)
- (reflex-base, Bug Fixes) Negative-step slices of array and string Vars now match Python at a `-1` bound ... and a Var step ... no longer raises `RecursionError`. (#7326)
- (reflex-base, Bug Fixes) `Var._replace(_var_data=...)` no longer raises `TypeError: dataclasses.replace() got multiple values for keyword argument '_var_data'`. (#7256)
- (reflex-base, Features) Add `Var.deep_equals()` for structural comparison of nested frontend values. (#7208)
- (reflex-base, Features) `Field` is now the descriptor holding a state var's value, and `EventHandler` binds to the state that declares it when accessed on a state instance. (#7312)
- (reflex, Breaking) ... Assigning an undeclared state attribute still raises `SetUndefinedStateVarError` outside of prod mode, but no longer in prod. (#7312)
Read `git show origin/r/pre-2026.10.05-37378928999:packages/reflex-base/src/reflex_base/event/__init__.py`
(the `event()` decorator: `background`, `supersedes`, `temporal`, `throttle`, `debounce`) and
`.../event/processor/event_processor.py` (supersedes = latest-wins per client token, cooperative cancel).

## What to do (one app, several pages; dev AND prod; Playwright; baseline on $SB/envs/stable for failures)
1. `@rx.event(supersedes=True)` user handlers: a slow async handler (yields 5 deltas over 5 s) triggered
   by rapid clicks — only the latest chain's deltas should land; with `background=True` + `supersedes=True`
   together (is that allowed? what happens?); a superseding handler that chains `yield Other.handler()`
   — is the chained child cancelled too?; a non-yielding CPU-bound superseding handler (cannot be
   interrupted — document the observed behavior); supersedes on a ComponentState handler used by two
   component instances (per-token semantics: does instance B's click cancel instance A's chain?).
2. Decorator-order / read-once (#7370): mark a handler background AFTER the class is created
   (`setattr(func, "_reflex_background_task", True)` after `State.handler` was accessed), a handler
   defined in a mixin and inherited by two substates (both backgrounds), a handler wrapped by a plain
   decorator (`functools.wraps`) before `@rx.event(background=True)`, a handler re-decorated by a package
   (`rx.event(State.existing_handler.fn, background=True)` style): does the app honor the marker, and is
   there any traceback? Compare 0.9.12.
3. Nested event lists (#7319): a handler returning `[A, [B, [C]], D]`, frontend `on_click=[E, [F]]`,
   an `rx.cond`-selected event list, a list containing one failing event in the middle (raises) followed
   by others — verify the others still run and the backend exception handler fired exactly once; the
   same via `rx.call_script` callbacks and `rx.run_script`; very deep nesting (depth 50).
4. Throttle/debounce/temporal with supersedes: `@rx.event(throttle=200, supersedes=True)` on key presses
   in an input (type 20 chars fast); `temporal=True` events sent while the backend is down (SIGSTOP the
   backend for 3 s then SIGCONT): dropped vs delivered, and ordering of the non-temporal ones.
5. Var ops: slices with Var bounds/steps inside `rx.foreach` over a State list (`State.items[::State.step]`,
   `[-1::-1]`, `[State.a:State.b]`, string vars `State.s[::-2]`), chained ops on sliced vars (`.length()`,
   `.join`, `.contains`), `Var.deep_equals` between a State dict var and a `rx._x.client_state` dict,
   between two computed vars, inside `rx.cond` and `rx.match`; `rx.Var.create(obj)._replace(_var_data=...)`
   in a custom component's `_get_imports/add_hooks` (the #7256 path); `rx.vars.object` key access with a
   Var key; `rx.foreach` over a dict var with `.items()`; `ArrayVar.pluck`/`.sort()`/`.reverse()` chains.
6. Type-check logging (#7353): a computed var returning the wrong type (declared `list[int]`, returns
   `list[str]`), a var assigned a wrong inner type (`list[int]` ← `["a"]`) in dev vs prod — count the
   log lines over 20 events (expect once per value in both, element-level only in dev); a wrong OUTER
   type in prod (expect a log line). No behavior change expected beyond logging; a crash is a finding.
7. State API: `self.get_state(Sub)` / `await self.get_var_value(Sub.x)` from a background task on a
   sibling substate with `async with self`; `State.setvar("x", v)` from the frontend (`State.setvar` as
   an event trigger) for a backend var name (should be rejected) and for a nonexistent name; `self.reset()`
   on a substate with client-storage vars and ComponentState children; `State.get_fields()` contents for a
   shadowed name on parent vs child (which Field object does each report; is the inherited one gone?);
   `dict()`/`get_value` on a state with a dataclass var holding a nested list after in-place mutation;
   assigning an undeclared attribute in dev (expect `SetUndefinedStateVarError`) and in prod (expect it
   silently works — then does the value show up in the delta? in `dict()`?); the auto-setter config
   (`REFLEX_STATE_AUTO_SETTERS`/`state_auto_setters` in rxconfig) on vs off: `State.set_x` existence and
   the deprecation/console message; `rx.State` subclass with `__init__` override; `__slots__`; a var named
   like a method (`items`, `dict`, `reset`, `router`): clear error or silent breakage?
8. Event handler binding (#7312): pass `Sub.handler` to a component rendered under a different substate's
   page; call `OtherState.handler(arg)` with a `Var` from `rx.foreach` index/item (0..4 args, and 5 args);
   `rx.event(lambda ...)` lambdas; an `EventHandler` accessed on an INSTANCE (`self.other_handler`) — the
   changelog says it binds to the declaring state: `return self.handler_of_parent()` from a child.
Record each divergence from 0.9.12 with a traceback or websocket-frame evidence.
