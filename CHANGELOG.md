## v0.9.12 (2026-09-21)

### Breaking Changes

- The root state gained five base vars holding the router data: `rx_router_session`, `rx_router_headers`, `rx_router_page`, `rx_router_url` and `rx_router_route_id`. A substate that declares one of these names now raises `BaseVarShadowsInheritedVarError`, the same error any other shadowed inherited var raises, and must rename its field. `State.router` itself is unchanged. ([#7068](https://github.com/reflex-dev/reflex/issues/7068))
- Declaring a substate var that shadows a var inherited from a parent state now raises `BaseVarShadowsInheritedVarError` at class creation. Such a declaration was silently ignored — reads and writes resolved to the parent's var and class-level access returned the raw default instead of a reactive `Var`. Rename the substate var to fix the error. ([#7077](https://github.com/reflex-dev/reflex/issues/7077))
- State vars, event handlers, and dynamic route arguments now reject names reserved by framework methods and bookkeeping before registration. Rename conflicting members. ([#7136](https://github.com/reflex-dev/reflex/issues/7136))
- `state.dict()` and the state deltas no longer carry a single `router` entry: the root state now serializes `rx_router_session`, `rx_router_headers`, `rx_router_page`, `rx_router_url` and `rx_router_route_id` instead (each with the usual field-marker suffix). Code that read or rewrote the `router` entry of a state dict or delta — for example to redact request headers before returning state over an API — must read those five entries instead. `State.router` itself is unchanged for app code. ([#7215](https://github.com/reflex-dev/reflex/issues/7215))

### Deprecations

- Declaring a computed var dependency on the `router` var (`deps=["router"]`) is deprecated; depend on the router Var instead, e.g. `deps=[State.router.url]` for a single field or `deps=[State.router]` to keep tracking all of them. ([#7068](https://github.com/reflex-dev/reflex/issues/7068))

### Bug Fixes

- Fix stateful inputs under `rx.form.control(..., as_child=True)` so they receive the parent form's attributes and their values appear in submitted form data. ([#6850](https://github.com/reflex-dev/reflex/issues/6850))
- Allow State Vars for page titles and descriptions in `@rx.page` and compiled metadata. ([#6923](https://github.com/reflex-dev/reflex/issues/6923))
- Stopping `reflex run` with SIGTERM no longer reports "Starting frontend failed with exit code 143" and now exits cleanly. ([#6981](https://github.com/reflex-dev/reflex/issues/6981))
- Preserve relationship serialization and database usage accounting for apps that use SQLModel directly, without loading unused database integrations. ([#7049](https://github.com/reflex-dev/reflex/issues/7049))
- Preserve prerendered pages when asset directories collide with routes under `frontend_path`, and compress the final merged output. ([#7078](https://github.com/reflex-dev/reflex/issues/7078))
- Generated `.pyi` stubs now type a prop declared as a union — `content: Var[str] | Component`, say — as optional, matching the `None` default that `create()` gives every prop. Type checkers previously reported the generated signature itself as an error. ([#7080](https://github.com/reflex-dev/reflex/issues/7080))
- Subclassing `rx.Model` (e.g. `class Item(rx.Model, table=True)`) without the `db` extra installed now raises the guided "pip install reflex[db]" `ImportError` instead of a bare `TypeError` from `__init_subclass__`. ([#7083](https://github.com/reflex-dev/reflex/issues/7083))
- Backend-only development runs no longer leave a compile-skip marker that can cause the next full run to skip frontend compilation. ([#7089](https://github.com/reflex-dev/reflex/issues/7089))
- Persist bundled-library metadata for backend-only workers so state hydration can serialize values that reference libraries included in the frontend build. ([#7096](https://github.com/reflex-dev/reflex/issues/7096))
- Keep the development backend port open while hot reload restarts the worker, so requests made during a reload wait for the new worker instead of being refused. ([#7114](https://github.com/reflex-dev/reflex/issues/7114))
- Fixed local package specifiers such as `@masenf/hello-react@../hello-react` and `@masenf/hello-react@../hello-react.tgz` being truncated at the first slash (to `@masenf/hello-react@..`) before reaching the package manager, so wrapping a React package from a local directory or archive now installs correctly. ([#7117](https://github.com/reflex-dev/reflex/issues/7117))
- Switching between bun and npm (`REFLEX_USE_NPM`) no longer leaves `reflex.lock/` in a state that makes the next run fail with `bun install --frozen-lockfile: lockfile had changes`. Only the lockfile of the package manager that actually ran is kept. ([#7129](https://github.com/reflex-dev/reflex/issues/7129))
- Keep saving state to disk and Redis when a state defines a var named `_get_was_touched`. ([#7132](https://github.com/reflex-dev/reflex/issues/7132))
- Apps no longer crash at startup with `AttributeError: 'method' object attribute '__call__' is read-only` when ASGI instrumentation that wraps middleware is active, such as sentry-sdk's Starlette integration. ([#7139](https://github.com/reflex-dev/reflex/issues/7139))
- Fix backend startup crashes from concurrent or truncated stateful-page marker writes. Markers are replaced atomically, remain readable by separate backend users, and are rebuilt when missing or corrupt; dry-run compilation leaves them unchanged. ([#7142](https://github.com/reflex-dev/reflex/issues/7142))
- Match routes that start with the `frontend_path` text, such as `/apple` under `frontend_path="/app"`, instead of treating them as 404. ([#7153](https://github.com/reflex-dev/reflex/issues/7153))
- Flush OpenTelemetry compile spans before the isolated initial development compile worker exits. ([#7155](https://github.com/reflex-dev/reflex/issues/7155))
- Fixed `StateManagerDisk.set_state` to persist and cache state instances that were not obtained from `get_state`, and debounced writes now flush the latest supplied value instead of the first one queued. ([#7159](https://github.com/reflex-dev/reflex/issues/7159))
- Fix `@rx.memo` components dropping the app wraps their body requires. Providers
  requested by a nested child, or through var data as `rx.upload`'s
  `UploadFilesProvider` is, now reach the app root — so a provider-backed
  component behaves the same inside a memo as inlined into the page. ([#7176](https://github.com/reflex-dev/reflex/issues/7176))
- Reuse one long-lived Redis client for the `/_health` endpoint instead of opening and closing a new TCP connection on every probe. ([#7187](https://github.com/reflex-dev/reflex/issues/7187))
- Emit Granian lifecycle logs as JSON records when Reflex JSON logging is enabled, keeping `reflex run --json` stdout valid JSON lines. ([#7193](https://github.com/reflex-dev/reflex/issues/7193))
- Avoid crash when node is not installed (`error: restartWithMergedOptions() was called, but the process has already been restarted.`). ([#7202](https://github.com/reflex-dev/reflex/issues/7202))
- `type(rx.State)` is `reflex.vars.BaseStateMeta` again, so a state declared with its own metaclass derived from `BaseStateMeta` (`class MyState(rx.State, metaclass=MyMeta)`) no longer raises `TypeError: metaclass conflict`. The reserved-state-name validation is unchanged: it now runs from `BaseStateMeta` itself for every subclass of `rx.State`. ([#7215](https://github.com/reflex-dev/reflex/issues/7215))
- An `@rx.var(cache=False)` value that a downstream `get_delta` override keeps out of the delta is now delivered as soon as the override stops withholding it, instead of being deduplicated away until the value changes again. Uncached var values only count as sent to the client once the delta that carries them is actually delivered. ([#7216](https://github.com/reflex-dev/reflex/issues/7216))
- Release the development backend port again when no worker can serve it, so requests fail fast while the app module raises on import and after the server shuts down, instead of waiting in the accept backlog until the client times out. ([#7217](https://github.com/reflex-dev/reflex/issues/7217))
- Keep app wraps registered below the "Built with Reflex" badge in the rendered
  page. In production builds with the badge on, the badge swallowed every
  lower-priority app wrap, so `rx.data_editor`'s `<div id="portal" />` never
  reached the DOM and its overlay cell editors — including the new image preview —
  could not open. ([#7218](https://github.com/reflex-dev/reflex/issues/7218))
- Fix nested router mutations bypassing background-task locks and read-only state proxies. Writes through `self.router` now enforce the same mutation guards as direct state-field access. ([#7230](https://github.com/reflex-dev/reflex/issues/7230))

### Performance

- `@rx.var(cache=False)` vars now remember what they last sent to the frontend. They are still recomputed on every state update, but the value is only included in the delta when it actually changed, so an uncached var whose value stays the same no longer causes needless network traffic and re-renders. ([#6946](https://github.com/reflex-dev/reflex/issues/6946))
- Reduce development startup and reload time and memory by deferring unused database, admin, and compiler imports in the backend launcher and state mutation tracking, and by avoiding redundant app preloads in spawned Granian supervisors. ([#7049](https://github.com/reflex-dev/reflex/issues/7049))
- Store router data in separate base vars (session, headers, page, url, route_id) so a navigation delta only re-sends the fields that changed instead of the whole router, and gather the connection-scoped router data (headers, client IP, session id) once at connect time rather than on every event. `State.router` is unchanged for app code.

  The page URL is also persisted as the URL itself rather than as its parsed pieces: `ReflexURL` and `URLData` re-split on the way out of the state store instead of writing scheme, netloc, origin, path, query, query parameters and fragment alongside the href on every state write. ([#7068](https://github.com/reflex-dev/reflex/issues/7068))
- Preload the global stylesheet so browsers can discover render-blocking CSS alongside early resource hints. ([#7078](https://github.com/reflex-dev/reflex/issues/7078))
- Honor `frontend_lazy_bundled_libraries` when compiling the app root so optional dynamic-component namespaces do not force their full exports into every page's initial bundle. ([#7078](https://github.com/reflex-dev/reflex/issues/7078))
- Reduce `reflex run` and `reflex export` memory: the vite/react-router processes no longer keep their dependency pre-bundling arena resident (`MIMALLOC_ARENA_EAGER_COMMIT=0`, overridable from the environment), and error telemetry is sent through `urllib` so backend workers never import `httpx`. ([#7112](https://github.com/reflex-dev/reflex/issues/7112))
- Speed up compilation by reading only the props a component sets, caching literal Var dispatch by value type, and trimming render and app-wrap bookkeeping. ([#7121](https://github.com/reflex-dev/reflex/issues/7121))
- Share one event chain per handler and trigger across call sites, and reuse memoized event wrappers by chain identity during compilation. ([#7122](https://github.com/reflex-dev/reflex/issues/7122))

### Documentation

- Refresh the `docker-example` deployments for current Reflex and consolidate them into `production`, `production-compose`, and `app-platform-backend`, with smaller images, clean SIGTERM shutdown, and no build tooling at runtime. The two-port example is gone since prod mode now serves the frontend and backend on one port; the self-hosting docs are updated to match. ([#7140](https://github.com/reflex-dev/reflex/issues/7140))


## v0.9.11 (2026-09-11)

### Breaking Changes

- State deltas may emit state entries and variable keys in a different order. Values are unchanged, but downstream snapshots or tests comparing serialized deltas as text may need updating; compare parsed JSON objects or normalize key order instead. ([#7087](https://github.com/reflex-dev/reflex/issues/7087))

### Features

- Propagate a frontend `traceparent` into event spans, count websocket connections and message sizes, and wrap the ASGI app when the `reflex-otel` instrumentor is active. ([#6227](https://github.com/reflex-dev/reflex/issues/6227))

### Bug Fixes

- A backend var whose name is annotated on a state now takes the default declared by a `field()` on a base class instead of silently becoming `None`, and an error raised by that field's `default_factory` surfaces instead of being swallowed. ([#6812](https://github.com/reflex-dev/reflex/issues/6812))
- State classes no longer resolve descriptors while being constructed, so a hybrid property's frontend var is no longer built against a half-built class. ([#6812](https://github.com/reflex-dev/reflex/issues/6812))
- Assigning to a state attribute backed by a property (including a `hybrid_property`) now runs its setter instead of raising `SetUndefinedStateVarError`. ([#6812](https://github.com/reflex-dev/reflex/issues/6812))
- Telemetry events are now collected under the submitting thread's registration context, so the background worker reuses the config the app already loaded instead of re-importing `rxconfig.py` (and mutating `sys.path`) off-thread. ([#6960](https://github.com/reflex-dev/reflex/issues/6960))
- Make `reflex.testing` importable without test-only dependencies and provide a `testing` extra for `AppHarness`. ([#6974](https://github.com/reflex-dev/reflex/issues/6974))
- Mutable proxies over dataclass state values now carry the wrapped type's `__dataclass_params__` and `__match_args__` on their class alongside `__dataclass_fields__`, so code that inspects a dataclass through the class — reading the `frozen`/`eq` flags or the positional field names after `dataclasses.is_dataclass` — no longer raises `AttributeError` on a proxied value. ([#7014](https://github.com/reflex-dev/reflex/issues/7014))
- `AdminDash` now works with starlette-admin 1.0, which renamed the SQLAlchemy `Admin(engine=...)` argument to `session_provider`. Both starlette-admin 0.x and 1.x are supported. ([#7019](https://github.com/reflex-dev/reflex/issues/7019))
- Compiling an app from several processes against one working directory — pytest-xdist workers, parallel builds, or containers sharing a bind mount — no longer aborts with `FileNotFoundError` or `FileExistsError` while linking a `rx.asset(shared=True)` file into `assets/external/`. A shared asset whose link already points at a different file is repointed at the asset rather than left alone. ([#7039](https://github.com/reflex-dev/reflex/issues/7039))
- `reflex run --env prod` and `reflex export` no longer fail with `FileNotFoundError` when `frontend_path` is set and route prerendering is disabled (`REFLEX_SSR=false`), and no longer fail on Windows with `cannot instantiate 'PosixPath'` whenever `frontend_path` is set. ([#7044](https://github.com/reflex-dev/reflex/issues/7044))
- Generate the frontend context module as `utils/context.jsx` so `reflex run` hot updates keep the state providers mounted; a stale `utils/context.js` is removed on the next compile. ([#7071](https://github.com/reflex-dev/reflex/issues/7071))
- Fix `rx.AdminDash` pages failing with `NoMatchFound` by preserving named route lookup through the application's context middleware. ([#7107](https://github.com/reflex-dev/reflex/issues/7107))
- Give forked backend workers distinct socket-owner identities so Redis can deliver backend-initiated state updates to clients connected to another worker. ([#7108](https://github.com/reflex-dev/reflex/issues/7108))
- Preserve explicit `bundle_library()` registrations through frontend compilation and automatically bundle imports used by initial-state components. Explicitly registered component subpaths can first appear after an event, and initial components such as Lucide icons no longer need a separate registration. ([#7109](https://github.com/reflex-dev/reflex/issues/7109))

### Performance

- Clear auto-memoization naming caches after compiling app. ([#6947](https://github.com/reflex-dev/reflex/issues/6947))
- New opt-in dev-server knobs: `REFLEX_DEV_PROD_REACT=1` serves React's production build under the Vite dev server (navigation CPU on a large app 54 → 36 ms, prod build 24 ms; edits become a full reload since Fast Refresh needs dev React), and `REFLEX_VITE_WARMUP_ROUTES=1` pre-transforms route modules at startup so the first visit to a page no longer waits on Vite (105–131 → 43–69 ms, or 20–32 ms with both). ([#7021](https://github.com/reflex-dev/reflex/issues/7021))
- Trimmed the framework overhead around every event handler: the state fast-paths its own bookkeeping attributes, foreground handler tasks start eagerly on Python 3.12+, the computed-var expiry check only looks at interval vars, route matching is memoized per path, and socket.io handlers run inline. About 28% less CPU per trivial event and 20% more events per second per worker under concurrent load. ([#7025](https://github.com/reflex-dev/reflex/issues/7025))
- Reduce CLI startup time by loading component and cloud command implementations only when invoked, and avoid frontend package reinstalls after backend-only config changes. ([#7050](https://github.com/reflex-dev/reflex/issues/7050))
- Avoid repeated PyPI requests by caching successful latest-version checks for 24 hours and throttling failed checks for one hour. ([#7050](https://github.com/reflex-dev/reflex/issues/7050))

### Miscellaneous

- Allow `wrapt` 2.2 and 2.3. ([#7019](https://github.com/reflex-dev/reflex/issues/7019))


## v0.9.10 (2026-09-01)

### Bug Fixes

- Shared state updates now reach linked clients connected to other backend instances — the fan-out previously skipped any client whose websocket was not connected to the instance processing the event, so with redis and multiple workers only same-instance clients received live updates. ([#6934](https://github.com/reflex-dev/reflex/issues/6934))
- Allow static IDs on document-root head components without generating React hooks. ([#7005](https://github.com/reflex-dev/reflex/issues/7005))


## v0.9.9 (2026-08-28)

### Breaking Changes

- `pip install reflex` no longer installs `pydantic`; pydantic model support activates when it is installed. Use the new `reflex[pydantic]` extra (or `reflex[db]`) to keep it. ([#6786](https://github.com/reflex-dev/reflex/issues/6786))
- The compiled frontend now targets React Router 8.3.0 (from 7.18.2), and Reflex requires Node 22.22.0 or newer as a result. Apps on the default generated setup need no `rxconfig.py` or app code changes. One change is required if you wrote a custom component against `react-router-dom`: that package no longer exists upstream and is no longer installed, so `library = "react-router-dom"` must become `react-router` (or `react-router/dom` for `RouterProvider`/`HydratedRouter`). ([#6854](https://github.com/reflex-dev/reflex/issues/6854))
- A `RegistrationContext` can only be associated with a single `App` instance, so creating a second bare `rx.App()` in one process now raises `ReflexRuntimeError` (0.9.8 allowed it); use a fresh `RegistrationContext` (e.g. `RegistrationContext.fork()`) to create multiple apps. ([#6382](https://github.com/reflex-dev/reflex/issues/6382))

### Deprecations

- `reflex.components.dynamic.bundled_libraries` and `DEFAULT_BUNDLED_LIBRARIES` are deprecated (removal in 1.0) but keep working, resolving against the active `RegistrationContext`. Use `RegistrationContext.ensure_context().bundled_libraries` to read the list, or `bundle_library()` / `reset_bundled_libraries()` to modify it. ([#6967](https://github.com/reflex-dev/reflex/issues/6967))
- `reflex.page.DECORATED_PAGES` is deprecated (removal in 1.0) but keeps working, resolving to a mapping of the app name to the active `RegistrationContext`'s page registrations. Use `RegistrationContext.ensure_context().decorated_pages` instead. ([#6985](https://github.com/reflex-dev/reflex/issues/6985))

### Features

- The current `App`, the loaded `Config`, `@rx.page` registrations, and the bundled-library registry are now scoped to the active `RegistrationContext` instead of module-level globals, so multiple apps (and test harnesses) can coexist in one process without leaking registrations into each other. ([#6382](https://github.com/reflex-dev/reflex/issues/6382))
- Report state deltas the frontend cannot process back to the backend via a new `client_error` socket event, logging an actionable error in the terminal instead of failing silently. A frontend/backend state mismatch is fatal for the session: further events stop until the page is reloaded after the frontend is rebuilt or `api_url` is corrected. ([#6827](https://github.com/reflex-dev/reflex/issues/6827))
- Framework logging now flows through standard python `logging` with per-module loggers (`reflex_base.utils.log`, re-exported as `reflex.utils.log`), bootstrapped on `import reflex`. Rich colored output is preserved, and `REFLEX_LOG_JSON` emits machine-readable JSON-lines records. `--loglevel critical` no longer prints the system-info banner. ([#6863](https://github.com/reflex-dev/reflex/issues/6863))
- The reflex CLI accepts `--json` (equivalent to `REFLEX_LOG_JSON`) to emit machine-readable JSON-lines logs. ([#6865](https://github.com/reflex-dev/reflex/issues/6865))
- `reflex deploy` accepts `--min-instances` and `--max-instances` to set the autoscaling bounds of an app deployed to Google Cloud. Omitted bounds are left unchanged. ([#6884](https://github.com/reflex-dev/reflex/issues/6884))
- `reflex deploy` gains `--gcp-connection`, to pick which of your organization's connected GCP accounts an app deploys through; `--full-deploy`, to serve the frontend from the provider's own container instead of Reflex's CDN; and `--strategy`, which was previously only settable in the config file. ([#6908](https://github.com/reflex-dev/reflex/issues/6908))
- Compiled components are now named for React DevTools: memoized components take a `displayName` from the Python class or `@rx.memo` function they came from instead of showing as `Anonymous`, generated contexts are named (`StateContext(reflex___state____state.my_state).Provider` rather than an unlabelled `Context.Provider`), pages are labelled with their route (`Component(blog/[slug])`), and client-only (`NoSSRComponent`) wrappers render as `ClientSide(<Tag>)`. ([#6945](https://github.com/reflex-dev/reflex/issues/6945))

### Bug Fixes

- Stale `on_load` work no longer blocks or outlives a page navigation: a newer navigation for the same client now cancels the previous page's unfinished `on_load` event chain, including `on_load` handlers that are background tasks (`@rx.event(background=True)`), which 0.9.8 let run to completion. Background tasks started from other events are unaffected. ([#6593](https://github.com/reflex-dev/reflex/issues/6593))
- A `[[...splat]]` catchall route no longer matches paths that merely share its prefix — `posts/[[...splat]]` matched `/postsomething` as well as `/posts` and its descendants, so the wrong page's `on_load` events could fire. ([#6790](https://github.com/reflex-dev/reflex/issues/6790))
- Ensure state manager instances use isolated internal locks instead of sharing one lock across instances. ([#6830](https://github.com/reflex-dev/reflex/issues/6830))
- Qualify `dict` annotations on `BaseState` that were shadowed by `BaseState.dict`, so type checkers resolve them to the builtin. ([#6846](https://github.com/reflex-dev/reflex/issues/6846))
- `reflex run` now pre-enables the `development` export condition for the dev server via `NODE_OPTIONS`/`BUN_OPTIONS`, fixing the dev server exiting with `restartWithMergedOptions() was called, but the process has already been restarted` on installs without node, where react-router 8's CLI re-executes itself to set the condition. ([#6857](https://github.com/reflex-dev/reflex/issues/6857))
- An `AppHarnessProd` no longer leaks `REFLEX_ENV_MODE=prod` to dev `AppHarness` instances created later in the same process, which made them compile with route prerendering enabled and drop events dispatched during hydration recovery. ([#6857](https://github.com/reflex-dev/reflex/issues/6857))
- Cache event handler annotations before runtime state-class patches can shadow builtin names on Python 3.14. ([#6890](https://github.com/reflex-dev/reflex/issues/6890))
- `rx.script` head updates now flush synchronously instead of via react-helmet's requestAnimationFrame batching, fixing intermittently missing script tags after hydration (flaky "scripts not loaded" failures). ([#6905](https://github.com/reflex-dev/reflex/issues/6905))
- Fixed a race where a finishing background task could silently discard state updates made by a concurrently running event handler before they reached the frontend, leaving the UI stale until the next write. Background handlers that never enter `async with self` still emit their delta, now computed under the state lock. ([#6920](https://github.com/reflex-dev/reflex/issues/6920))
- `AppHarness` starts the frontend dev server with the `development` export condition enabled, fixing "Frontend did not start" on node-less (bun-only) installs where react-router's dev CLI restart guard trips. ([#6931](https://github.com/reflex-dev/reflex/issues/6931))
- Adding a page no longer raises a spurious `RouteValueError` when a static segment lines up with another route's dynamic segment (e.g. `/posts/all/[x]` alongside `/posts/[id]`). React Router resolves such siblings in favor of the static one, so only two differently named dynamic segments at the same position conflict. The check was also order-dependent: it only tripped when the bracket-carrying route was added second. ([#6953](https://github.com/reflex-dev/reflex/issues/6953))
- Reduce published wheel and sdist size by removing misplaced generated artifacts. ([#6966](https://github.com/reflex-dev/reflex/issues/6966))
- A `client_error` socket emit with no payload no longer raises an unhandled `TypeError` inside python-socketio's dispatch, which let any connected socket — even one without a valid token — spam asyncio tracebacks into the backend logs past the handler's rate limits. ([#6984](https://github.com/reflex-dev/reflex/issues/6984))
- Console warnings and errors no longer print literal backslash-escaped brackets (e.g. `dict\[str, str]`). The rich-markup escapes were left over from the legacy console helpers, but the logging pipeline renders messages with markup disabled, so bracketed type names now print verbatim. `VarAttributeError` messages drop the same escapes. ([#6989](https://github.com/reflex-dev/reflex/issues/6989))
- `reflex run` no longer hangs forever when a fatal error (e.g. the node minimum-version check on the npm path) exits the frontend worker thread while the backend blocks the main thread; the failure now interrupts the main thread and the CLI exits promptly with the original error. ([#6990](https://github.com/reflex-dev/reflex/issues/6990), [#6994](https://github.com/reflex-dev/reflex/issues/6994))

### Performance

- Remove the per-update `asyncio.create_task` wrapper in `EventNamespace.emit_update`, cutting scheduling overhead roughly in half for every outgoing state update. ([#6734](https://github.com/reflex-dev/reflex/issues/6734))
- Dev mode no longer pays for React's per-element owner-stack capture: navigation clicks in a large app dropped from ~350ms to ~83ms of main-thread CPU (5.6x prod down to ~1.3x). In exchange `React.captureOwnerStack()` returns no owner frames in dev, which affects React DevTools' owner-stack view and custom error overlays built on that API; set `REFLEX_REACT_OWNER_STACKS=1` to restore them. ([#6905](https://github.com/reflex-dev/reflex/issues/6905))
- `@rx.memo` components with props bound to state are now auto-memoized at the call site: the state hooks those props need compile into a generated wrapper component instead of the page module. A state change re-renders that wrapper rather than the whole page, and React's `memo` stops there unless one of the prop values actually changed. ([#6949](https://github.com/reflex-dev/reflex/issues/6949))
- The generated `vite.config.js` now declares a hook filter on the plugin that redirects `react-dom/server` to `react-dom/server.node`, so the bundler no longer calls into it for every import in the module graph — on the Reflex docs site that was ~15,800 calls per build to rewrite a single specifier. ([#6959](https://github.com/reflex-dev/reflex/issues/6959))

### Documentation

- Documented the `provider`, `gcp_connection` and `full_deploy` cloud config settings, including which settings a Google Cloud target ignores and why `full_deploy` is left unset rather than false by default. ([#6908](https://github.com/reflex-dev/reflex/issues/6908))

### Miscellaneous

- The generated `package.json` no longer carries a framework-owned `postcss` override; the pinned `postcss` dev dependency already forces a single resolved copy for every transitive requirer. Projects that already installed 0.9.8 keep an inert `"postcss": "8.5.23"` override in `reflex.lock/package.json`; it matches the dev-dependency pin, so it changes nothing today and can be deleted by hand. ([#6854](https://github.com/reflex-dev/reflex/issues/6854))
- Upgrade the locked dev tooling: `ruff` 0.15.12 -> 0.16.2, `pyright` 1.1.408 -> 1.1.411, `typer` 0.25.1 -> 0.27.1. ([#6893](https://github.com/reflex-dev/reflex/issues/6893))
- The `reflex deploy` command implementation moved out of the `reflex` package into `reflex-hosting-cli`, so cloud code is no longer shipped inside the framework. Flags and behavior are unchanged, and `reflex-hosting-cli` remains a dependency of `reflex`, so `reflex deploy` and `reflex cloud` stay available out of the box. If the package is not installed, these commands now report which package to install instead of failing with a missing-command error. ([#6924](https://github.com/reflex-dev/reflex/issues/6924))


## v0.9.8.post1 (2026-08-18)

### Features

- `reflex deploy` accepts `--min-instances` and `--max-instances` to set the autoscaling bounds of an app deployed to Google Cloud. Omitted bounds are left unchanged. ([#6884](https://github.com/reflex-dev/reflex/issues/6884))
- `reflex deploy` gains `--gcp-connection`, to pick which of your organization's connected GCP accounts an app deploys through; `--full-deploy`, to serve the frontend from the provider's own container instead of Reflex's CDN; and `--strategy`, which was previously only settable in the config file. ([#6908](https://github.com/reflex-dev/reflex/issues/6908))

### Documentation

- Documented the `provider`, `gcp_connection` and `full_deploy` cloud config settings, including which settings a Google Cloud target ignores and why `full_deploy` is left unset rather than false by default. ([#6908](https://github.com/reflex-dev/reflex/issues/6908))


## v0.9.8 (2026-08-04)

### Features

- Added content-hash cache busting to `rx.asset` URLs. ([#6550](https://github.com/reflex-dev/reflex/issues/6550))
- Add a `preview` run mode (`reflex run --env preview`) that hot reloads like `dev` but serves a freshly built, un-minified frontend bundle mounted into the backend instead of running the Vite dev server. Minification, CSS minification, autoprefixer, and sourcemaps are disabled by default for faster rebuilds and readable output (each overridable via `VITE_MINIFY`, `REFLEX_NO_AUTOPREFIXER`, and `VITE_SOURCEMAP`). ([#6663](https://github.com/reflex-dev/reflex/issues/6663))
- Support using mutable state proxies as async context managers. ([#6689](https://github.com/reflex-dev/reflex/issues/6689))
- Run plugins' staged `register_route` hooks once per app before page evaluation so plugins can contribute pages atomically, and invalidate the cached route resolver when a page is added after it was first built. ([#6728](https://github.com/reflex-dev/reflex/issues/6728))
- `reflex deploy` now accepts `--provider` (deploy to Reflex Cloud or a GCP account connected to your organization) and `--description` (record an optional changelog note on the deployment, shown in `reflex cloud apps history`).

### Bug Fixes

- Fix `reflex component build` crashing with `AttributeError` on Python 3.10 and 3.11 by delegating recursive stub generation to the Python 3.10-compatible `PyiGenerator` scanner. ([#6760](https://github.com/reflex-dev/reflex/issues/6760))
- Fixed `reflex rename` corrupting or failing on source files on non-UTF-8 platform locales while preserving declared Python source encodings and line endings. ([#6761](https://github.com/reflex-dev/reflex/issues/6761))
- Fixed nested/subfolder stylesheets failing to load on Windows because the generated CSS `@import` used backslash path separators (which CSS treats as escape sequences); the import URL is now always POSIX-normalized. ([#6762](https://github.com/reflex-dev/reflex/issues/6762))
- Process persisted package.json files before mirroring them into the web directory. ([#6765](https://github.com/reflex-dev/reflex/issues/6765))
- Fix production frontend hydration on Windows when the system MIME registry maps JavaScript files to `text/plain`. ([#6831](https://github.com/reflex-dev/reflex/issues/6831))
- Fixed `reflex run` failing with `error: lockfile had changes, but lockfile is frozen` after upgrading to a Reflex version that adds a `package.json` override. Overrides are now applied after the lockfile saved in `reflex.lock/` has been installed, so it is no longer treated as out of date. ([#6844](https://github.com/reflex-dev/reflex/issues/6844))

### Miscellaneous

- Update dev pin Pillow==12.3.0 to avoid various CVE reports ([#6836](https://github.com/reflex-dev/reflex/issues/6836))
- Update locked `aiohttp==3.14.3` and `cryptography==50.0.0`, clearing CVE-2026-59881, CVE-2026-69243, CVE-2026-69244 and CVE-2026-69247. Both are transitive development dependencies of the docs app and are not installed with Reflex. ([#6837](https://github.com/reflex-dev/reflex/issues/6837))


## v0.9.7 (2026-07-15)

### Features

- Added `default_color_mode` to `rx.Config` (`"system"`, `"light"`, or `"dark"`, also settable via `REFLEX_DEFAULT_COLOR_MODE`), so apps can set the initial color mode — and use the built-in color mode switcher and `rx.color_mode_cond` — without pulling in the large Radix themes CSS. The value drives both the compiled `ThemeProvider` default and the pre-hydration preload script, so there is no flash of the wrong theme on first paint. An explicit `rx.theme(appearance=...)` still takes precedence. ([#6716](https://github.com/reflex-dev/reflex/issues/6716))
- `@rx.memo` components now compile with a configurable JS wrapper: React's `memo` remains the default, `wrapper=` swaps in a custom function `Var` whose imports ride along into the generated module, and `wrapper=None` emits the bare function component. ([#6730](https://github.com/reflex-dev/reflex/issues/6730))
- The new `frozen_lockfile` config option is now honored during frontend package installation: when enabled (the default), bun's initial install runs with `--frozen-lockfile` so a lockfile out of sync with `package.json` fails fast. Set `frozen_lockfile=False` to let the lockfile update in place instead. npm has no equivalent install flag today, so the option is a no-op there. ([#6763](https://github.com/reflex-dev/reflex/issues/6763))

### Bug Fixes

- Fix stateful pages being evaluated twice in one process (forked prod workers and same-process export+serve), which created duplicate `ComponentState` classes and broke frontend hydration (`TypeError: d is not a function`). ([#6710](https://github.com/reflex-dev/reflex/issues/6710))
- Reset the disk state manager write queue task after close. ([#6715](https://github.com/reflex-dev/reflex/issues/6715))
- Close the `RedisTokenManager` redis client and cancel its pub/sub background tasks on app shutdown, fixing leaked redis connections (`ResourceWarning: unclosed Connection`) when the server stops. ([#6724](https://github.com/reflex-dev/reflex/issues/6724))
- Event handlers and computed vars inherited from a state mixin now preserve the source function's custom attributes and keyword-only defaults. ([#6725](https://github.com/reflex-dev/reflex/issues/6725))

### Performance

- Run anonymous telemetry collection and delivery on a dedicated single-worker background thread instead of inline on the asyncio event loop. The blocking syscalls, subprocess calls and synchronous HTTP request used to gather and post an event no longer stall the event loop — notably when reporting backend errors at a high rate. Delivery is best-effort and any failure is suppressed, so telemetry can never affect the running app. ([#6626](https://github.com/reflex-dev/reflex/issues/6626))
- Event chaining (`yield OtherState.handler(rows)`) no longer deep-copies payload values that are not attached to any state: only state-bound `MutableProxy` subtrees are copied, making proxy-free payloads ~5x faster to chain. ([#6739](https://github.com/reflex-dev/reflex/issues/6739))
- `Var.to()` and `Var.guess_type()` resolve their target Var subclass through cached registry lookups instead of scanning the full registry with `safe_issubclass` on every call. ([#6742](https://github.com/reflex-dev/reflex/issues/6742))


## v0.9.6 (2026-06-25)

### Features

- Auto-memoized (`rx.memo`) components now compile to `.web/app_components/` output paths that mirror their defining Python source module (using the real package name, including framework packages) instead of being bundled into a single shared `components.jsx`. The compiler's auto-memo registry is scoped per source module, so identical-rendering subtrees in different modules each emit their own output instead of one silently overwriting another, hot-reloads of a module refresh the correct output, and stale memo files are cleaned up when their source changes. Memos whose module can't be mirrored (`__main__`, unsafe names) fall back to one file per memo at `.web/utils/components/<name>.jsx`. Each mirrored memo's generated export name also carries a stable per-module suffix, so two memos that share a name in different modules compile to distinct symbols and can be used together on one page without colliding. ([#6457](https://github.com/reflex-dev/reflex/issues/6457))
- `rx._x.hybrid_property` now works on dataclasses, pydantic models and SQLAlchemy models, not just `State` classes. Accessing the property through an object var on the frontend (e.g. `State.info.a_b`) renders it as a var, using the same code you already use on the backend. ([#6617](https://github.com/reflex-dev/reflex/issues/6617))
- `reflex init` now writes a Reflex-managed section into `AGENTS.md` (fetched from the canonical source and delimited by markers that preserve surrounding user content), and bridges it for Claude Code by creating a `CLAUDE.md` importing `@AGENTS.md` — or, if a `CLAUDE.md` exists without the import, managing the section there directly. ([#6620](https://github.com/reflex-dev/reflex/issues/6620))
- `rx._x.hybrid_property` now raises a clear error when its frontend logic reads a backend (underscore-prefixed) state var, instead of silently baking the var's server-side default into the frontend. Reference a regular var, or provide a separate frontend implementation with `@<name>.var`. ([#6621](https://github.com/reflex-dev/reflex/issues/6621))

### Bug Fixes

- Sync `reflex.lock/package.json` to `.web/package.json` before installing packages to ensure lock file and package.json are aligned. ([#6658](https://github.com/reflex-dev/reflex/issues/6658))
- Avoid re-entering config loading when a `State` subclass is defined in `rxconfig.py`. ([#6662](https://github.com/reflex-dev/reflex/issues/6662))
- Raise minimum dependency versions to pull in security fixes: `starlette>=1.3.1` (Host-header path poisoning, `request.form()` DoS, and UNC-path SSRF), `python-multipart>=0.0.32` (quadratic-time querystring DoS, unbounded header field size, and negative `Content-Length` buffering in `parse_form`), and `granian>=2.7.4` (WSGI and WebSocket header-panic DoS). ([#6665](https://github.com/reflex-dev/reflex/issues/6665))
- Fixed `modify_state` to rebind `EventContext.token` to the token being modified, so delta resolution and computed vars inside shared-state fan-out tasks observe the correct client token rather than the triggering event's inherited context. ([#6673](https://github.com/reflex-dev/reflex/issues/6673))


## v0.9.5.post2 (2026-06-10)

### Bug Fixes

- Allow access to State from `app_wrap` components ([#6651](https://github.com/reflex-dev/reflex/issues/6651))

## v0.9.5.post1 (2026-06-10)

### Bug Fixes

- Bumped minimum `reflex-components-core` dependency to 0.9.5 for compatibility.

## v0.9.5 (2026-06-10)

### Features

- `rx.form` `on_submit` handlers can now annotate their form-data parameter with a `TypedDict` (including `typing_extensions.NotRequired` fields). The submitted mapping is accepted by the event-argument type checker, and at component build time the form statically validates that its controls supply every required `TypedDict` field, raising `EventHandlerValueError` — with the missing and present field names — when a required field has no control with a matching static `name`/`id`. Validation is skipped when the form sets an `id` (controls may be associated externally via the HTML `form` attribute) or when any control identifier is a dynamic `Var`. ([#6301](https://github.com/reflex-dev/reflex/issues/6301))
- Event handlers attached to JSX literals built outside a component's render scope — such as an `ErrorBoundary`'s `onError` — can now dispatch events. `addEvents` is reached through a module-level import that `EventLoopProvider` populates on each render, so dispatch no longer depends on a `useContext` hook being hoisted into the calling scope. The state and event-loop providers, previously hard-coded in the layout template, are now injected around the app root by the compiler from the `app_wraps` declared on the `Var`s that use them. ([#6447](https://github.com/reflex-dev/reflex/issues/6447))
- Added `App.hydrate_fallback`, a component rendered during the page's hydration window (React Router's `HydrateFallback`) instead of a blank white page. It can also be configured without code through the `hydrate_fallback` config — a dotted import path to a no-arg callable returning a component, settable via the `REFLEX_HYDRATE_FALLBACK` environment variable — with the `App` argument taking precedence. Note that the fallback only covers the hydration window after the JS bundle has loaded, not the initial bundle download. ([#6630](https://github.com/reflex-dev/reflex/issues/6630))
- Added the `REFLEX_HOT_RELOAD_OVERRIDE_PATHS` environment variable, a colon-separated list of paths that, when set, fully replaces the paths watched for hot reload in dev mode — taking precedence over the config-derived defaults as well as `REFLEX_HOT_RELOAD_INCLUDE_PATHS` and `REFLEX_HOT_RELOAD_EXCLUDE_PATHS`. ([#6639](https://github.com/reflex-dev/reflex/issues/6639))

### Bug Fixes

- Anonymous telemetry now reports the installation and project identifiers as UUID strings rather than 128-bit integers. PostHog coerced the large integers to floats, discarding all but ~16 significant digits and risking distinct installs or apps being correlated as one. Each identifier is re-encoded to the same value (a UUID carries the same 128 bits), and a one-time PostHog `$create_alias` links an installation's pre-existing history to its new identifier so continuity is preserved. ([#6611](https://github.com/reflex-dev/reflex/issues/6611))
- `scripts/make_pyi.py` is now a proper CLI for maintaining `pyi_hashes.json`: `--force` regenerates every default target (ignoring the incremental markers), explicit targets are merged into the registry instead of pruning it, and an unreachable last-run commit (after a branch switch or rebase) triggers a full regeneration. A new `--check` mode, wired into the pre-commit CI job, fails when a `pyi_hashes.json` entry no longer has a matching `.py` source. ([#6614](https://github.com/reflex-dev/reflex/issues/6614))
- `State.get_var_value()` no longer silently returns a wrong value when passed a Var operation — an arithmetic/concatenation expression such as `State.a + State.b`, or an indexed/item access such as `State.items[0]`. Previously it resolved the state and field of the operation's *first* operand and returned that field's value instead of the operation's result. It now raises `UnretrievableVarValueError`, consistent with how it already handled vars not associated with any state. Plain field and computed-var references continue to resolve as before. ([#6633](https://github.com/reflex-dev/reflex/issues/6633))

### Performance

- Speed up reading mutable state vars (lists, dicts, dataclasses) through `MutableProxy`. The per-element check that detects `dataclasses.asdict`/`astuple` recursion now reads `frame.f_code.co_filename` directly instead of calling `inspect.getfile()`, cutting proxy read overhead by roughly 3-4x on large containers without changing behavior. ([#6600](https://github.com/reflex-dev/reflex/issues/6600))

### Miscellaneous

- Report the versions of the first-party Reflex subpackages shipped with Reflex (`reflex-base`, the `reflex-components-*` family and `reflex-hosting-cli`) in anonymous telemetry via a new `reflex_package_version` field. The set is derived from Reflex's own declared dependencies, so unrelated third-party `reflex-*` packages are never reported. Now that Reflex is split across many independently-versioned packages, the single `reflex_version` field no longer reflects the full install. ([#6610](https://github.com/reflex-dev/reflex/issues/6610))


## v0.9.4 (2026-06-03)

### Deprecations

- `rx._x.memo` is deprecated in favor of `rx.memo`. The old name remains a working alias for now; update imports to use `rx.memo` directly. ([#6517](https://github.com/reflex-dev/reflex/issues/6517))
- `@rx.memo` now expects each parameter to be annotated as `rx.Var[...]` (or `rx.RestProp`/`rx.EventHandler`) and the function to declare an `rx.Component` or `rx.Var[...]` return type. Memos that still use bare Python types (e.g. `name: str`) or omit the return annotation keep working — the values are coerced to `rx.Var[...]`/`rx.Component` and a deprecation warning points at the parameters and return type that need explicit annotations — but this fallback will be removed in 1.0. ([#6598](https://github.com/reflex-dev/reflex/issues/6598))

### Features

- Added `rx._x.hybrid_property`, a property decorator usable on State classes that works like a normal Python property for backend access while also rendering on the frontend at class level. Use the same method for both, or register a separate frontend implementation with `@<name>.var`. ([#3806](https://github.com/reflex-dev/reflex/issues/3806))
- Promoted the component memo system to a first-class `rx.memo` API. Memo-decorated components now accept `rx.EventHandler` parameters and carry annotated return types so they type-check correctly at call sites. ([#6517](https://github.com/reflex-dev/reflex/issues/6517))
- Added `rx.EMPTY_VAR_COMPONENT`, an empty-component `rx.Var[rx.Component]` sentinel for use as a default on `@rx.memo` `children` slots (and any `rx.Var[rx.Component]` prop) — the component counterpart to `rx.EMPTY_VAR_STR` and `rx.EMPTY_VAR_INT`. ([#6598](https://github.com/reflex-dev/reflex/issues/6598))
- `@rx.memo` now evaluates the decorated function body lazily — on first use (component instantiation) or at compile time — instead of at import time. This speeds up startup and lets a memo reference modules that aren't fully imported yet, sidestepping circular-import errors during decoration. Body-dependent errors (e.g. a var-returning memo that uses hooks or non-bundled imports) now surface when the memo is first used or compiled rather than at import. ([#6598](https://github.com/reflex-dev/reflex/issues/6598))

### Miscellaneous

- Introduced towncrier-based changelog management. Each PR that changes package source now adds a fragment under the affected package's `news/` directory; fragments are assembled into `CHANGELOG.md` at release time. See CONTRIBUTING.md for the full workflow. ([#6350](https://github.com/reflex-dev/reflex/issues/6350))
- Removed the "choose templates" option from `reflex init`. The interactive prompt now offers only a blank app or the AI builder, and no longer opens the open-source templates page. ([#6592](https://github.com/reflex-dev/reflex/issues/6592))
