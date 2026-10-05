# Cluster `router_vars` — the router split (#7068), inherited-var shadowing (#7077), reserved names (#7136)

Highest-risk change of the train: every app's root state gained five base vars and every navigation
delta changed shape. Changelog lines (verbatim):

Breaking:
- The root state gained five base vars holding the router data: `rx_router_session`, `rx_router_headers`, `rx_router_page`, `rx_router_url` and `rx_router_route_id`. A substate that declares one of these names now raises `BaseVarShadowsInheritedVarError`, the same error any other shadowed inherited var raises, and must rename its field. `State.router` itself is unchanged. (#7068)
- Declaring a substate var that shadows a var inherited from a parent state now raises `BaseVarShadowsInheritedVarError` at class creation. Such a declaration was silently ignored — reads and writes resolved to the parent's var and class-level access returned the raw default instead of a reactive `Var`. Rename the substate var to fix the error. (#7077)
- State vars, event handlers, and dynamic route arguments now reject names reserved by framework methods and bookkeeping before registration. Rename conflicting members. (#7136)
Deprecation:
- Declaring a computed var dependency on the `router` var (`deps=["router"]`) is deprecated; depend on the router Var instead, e.g. `deps=[State.router.url]` for a single field or `deps=[State.router]` to keep tracking all of them. (#7068)
Performance:
- Store router data in separate base vars (session, headers, page, url, route_id) so a navigation delta only re-sends the fields that changed instead of the whole router, and gather the connection-scoped router data (headers, client IP, session id) once at connect time rather than on every event. `State.router` is unchanged for app code. The page URL is also persisted as the URL itself rather than as its parsed pieces: `ReflexURL` and `URLData` re-split on the way out of the state store. (#7068)
- (reflex-base) The event processor now refreshes only the router vars whose backing `router_data` keys actually changed, so a navigation no longer rebuilds and re-sends the connection-scoped session and header data. `ROUTER_VARS` names the per-field router vars that replaced the single `router` var on the root state. (#7068)
- (reflex-base) `VarData` now tracks every state field a var is built from in `field_dependencies` ... A computed var depending on a composite var (`deps=[SomeState.composite]`) is now invalidated when any of its underlying fields changes — including fields belonging to a different state. (#7068)

Read PR #7068's description first (it has a table of which router vars land in the delta per event
kind, and a compatibility section). Also #7077 and #7136.

## Build (one multi-page app, dev AND prod, plus a redis variant)

Pages: `/`, `/items/[id]` (dynamic), `/docs/[[...splat]]` (catch-all), `/search` (reads `?q=`),
`/about`. Root `State` with computed vars covering EVERY dependency form:
`self.router.url.path` auto-dep; `deps=[State.router]`; `deps=[State.router.url]`;
legacy `deps=["router"]` (expect exactly one deprecation warning naming `State.router`);
one reading `self.router.headers.user_agent` and a custom header; one reading
`self.router.session.client_ip` / `client_token` / `session_id`; one reading the deprecated
`self.router.page.params`; one using `self.router.url.query_parameters`. A substate that reads
`self.router` in a handler and in a computed var. A `ComponentState` whose render uses
`State.router.url.path`. An `@rx.memo` component fed `State.router.url.path` as a prop.
Render the WHOLE router (`rx.code(State.router.to_string())` or pass `State.router` to a
component) — the PR says it still emits the pre-split object literal. `rx.cond(State.router.url.path == "/", ...)`.
`on_load` handlers that read `self.router.page.params["id"]` and redirect via `rx.redirect`.

Negative cases (compile-time, in a separate script with the venv guard): substate declaring
`rx_router_url: str`; substate shadowing a parent var (`count: int` in both); a computed var named
`router`; state vars / handlers named after framework members (try `dirty_vars`, `get_delta`,
`process`, `router_data`, `parent_state`, `substates`, `get_value`, `dict`, `set`; and a dynamic
route arg named `router` or `state`). Record the exact exception type and message for each and
judge whether the message tells a user what to rename. Compare with 0.9.11.post1 (what happened
before: silent shadowing, `'int' object is not callable`, ...).

## Drive (Playwright, capture websocket frames)

Record every `/_event` websocket frame (`page.on("websocket", ...)`, `framereceived`). For each of:
first event on a connection; client-side navigation to a different route; navigation within the
same dynamic route (different `id`); an event with no route change; a reload; a second tab in the
same browser context; browser back/forward; a direct load of `/items/7?x=1#frag` — assert WHICH
`rx_router_*` keys appear in the delta and the byte size, and compare against the PR's table and
against 0.9.11.post1's single `router` var. Check the computed vars re-evaluate (the page shows the
new path / params / query) on every form of navigation, including `deps=[State.router]` and the
legacy string form. Send a custom request header from Playwright (`extra_http_headers`) and check
it shows up; change it for a new context. Mutate `self.router_data["headers"]` inside a handler and
confirm the next event still sees the pristine headers (the PR claims the cache is copied).

## Persistence / upgrade

Run with `REFLEX_REDIS_URL` (your own redis on BP+15) AND with `REFLEX_STATE_MANAGER_MODE=disk`:
navigate around, then inspect the stored state (redis `GET`, or the `.states/` pickle) — the URL
should be stored ONCE, not as parsed pieces. Then the real upgrade path: run the same app on
0.9.11.post1 against the SAME redis (populate states), stop, start 0.9.12a1 against that redis and
reconnect the browser: old pickled states must be discarded gracefully (no traceback, page works).
Do the same with the disk manager. Also: kill and restart the backend with the tab open — a
reconnect should re-send `rx_router_session` only (new sid).

## Also

- Prod mode (`--env prod`, one port): repeat the navigation-delta matrix.
- Two browser CONTEXTS (two tokens) on different dynamic ids concurrently, each hammering events.
- Anything that used to read `State.router` at class level for a component prop (e.g. `rx.text(State.router.session.client_token)`) should compile to the per-field var — grep `.web/` for `rx_router_session` in the compiled page.
