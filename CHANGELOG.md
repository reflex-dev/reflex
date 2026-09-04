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
