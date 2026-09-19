# Cluster `render_ctx_statemgr` — per-state context providers (#6181), stable provider values (#6180), StateManagerDisk (#7159), `_get_was_touched` (#7132)

Changelog lines (verbatim):
- (reflex-base) Reduce browser rendering overhead for state updates, especially in apps with many substates. (#6181) — PR: each substate gets its own reducer and provider so a delta only re-renders the providers it touches; dispatchers register into a stable shared registry during the layout phase, before the event loop connects the WebSocket; the new browser test checks an on_load updating two sibling substates produces both values and a SINGLE received delta.
- (reflex-base) Components that read the color mode or event loop context no longer re-render on unrelated `ThemeProvider` updates or on router navigation. The `ThemeProvider` system-preference listener is now attached once on mount. (#6180)
- Fixed `StateManagerDisk.set_state` to persist and cache state instances that were not obtained from `get_state`, and debounced writes now flush the latest supplied value instead of the first one queued. (#7159)
- Keep saving state to disk and Redis when a state defines a var named `_get_was_touched`. (#7132)

Read PRs #6181, #6180, #7159. These merged in the last 24 h before the alpha (#6181 is the top
commit of the train) so they are the least battle-tested code in the release.

## Build (dev AND prod; baseline render counts on 0.9.11.post1)

1. Render-count instrumentation: a small custom component (subclass `rx.Component`/`rx.el.div`
   with `add_hooks` returning `const r = useRef(0); r.current++; window.__renders = window.__renders || {}; window.__renders["<name>"] = r.current;`)
   placed (a) inside each of 8 substate-bound sections, (b) inside an `@rx.memo` receiving props
   from two substates, (c) inside a `ComponentState`, (d) next to a component that reads the color
   mode (`rx.color_mode_cond`, `rx.color_mode.button`), (e) a plain `rx.button` with an `on_click`
   (event-loop context consumer), (f) inside `rx.foreach` over 300 rows of substate A.
   Read `window.__renders` from Playwright after: one event touching substate A only; a background
   task updating substate B every 100 ms for 5 s while the user clicks in A; toggling color mode;
   client-side navigation and back; `on_load` updating two sibling substates (assert one websocket
   frame carrying both). Compare counts with 0.9.11.post1 — the claim is fewer re-renders; report
   the numbers either way. Also measure long tasks (`PerformanceObserver` `longtask`) during the
   background storm.
2. Dispatcher registry edge cases: a substate whose FIRST consumer mounts only after navigation
   (page-2-only substate) receiving a delta pushed by a background task started on page 1;
   `rx.dynamic`/lazy components mounting late; a delta for a substate that no mounted component
   consumes (the previous campaign's FINDING-036 latched the frontend dead — see
   `git -C /home/user/reflex show origin/claude/reflex-prerelease-testing-t0sd90:prerelease-testing/2026-09-10-v0.9.11a1/FINDINGS.md`
   and search for FINDING-036) — re-test it on this train, with the same repro shape.
3. Client-storage vars (`rx.LocalStorage`, `rx.Cookie`, `rx.SessionStorage`) in two different
   substates: set them, reload, open a second tab; values must hydrate into the right provider.
4. StateManagerDisk (`REFLEX_STATE_MANAGER_MODE=disk`, dev mode): set a var 20 times in 1 s
   (debounce), SIGTERM the server within the debounce window, restart, reload → the LAST value
   must be there. Persist a state obtained via `app.modify_state(token)` from a custom Starlette
   API route (`app.api`/`api_transformer`) rather than from the websocket, and check it lands on
   disk and is visible to the browser. Hot reload (edit a file) with the disk manager → state
   survives the worker restart. A state declaring `_get_was_touched: bool = False` (and one
   declaring it as a computed var) → persistence to disk AND redis still happens (compare the
   `.states/` dir / redis keys before and after; 0.9.11.post1 stops saving — confirm as baseline).
