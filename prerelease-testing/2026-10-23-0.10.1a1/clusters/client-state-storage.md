# Cluster `client-state-storage` — client_state, browser storage vars, hydration size

## Changelog lines (verbatim)
- (reflex #7407) Fix a global `rx._x.client_state` reader that mounts after the value was set, such as one behind an `rx.cond`, keeping the stale value when the value is later set back to its default.
- (reflex #7407) Fix `TypeError: refs._client_state_set... is not a function` when the backend pushes a global `rx._x.client_state` value before any component using it has mounted, such as one behind an `rx.cond` or a page that waits for hydration. The value is now kept for the first component that mounts.
- (reflex-base #7545) Editing one tab no longer leaves other `sync=True` browser storage vars that share its storage `name` stale in other tabs; every such var is now synced, not only the last one declared.
- (reflex #7603) Avoid false type errors when hydrating or assigning strings to vars annotated with `Cookie`, `LocalStorage`, or `SessionStorage`.
- (reflex #7568) Cached computed vars that depend on client storage (`rx.LocalStorage`, `rx.SessionStorage`, `rx.Cookie`) are now evaluated once per page load instead of twice.
- (reflex-base #7551 / core #7551) Report a hydrate message that exceeds the server's message size limit, with its size and the limit, instead of sending it and retrying. The default connection toast shows a hydration size error at once and keeps it open until the user closes it.
- (reflex-base #7605) Retry with backoff and show the connection error when the server or a proxy closes the connection before it is established, for example when browser storage makes the hydrate message too large, instead of reconnecting in a tight loop.
- (reflex #7585 / reflex-base #7585) A background task that re-enters an expired session now rehydrates the loaded state tree, so the browser no longer shows stale values for those states. The browser drops their stale values and keeps its route and browser storage; its next event runs the current page's on_load.

## What to build
An app with: global `rx._x.client_state` readers/setters, some behind `rx.cond` and on a second page; the backend pushing the client_state value (`State.set_value` via `cs.push(...)`) from `on_load` and from a background task before anything mounts; two `rx.LocalStorage(sync=True, name="shared")` vars in different substates sharing one storage name; `rx.Cookie`, `rx.SessionStorage`; a cached `@rx.var(cache=True)` reading a storage var with a server-side evaluation counter you expose on the page; a page that stuffs a LocalStorage var with ~1–2 MB so the hydrate message exceeds the default limit.

## Combine it with
- Two Playwright browser contexts/tabs for the sync test; edit in tab A, assert tab B for every sharing var.
- Set the client_state back to its default after a non-default value with the reader mounted late (the #7407 case).
- Count computed-var evaluations per page load across a full reload, client-side navigation, and prod mode. Compare to 0.10.0.
- Hydration-too-large: observe the toast text, that it persists, that the client does not loop (count socket connects in the network log over ~30 s), server log message. Then shrink storage and reload to recover.
- Expired session: run the backend with a short `REFLEX_STATE_EXPIRATION`/`state_manager` expiry (e.g. `rxconfig.py` `redis_token_expiration` is Redis-only; for in-memory use `REFLEX_STATE_EXPIRATION`? — check the released source on branch r/pre-2026.10.23-40018338326 for the knob) and a background task that sleeps past expiry, then writes; verify the browser rehydrates and route/storage survive.
