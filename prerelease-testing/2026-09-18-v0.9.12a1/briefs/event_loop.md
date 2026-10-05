# Cluster `event_loop` — uncached-var delta dedupe (#6946), supersedes ordering (#7168), re-chain recursion (#7145), callback event routing (#7156, #7157), redis health client (#7187)

Changelog lines (verbatim):
- `@rx.var(cache=False)` vars now remember what they last sent to the frontend. They are still recomputed on every state update, but the value is only included in the delta when it actually changed... (#6946) / (reflex-base) `ComputedVar` now records a key for the value an uncached (`cache=False`) var last sent to each client, so `BaseState.get_delta` can leave the var out of the delta when a recomputation produces the same value. (#6946)
- (reflex-base) Superseding event handlers (`@rx.event(supersedes=True)`) now cancel stale invocations across distinct event chains: supersession is ordered by the user-initiated root enqueue, so the newest chain wins, invocations within one chain (self-chains and sibling fan-out) coexist, and a stale chain enqueuing a superseding handler after a newer chain already has is dropped instead of cancelling the newer work. (#7168)
- (reflex-base) Fix `RecursionError: maximum recursion depth exceeded` in the event processor when a handler re-chains itself many times (for example a polling loop started from `on_load`), which surfaced on the client's next navigation and in the event cleanup callbacks. (#7145)
- (reflex-base) Fix client-side event routing for events queued from callbacks (e.g. a `rx.call_script` callback or toast action triggering an upload handler): the client handler name was passed in the `event_actions` slot, so handlers like `uploadFiles` never ran. (#7156)
- (reflex-base) Fix `ReferenceError: queueEvents is not defined` when a callback formatted for a JS interface (e.g. a toast action button) runs outside the event-loop eval context; such callbacks now dispatch through `addEvents` like compiled event triggers. (#7157)
- (sonner 0.9.4a1) Fix `rx.toast` `action` and `cancel` buttons not triggering their `on_click` events when the toast is fired from a frontend event trigger. (#7157)
- Reuse one long-lived Redis client for the `/_health` endpoint instead of opening and closing a new TCP connection on every probe. (#7187)

Read PRs #6946 and #7168 (the latter has a precise three-way model: newer generation cancels,
same generation coexists, older generation is dropped).

## Build (dev AND prod; websocket frame capture is essential here)

1. Uncached vars: `@rx.var(cache=False)` returning (a) a stable value derived from a base var,
   (b) a value that alternates A→B→A across events, (c) a `float('nan')`, (d) a list/dict rebuilt
   each call with equal contents, (e) a dict whose key ORDER differs but contents equal, (f) a
   value depending on another substate. Hammer unrelated events and assert from the frames when
   each var is (not) in the delta. Then the cases where it MUST be re-sent: first hydrate, hard
   reload, a second browser CONTEXT (per-client memory — the two clients must not share the
   "last sent" key), a reconnect after killing the backend, and after the value changes back to an
   earlier value. Prod mode with redis and the default worker count: does per-client dedupe
   survive events landing on different workers (over-send is fine; a MISSING update is a bug)?
   Baseline the frame contents on 0.9.11.post1.
2. Supersedes: a `@rx.event(supersedes=True, background=True)` `refresh` that appends
   start/finish markers to a list and sleeps ~2 s; reach it (a) as a root from two buttons,
   (b) as a child of two different root chains (`yield State.refresh` from handlers A and B),
   (c) as sibling fan-out `return [State.refresh("x"), State.refresh("y")]`, (d) as a self-chaining
   poll loop started from `on_load` with a restart button mid-run, (e) a deliberately slow stale
   chain that enqueues `refresh` AFTER a newer chain already did. Assert from the markers which
   invocations were cancelled/dropped/ran, matching #7168's model. Foreground (non-background)
   variants too.
3. #7145: `on_load` → `yield State.tick` self-chain with `await asyncio.sleep(0.005)` for 3000+
   iterations, then navigate to another page and back; watch the server log for RecursionError and
   the browser console for errors; confirm the loop stops/continues as designed.
4. Callback routing: `rx.call_script("...", callback=State.handle(rx.upload_files(upload_id="u1")))`
   (i.e. a callback that triggers the upload client handler), a toast with `action=` /
   `cancel=` whose `on_click` is (a) a State handler, (b) a handler taking `rx.upload_files`,
   (c) `rx.set_clipboard`/`rx.window_alert`, fired (i) from the backend (`return rx.toast(...)`)
   and (ii) directly from a frontend trigger (`on_click=rx.toast("...", action=...)`), (iii) inside
   an `@rx.memo` and a `ComponentState`. Each must dispatch; watch for `ReferenceError` in console.
5. Health: start redis (BP+15), run with `REFLEX_REDIS_URL`, hit `/_health` 300 times and sample
   `redis-cli -p <port> CLIENT LIST | wc -l` and `INFO stats total_connections_received` before and
   after — the connection count must not grow per probe (compare 0.9.11.post1).

## Lead handed over from the `ent_mcp_oidc` cluster (please chase)

They found (regression vs 0.9.11.post1, reproduced only through reflex-enterprise's delta filter so far):
a `@rx.var(cache=False)` whose entry is removed from the outgoing delta by a downstream `get_delta`
override is **never re-sent** once it should become visible — #6946's "last value sent" memo is
updated when the value is computed, not when the delta is actually delivered. Their script:
`/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/ent_mcp_oidc/scripts2/uncached_after_login.py`
and NOTES.md ISSUE-2. Build a pure-reflex repro: e.g. a State subclass overriding `get_delta` (decorate
it with `rx.state._override_base_method`, a private helper, so #7136 accepts the name) that drops the
uncached var's key the first time; or make the socket drop between compute and emit (kill the tab's
websocket right after an event) and see whether the next event re-sends the unchanged uncached value.
Read the memo logic in the release source (`grep -n "last" reflex/state.py packages/reflex-base/src/reflex_base/vars/base.py`
around `ComputedVar`/`get_delta`) and say precisely when the memo is written.
