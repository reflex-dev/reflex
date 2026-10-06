# Cluster `hydration` — combined hydrate+connect (#7064) and client-storage/on_load lifecycle

Ports: frontend 3220-3239, backend 8220-8239. Work dir: $SB/apps/hydration/. DEST: /home/user/reflex/prerelease_testing/2026-10-06/hydration/

## Why this cluster exists
Changelog (verbatim):
- (reflex, Performance) Speed up first page loads by combining hydration with the websocket connect and sending only values that differ from compiled defaults. Reduce Redis state-tree read/write overhead and avoid repeated class metadata computation in apps with many states. (#7064)
- (reflex-base, Performance) Begin opening the websocket transport before React mounts, then hydrate with a single `hydrate_and_load` event sent along with the websocket connect to save a round trip. (#7064)
- (reflex-base, Bug Fixes) Events sent while a buffered upload ... is in flight are no longer chained to it ... navigating during an upload cancels the previous page's unfinished `on_load` handlers again. (#7357)
- (reflex-base, Bug Fixes) Flatten nested client event lists before dispatch and keep processing queued events after one event fails. (#7319)

Implementation notes (read `git show origin/r/pre-2026.10.05-37378928999:reflex/state.py` around
`hydrate_and_load`, and `packages/reflex-base/src/reflex_base/event/processor/base_state_processor.py`
`_supersede_previous`; PR #7064 description via the GitHub MCP tool): on each websocket (re)connect the
frontend sends ONE `hydrate_and_load` event carrying the browser's client-storage values and per-state
hashes of the compiled `initialState`; the backend resets client storage, applies the browser values,
and sends only states whose hash differs; then `on_load_internal` runs page on_load handlers as a
separate superseding event. The previous campaign only verified "page hydrates" and "?self=1".
Everything below is the interaction surface nobody has driven.

## Build one multi-page app (dev AND prod — prod is where `initialState` hashes matter most) with:
1. Client storage vars: `rx.LocalStorage` (plain and `sync=True`), `rx.SessionStorage`, `rx.Cookie`
   (with `max_age`/`path`), on the root state AND on a substate AND on a `ComponentState`; defaults that
   are non-empty strings; a var whose default equals what the browser stores (hash-equal case) and one
   that differs. Flows: set values → reload → values restored BEFORE on_load runs (have on_load read them
   and record what it saw); two tabs with `sync=True` (change in tab A appears in tab B); clear storage via
   devtools (`page.evaluate`) → reload → defaults restored; set a cookie from JS to a value of the wrong
   type (e.g. non-int for an int var) → what happens on hydrate? (traceback vs graceful); very large
   localStorage value.
2. on_load variety: a page whose on_load redirects (`return rx.redirect("/other")`); one whose on_load
   is a background task; one whose on_load raises; one whose on_load yields several deltas slowly (2s)
   — navigate away mid-way (client-side link AND browser back) and verify the stale on_load's later
   deltas do not land on the new page (`supersedes`); `app.add_page(on_load=[A, B])` ordering with a
   substate handler that depends on the root's client storage; `rx.State.is_hydrated` used in `rx.cond`
   to gate UI (spinner → content): no flash of wrong content, and `is_hydrated` becomes True exactly
   once per load; `on_load` + `rx.call_script` returning a value into a handler.
3. Defaults that differ from compiled defaults: a var with `default_factory` producing a per-session
   value (uuid/time), an env-driven default, a computed var (`@rx.var`) with a non-trivial initial value,
   a var the app mutates at import time on the class (`State.items.append` style anti-pattern — does the
   hash diff still send it?), a `dict`/`list`/dataclass-typed var, a var typed `datetime`. Verify the
   first paint shows the right values in prod (no flash of compiled defaults → inspect the websocket
   frames: which states were sent in full vs partial).
4. Reconnect: kill the backend (SIGTERM the `reflex run` process group) while a tab is open with
   modified state, restart it on the same ports; with the memory state manager the state is gone — what
   does the tab show, does it re-hydrate to defaults cleanly, does on_load re-run? Repeat with Redis
   (`REFLEX_REDIS_URL`, start your own redis-server) where state should SURVIVE: verify values persist
   and client storage is re-applied once, not twice. Also simulate a flaky socket by `page.context.set_offline(True/False)`.
5. Multi-tab same client token: open the same app in two tabs of the SAME context (same localStorage
   token → same backend state tree, different session ids): change state in one, see it in the other;
   reload one; close one. Then a NEW context (new token).
6. Dynamic routes at hydrate: `/items/[id]` with `on_load` reading `self.router.page.params["id"]` and
   `self.router.url`; load directly, client-navigate between two ids, back/forward. Catch-all route.
7. Event delivery during hydrate: click a button immediately on page load (before `is_hydrated`) — is
   the event queued and processed in order after hydration? Use `rx.cond(State.is_hydrated, ...)` vs an
   always-visible button.
8. `app.add_page(... on_load=State.handler)` where the handler is on a state that also declares
   LocalStorage: ordering between client-storage apply and on_load.
Also measure, roughly, time-to-first-delta on first load (dev and prod) alpha vs 0.9.12 for the same app
(Playwright `performance.timing`/websocket frame timestamps): the changelog claims a saved round trip —
report what you measured, it is fine if it is small.

For each failure, re-run the same scenario on `$SB/envs/stable` (0.9.12) to classify regression vs pre-existing.
