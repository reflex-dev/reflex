# Where Reflex apps spend their time: measurements and a plan

This directory holds a reproducible latency harness (`latency_*.py`) and the
results of running it against the current `main`. The goal was to replace
intuition ("apps feel slow") with a per-phase accounting of every millisecond
between a user action and pixels, in prod and dev mode, at realistic network
round-trip times (RTT), and to compare that with how peer frameworks solve the
same problems.

Environment: 4 vCPU Linux container, headless Chromium 1194, Python 3.14,
uvicorn + `websockets` sans-io, disk state manager (the default), production
export served by Starlette static files. Network RTT is emulated with a
loopback TCP delay proxy (`latency_delay_proxy.py`), so "50 ms" means a real
50 ms round trip for HTTP and websocket traffic alike. All numbers are medians.

## 1. Results

### 1.1 Cold first load (prod, 6-page app, `/` prerendered)

| phase (ms since navigation start) | 0 ms RTT | 50 ms RTT | 100 ms RTT |
|---|---|---|---|
| HTML `responseStart` | 4 | 56 | 106 |
| `DOMContentLoaded` (JS parsed, React mounted on prerendered HTML) | 74 | 217 | 381 |
| websocket open | 121 | 293 | ~470 |
| `hydrate` delta received (7.2 KB) | 136 | 456 | 801 |
| warm reload, hydrated | 89 | 429 | 784 |

Transfer: 16 requests, 332 KB on the wire; JS is 13 files, 239 KB gzipped /
779 KB decoded (root chunk 272 KB raw, entry 178 KB, `link` chunk 144 KB).

Websocket frame timeline at 50 ms RTT (from `frames_prod_50.txt`):

```
recv 0{...}            +349 ms   engine.io open packet (after TCP + upgrade)
sent 40/_event         +349 ms   socket.io namespace connect
recv 40/_event         +402 ms   (+1 RTT)
sent hydrate           +403 ms
sent on_load_internal  +403 ms
recv delta (7223 B)    +458 ms   (+1 RTT)
recv delta (88 B)      +458 ms
```

So after the page has JS, the socket costs TCP + upgrade (2 RTT), then the
namespace connect (1 RTT), then hydrate (1 RTT). The prerendered HTML paints
early, but nothing that reads state is meaningful until `hydrate` lands, which
is roughly 8 RTTs after navigation start.

### 1.2 Client-side navigation (prod, click on `rx.link` from `/`)

Times in ms after the click. "mounted" is the destination route rendered;
"hydrated" is when `State.is_hydrated` flips back to true.

| destination | metric | 0 ms | 50 ms | 100 ms |
|---|---|---|---|---|
| `/table` (100 rows, no `on_load`) | mounted | 23 | 73 | 122 |
| | hydrated again | 40 | 73 | 124 |
| `/loaded_fast` (`on_load`, no I/O) | mounted | 21 | 62 | 111 |
| | on_load data shown | 21 | 62 | 111 |
| | hydrated again | 22 | 71 | 122 |
| `/loaded` (`on_load` with 20 ms I/O) | mounted | 17 | 64 | 112 |
| | on_load data shown | 28 | 78 | 128 |
| | hydrated again | 43 | 93 | 144 |
| `/static` (no state on page) | mounted | 13 | 61 | 115 |

Every navigation costs one RTT before the destination is even mounted: the
route module is a separate chunk that is fetched on click (`chunk_requests` =
1 every time; nothing is prefetched). Then `on_load_internal` costs a second
RTT plus handler time before `is_hydrated` is true. A page with no `on_load`
still pays that second round trip. The `unhydrated` flag is set ~16-20 ms
after the click, so anything gated on `is_hydrated` flickers for one RTT.

### 1.3 Event round trip (prod, `counter += 1` on a small page)

| leg | ms |
|---|---|
| click handler to `WebSocket.send` (state.js) | 0.2 |
| browser send to `on_event` on the server (wall clock, same host) | 1.0 |
| server `on_event` arrival to `emit_update` returned | 1.4 |
| `emit_update` to uvicorn ASGI `websocket.send` | 0 (inside the emit) |
| ASGI send to `message` event in the page | 0.4 (synthetic click) |
| websocket message to DOM updated | 0.6 |
| **click to DOM, synthetic click** | **3.3** |
| click to DOM, real mouse input via Playwright | 12.6 |
| click to DOM at 50 / 100 ms RTT | 54 / 104 |

Server-only round trip from a Python socket.io client: 1.14 ms for Reflex vs
0.53 ms for a bare python-socketio echo server, so the framework adds about
0.6 ms of Python per trivial event. Raw browser `WebSocket` to the same backend:
1.2-2.8 ms. The ~9 ms difference between synthetic and real clicks is
Chromium's own input handling, style, layout and paint for the click, which
delays the websocket `message` task on the main thread; it is not Reflex code
(CPU profile: 15 ms of app JS across 30 clicks). Conclusion: at loopback the
whole stack answers an event in ~3 ms. Interaction latency in deployed apps is
one network RTT plus handler time, plus rendering.

`rx.input` `on_change` is debounced by default: typing 21 characters produced
one websocket frame.

### 1.4 Large state (prod, 2000-row `rx.foreach` table on the page)

| action | click to DOM (ms) | delta bytes |
|---|---|---|
| `counter += 1` (same substate as the list) | 49 | 106 |
| unrelated var in the same substate | 45 | 104 |
| mutate one cell of one row | 57 | 79,673 |
| var in a *different* substate | 32 | 103 |
| same `counter += 1` on a small page | 13 | 133 |

Two structural costs show up here. Deltas are var-granular: changing one cell
resends the whole 80 KB list. And any state change re-renders the whole page:
an unrelated var in a different substate still costs +20 ms, and one in the
same substate +37 ms, because the state contexts are provided from one tree
and the page consumes them wholesale (tracked as #6181).

### 1.5 Dev mode

Cold load in dev: 27 JS files, 8.4 MB (unbundled React dev build), 45 requests,
hydrated at 424 ms on loopback.

Edit-to-browser cycle (`reflex run`, change one heading, 5 iterations):

| event (ms after save) | median |
|---|---|
| backend websocket closed (uvicorn reloader kills the worker) | ~150 |
| client reconnect attempts | 150, 350, 750, then 1350 |
| "Compiling: 100%" (worker re-imported, all pages recompiled) | 715-920 |
| Vite HMR update for the route received | 730-1170 |
| backend websocket reopened, re-hydrated | 1350-1390 |
| **new text visible** | **1120-1480** |

Breakdown of a cycle: ~0.15 s change detection, then ~0.6-0.8 s until the
worker has restarted, re-imported the app and recompiled every page (in
isolation, a fresh interpreter importing `reflex` and touching
`rx.App`/`rx.State`/`rx.box` costs 1.2 s, plus 0.1 s for the app module, so the
reloader's worker evidently avoids part of that cold import), then up to 0.6 s
waiting for the client's incremental reconnect backoff (`200 ms * n_errors` in
`state.js`) even though the backend was already up. The frontend HMR update itself lands within ~100 ms of the
compiler writing the route file.

Compile cost scales with total page count, not with what changed
(`latency_compile_scaling.py`, dry-run compile of a page with a table, a form
and ten rows of controls):

| pages | compile (s) | per page (ms) |
|---|---|---|
| 1 | 0.08-0.15 | 78-147 |
| 5 | 0.10 | 21 |
| 20 | 0.45 | 22 |
| 50 | 1.24 | 25 |

On a real docs-sized app (80 routes, 42k components) this was 48 s after #7012.

## 2. Reading the numbers

Reflex's per-event Python cost, transport and client runtime are already
fast: 3 ms end to end on loopback. Nothing in the hot path is "the" bottleneck.
The slowness users feel is round trips multiplied by RTT, paid in places where
other frameworks pay none:

- **First load: ~8 RTTs before state-dependent content appears.** HTML, JS chain,
  TCP + upgrade, socket.io namespace connect, then `hydrate`. Prerendered HTML
  only carries the compiled default values of state vars, never per-user or
  `on_load` data, so real content waits for the socket.
- **Navigation: 2 RTTs minimum.** One for the lazily loaded route chunk, one for
  `on_load_internal`, even when the page defines no `on_load`. Nothing is
  prefetched on hover or in viewport.
- **Interaction: 1 RTT for everything**, including pure UI state (toggles,
  tabs, dialogs, hover), plus full-page re-render and whole-var deltas on large
  state.
- **Dev: O(all pages) compile plus a process restart on every save**, plus
  reconnect backoff that idles after the backend is ready.

## 3. How peers attack the same latencies

Same architecture family (state on the server, UI patched over a socket):

- **Phoenix LiveView** renders once over plain HTTP ("dead render") and only then
  connects the socket, so first paint has data; templates are split into static
  and dynamic parts with fingerprints so diffs carry only changed expressions;
  `live_patch` navigates within a view with a minimal diff instead of a full
  remount; `Phoenix.LiveView.JS` commands (toggle, show, hide, add_class) run
  without a round trip; every push gets an automatic `phx-*-loading` class.
  https://hexdocs.pm/phoenix_live_view/Phoenix.LiveView.Engine.html,
  https://hexdocs.pm/phoenix_live_view/live-navigation.html,
  https://hexdocs.pm/phoenix_live_view/Phoenix.LiveView.JS.html
- **Livewire v3** prefetches `wire:navigate` links on hover (60 ms), defers
  `wire:model` sync by default (per-keystroke is opt-in), uses Alpine for client
  state, morphs the DOM, and lazy-loads components with placeholders.
  https://livewire.laravel.com/docs/3.x/wire-navigate
- **Blazor Server** prerenders, ships binary render batches (diff of the render
  tree, not whole values), and .NET 8 added enhanced navigation and streaming
  rendering; `InteractiveAuto` exists precisely because server round trips on
  every interaction felt slow.
  https://learn.microsoft.com/en-us/aspnet/core/blazor/components/render-modes
- **Turbo 8 / htmx** prefetch on hover by default and show cached snapshots
  instantly; InstantClick documented the 200-300 ms hover-to-click gap this
  exploits. https://github.com/hotwired/turbo/pull/1101, https://instant.page/
- **Streamlit** is slow for the same reason (full rerun per interaction over a
  websocket) and answered with `st.fragment` and caching; **Dash** added
  `clientside_callback` "to avoid the extra time that it takes to make a
  roundtrip to the server"; **Marimo** reruns only dependents of a change.

Client frameworks the user asked about:

- **React Router** (already Reflex's router) has `<Link prefetch="intent|viewport|render">`
  which preloads route modules during hover; Reflex's `rx.link` does not expose
  it. **TanStack Router** does the same with `defaultPreload: 'intent'` plus
  loader caching with a 30 s stale time. Switching routers would buy nothing the
  current one cannot do; the missing piece is exposing prefetch and applying
  the *same* intent-preload idea to `on_load`.
- **TanStack Query / SWR** assume the client owns a cache of server data and
  revalidates it. Reflex state is server-authoritative and mutated by handlers,
  so a generic client cache would show stale values. What transfers is the
  pattern (stale-while-revalidate keyed by route and a server-side state
  version), not the library.
- **Speculation Rules** (Chrome) measured 58-67 ms LCP savings at Google Search
  scale from hover prerendering; instant.page's data says a 65 ms hover gives a
  50% click probability with 300 ms to spare. That window is exactly the second
  navigation RTT Reflex pays today.
  https://developer.chrome.com/blog/search-speculation-rules

Human thresholds: 100 ms feels instant, 1 s keeps flow (Nielsen; RAIL). At a
100 ms RTT Reflex navigation lands at 120-145 ms and interactions at ~105 ms,
so a deployed app with a single-region backend sits right at the edge where
every extra round trip is felt.

## 4. Already landed or in flight (do not redo)

Recent perf work concentrated on Python CPU per event and compile time, which
the measurements confirm is now small: #7025 (-28% CPU per event), #7012
(compile 263 s to 48 s on 80 routes), #6949 (auto-memoized `rx.memo` call
sites), #6905 (React owner stacks off in dev), #7021 (`REFLEX_DEV_PROD_REACT`,
`REFLEX_VITE_WARMUP_ROUTES`), #6630 (`hydrate_fallback`). Open: #6906 (drop
unchanged router data from nav deltas, -72% bytes), #6946 (omit unchanged
computed vars), #6181 (per-substate context providers), #6936
(`rx.client_state()` redesign), #6688 (`REFLEX_COMPILE_CACHE` with a fork
server), #4922 (hot reload strategies), #3778 (binary wire protocol). None of
them removes a round trip from load or navigation.

## 5. Plan, ranked by measured impact

Each item lists what the measurements say it is worth.

1. **Skip the un-hydrate + `on_load_internal` round trip for routes without
   `on_load`.** The compiler knows which routes have load events; emit that set
   into the client and, for those routes, keep `is_hydrated` true and do not
   wait on the backend (the router-data update can still be sent fire-and-forget).
   Saves 1 RTT (50-100 ms) on most navigations and removes the flicker.
2. **Prefetch route chunks on intent.** Expose React Router's `prefetch` on
   `rx.link` and default it to `"intent"`. Saves the other RTT on navigation
   (the chunk fetch measured at exactly 1 RTT); the hover window is ~300 ms.
3. **Speculative `on_load` on intent, with a server-side result cache.** On
   hover, send `on_load_internal` for the hovered route with a "speculative"
   flag; the server runs the load chain against a copy of the state and caches
   the resulting delta for a few seconds keyed by (token, route, state version).
   On click the client asks for it and applies immediately. This is the
   TanStack/Livewire pattern applied to a server-owned state. Needs cancellation
   (#6593's supersede logic already exists) and a rule that handlers with side
   effects opt out.
4. **Collapse the socket handshake and push hydrate on connect.** Send the
   client token plus `on_load` request in socket.io's connect `auth` payload,
   have `on_connect` run hydrate and emit the delta unprompted. Saves 1-2 RTTs
   on first load (100-200 ms at 100 ms RTT). `pingInterval` and namespace can
   stay.
5. **Inline initial state into the prerendered HTML (dead render).** Serialize
   the default state (and for public pages, an on_load result computed at
   build time) into the page so the first paint shows data and `hydrate`
   becomes a diff. This is how LiveView and Blazor get their first paint. The
   remaining wait for interactivity is unchanged, so pair with 4.
6. **Client-only interactions.** A small `rx.js` command set (toggle, show/hide,
   set class, set a client var) and first-class `rx.client_state` (#6936) for
   pure UI state remove the 1-RTT cost for the most frequent interactions.
   LiveView's `JS` module is the reference design.
7. **Automatic loading state on the triggering element** (`data-loading`
   attribute, disabled until the delta arrives). Costs nothing on the wire and
   is the cheapest way to make a 100 ms RTT feel intentional instead of broken.
8. **Per-substate providers and finer deltas.** #6181 addresses the +20 ms
   unrelated-substate re-render measured on 2000 rows. For lists, move to
   per-item patches (JSON Patch or index-based ops) instead of resending the
   whole var: one cell edit currently costs 80 KB.
9. **Dev reload: stop waiting on backoff, then compile less.** Two independent
   fixes: (a) make the reloader signal readiness (or reconnect faster with a
   jittered short interval) so the client does not idle 400-600 ms after the
   backend is up; (b) incremental compile (module to pages dependency graph,
   compile changed pages and dependents, compile other routes on first request
   like Next's on-demand entries), which turns O(pages) into O(changed). #6688
   and #4922 cover the machinery. Together these bring a typical edit from
   ~1.3 s to well under 0.5 s on small apps and stop the linear growth.
10. **Optimistic setters.** For plain `setattr`-style handlers, apply the
    predicted delta locally and rebase on the server delta (Replicache's
    model). Removes perceived latency for form-like interactions; needs the
    compiler to mark handlers as pure setters.

Items 1, 2, 4 and 9a are small and measurable with this harness; items 3, 5,
6 and 8 are the architectural work that separates Reflex from the frameworks
above.

## 6. Running the harness

```
uv sync --all-packages && uv pip install playwright
uv run python benchmarks/latency_browser.py prod 0        # loopback
uv run python benchmarks/latency_browser.py prod 50       # 50 ms emulated RTT (prod only)
uv run python benchmarks/latency_browser.py dev 0
uv run python benchmarks/latency_browser.py prod 0 events_only synthetic   # click path only
uv run python benchmarks/latency_browser.py prod 0 events_only trace       # + Chrome trace
uv run python benchmarks/latency_big_state.py 2000
uv run python benchmarks/latency_server_rtt.py            # Python socket.io client vs bare echo
uv run python benchmarks/latency_ws_probe.py              # raw browser websocket RTT
uv run python benchmarks/latency_compile_scaling.py
uv run python benchmarks/latency_dev_reload.py 5          # needs a prior dev run (app_dev/)
```

Set `BENCH_CHROMIUM` to a Chromium executable if Playwright's default install
is not available. Reports are written next to the scripts as `report_*.json`;
`frames_*.txt` and `event_frames_*.txt` hold raw websocket frame timelines.
