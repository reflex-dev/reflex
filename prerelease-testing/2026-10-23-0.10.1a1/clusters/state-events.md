# Cluster `state-events` — event loop, event sequences, background tasks, delta semantics

## Changelog lines (verbatim)
- (reflex #7402) A page's `on_load` accepts any sequence of events, e.g. a tuple, like a list of them.
- (reflex-base #7402) Event props and the events an event handler returns accept any sequence of events, e.g. a tuple or a variable typed `list[EventSpec]`, not only a list literal. The new `reflex_base.event.event_sequence` helper returns such a value as a sequence of events, wrapping a single event in a list.
- (reflex #7415 / reflex-base #7415) Cancel unfinished page-load event chains when the client disconnects, including hydration that has not yet started. Independent background events continue running.
- (reflex #7410) Fix unawaited coroutine warnings when a state delta filter withholds an async uncached computed variable.
- (reflex #7500) Mutating a nested value reached through `dict.values()` or `dict.items()` on a state var now marks the var dirty, so the UI and cached vars depending on it update.
- (reflex-base #7273, PERF) Unchanged objects and arrays in state updates now keep their previous identity on the frontend, so memoized components skip re-rendering them, and an update that changes nothing no longer re-renders at all.
- (reflex-base #7447, PERF) A running background event handler no longer keeps the state tree it was dispatched with alive once it has entered `async with self`.
- (reflex-base #7441 / reflex #7441) Fix a blank page with `Maximum call stack size exceeded` in apps with thousands of state classes. State is now read from one shared store, so the React provider tree no longer grows with the number of states. Detect state reads from the new shared state store when checking that an app that reads state defines an `rx.State` subclass.
- (reflex #7435 / reflex-base #7435) Frontend updates and events now keep working when a backend update names a substate the compiled frontend does not know. Reflex skips that substate and reports it once per connection. The backend log now says the substate was skipped.

## What to build
App A: pages whose `on_load` is a tuple, a list, a single event, a var-typed `list[EventSpec]` returned from a handler, `on_click=(A.h1, B.h2)`; a slow `on_load` chain (sleep 5 s across 3 handlers) that writes a server-side marker file at each step, so you can navigate away/close the tab mid-chain and prove cancellation (and that a `@rx.event(background=True)` task started from on_load keeps running). State with `dict[str, dict[str, int]]` mutated through `.values()`/`.items()` and a cached var over it. An async uncached computed var that a delta filter withholds (e.g. only referenced on page 2) — check server log for `RuntimeWarning: coroutine ... was never awaited`.
App B: generate ~2000–3000 substates programmatically (type()/exec) with a few vars each, one page reading a var from each of a few hundred; confirm it renders in dev and prod and compare with 0.10.0 (which should blow the stack per the changelog — confirm, that is the baseline).
Memo/identity: an `@rx.memo` child receiving a dict/list from state, with a render counter (console.log via rx.call_script or a DOM counter); trigger a no-op update and an unrelated-field update and count renders in 0.10.1a1 vs 0.10.0.

## Combine it with
- Background task + foreground handler racing on the same var; `yield` streaming; abrupt socket drop mid-stream (close the page) while a background task continues; check server log for tracebacks after disconnect.
- Unknown substate: compile the frontend, then add a substate to the backend only (edit the python, keep the prod-built `.web`, restart backend only or run backend with `reflex run --backend-only` against the old frontend build) and verify events still work and the log says "skipped" once per connection.
