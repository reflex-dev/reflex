## v0.9.9.post1 (2026-09-01)

### Deprecations

- `reflex_base.config._load_config()` is deprecated in favor of `_get_config()`; use `get_config()` to read the cached config. ([#6933](https://github.com/reflex-dev/reflex/issues/6933))

### Bug Fixes

- Avoid ModuleNotFoundError when loading `rxconfig.py` in a multi-threaded context. ([#6933](https://github.com/reflex-dev/reflex/issues/6933))


## v0.9.9 (2026-08-28)

### Breaking Changes

- `get_config(reload=True)` has been replaced by `reload_config()`, and the module-level `bundled_libraries` list in `reflex_base.components.dynamic` has moved onto the active `RegistrationContext` (use `bundle_library()` / `reset_bundled_libraries()` as before). Reading `reflex_base.components.dynamic.bundled_libraries` (or `DEFAULT_BUNDLED_LIBRARIES`) still works as a deprecated shim that resolves against the active context; the shims are removed in 1.0. ([#6382](https://github.com/reflex-dev/reflex/issues/6382))
- `pydantic` is no longer a hard dependency; pydantic model support activates when it is installed. Use the `reflex-base[pydantic]` extra (or `reflex[db]`) to keep it. ([#6786](https://github.com/reflex-dev/reflex/issues/6786))
- Upgraded the frontend to React Router 8.3.0 (from 7.18.2). Its new baseline requires Node 22.22.0+, so `Node.MIN_VERSION` moves from 22.12.0 to 22.22.0; the already-pinned React 19.2.8 and Vite 8.0.16 satisfy the React 19.2.7+ and Vite 7+ floors. React Router 8 dropped the `react-router-dom` re-export package, so it is no longer installed: components that declare `library = "react-router-dom"` must import from `react-router` instead (`RouterProvider`/`HydratedRouter` come from `react-router/dom`). Existing projects have the stale entry pruned from `package.json` on the next install. ([#6854](https://github.com/reflex-dev/reflex/issues/6854))

### Deprecations

- The `console.debug/info/success/log/warn/error/timing` helpers are deprecated (removal in 1.0) but keep working as shims; use `logging.getLogger(__name__)` and the pipeline in `reflex_base.utils.log` instead. The interactive Rich features (`print`/`rule`/`status`/`ask`/`progress`) remain first-class. ([#6867](https://github.com/reflex-dev/reflex/issues/6867))
- `get_config(reload=True)` is deprecated (removal in 1.0) but keeps working: passing `reload=True` emits a deprecation warning and delegates to `reload_config()`, which forces a fresh load of the config into the current `RegistrationContext`. ([#6985](https://github.com/reflex-dev/reflex/issues/6985))

### Features

- `RegistrationContext` now carries the loaded `Config`, the registered `App`, decorated pages, and bundled libraries, and provides `fork()` to derive a fresh context that preserves existing registrations while resetting the app and config. ([#6382](https://github.com/reflex-dev/reflex/issues/6382))
- Validate incoming state deltas in the frontend before dispatching and report unprocessable updates to the backend via a new `client_error` socket event instead of failing silently in the browser console. Values reported by a client are escaped and bounded before reaching the backend logs. ([#6827](https://github.com/reflex-dev/reflex/issues/6827))
- Added `reflex_base.utils.log`: a standard python logging pipeline with a rich-rendering console handler (legacy colors preserved), a JSON-lines handler behind `REFLEX_LOG_JSON`, record deduplication, and file logging. `LogLevel` gained a correct total ordering and `to_logging_level()`, and the interactive console helpers (`print`/`rule`/`status`/`progress`) now respect JSON mode. ([#6863](https://github.com/reflex-dev/reflex/issues/6863))
- Compiled components are now named for React DevTools: memoized components take a `displayName` from the Python class or `@rx.memo` function they came from instead of showing as `Anonymous`, generated contexts are named (`StateContext(reflex___state____state.my_state).Provider` rather than an unlabelled `Context.Provider`), pages are labelled with their route (`Component(blog/[slug])`), and client-only (`NoSSRComponent`) wrappers render as `ClientSide(<Tag>)`. ([#6945](https://github.com/reflex-dev/reflex/issues/6945))
- Add the `REFLEX_REFERRER_PARAM` environment variable, read at compile time to append a `ref` query parameter to the "Built with Reflex" badge link. ([#6951](https://github.com/reflex-dev/reflex/issues/6951))

### Bug Fixes

- Event handlers marked with `@rx.event(supersedes=True)` now use latest-wins semantics: enqueuing a new invocation cancels the previous unfinished event chain for the same client token. `on_load_internal` uses this to cancel stale `on_load` chains on navigation. ([#6593](https://github.com/reflex-dev/reflex/issues/6593))
- `@rx.memo` functions that forward props through `rx.RestProp` now classify those props the same way a regular component does: a forwarded prop that is not a declared prop of the target (e.g. `font_weight=`) joins the component's `style` and renders as `css`, instead of being passed through as an unrecognized prop and silently dropped. Such props merge with an explicit `style=` rather than replacing it, and props the target actually declares are still forwarded normally. ([#6605](https://github.com/reflex-dev/reflex/issues/6605))
- Declare `rx.plugins.RadixThemesPlugin()` in the `rxconfig.py` written by `reflex init`, so freshly scaffolded apps no longer emit the implicit Radix Themes enablement deprecation warning. ([#6776](https://github.com/reflex-dev/reflex/issues/6776))
- Qualify annotations whose bare builtin name is shadowed by a member of the same class, so `Var.create` is no longer inferred as `LiteralBooleanVar` for every argument type. `Var.bool`, `BaseComponent.set` and `PropsBase.dict` shadowed `bool`, `set` and `dict` for annotations elsewhere in their own class bodies, which type checkers resolve against the class namespace. ([#6846](https://github.com/reflex-dev/reflex/issues/6846))
- The `vite preview` server that react-router prerendering fetches pages from is now pinned to `127.0.0.1`, fixing `reflex export` failing with `Prerender: Request failed for /: ECONNREFUSED` in environments where `localhost` resolves to both IPv4 and IPv6 loopback addresses (such as docker containers). ([#6857](https://github.com/reflex-dev/reflex/issues/6857))
- Resolve event handler annotations before runtime state-class patches can shadow builtin names on Python 3.14. ([#6890](https://github.com/reflex-dev/reflex/issues/6890))
- Chained events (those yielded by an event handler) now inherit the routing data of the event being processed, so `router` and dynamic route args resolve against the view that produced them instead of whichever view the last client-sent event left on the root state. ([#6919](https://github.com/reflex-dev/reflex/issues/6919))
- Stop background event handlers from computing a delta and cleaning the root state after the state lock is dropped. On a shared state tree (opportunistic locking, in-memory state manager) a concurrent foreground write landing between the background task's dirty-var snapshot and its `_clean()` was silently discarded and never reached any delta. ([#6920](https://github.com/reflex-dev/reflex/issues/6920))
- Resolve `TypeAliasType` annotations (PEP 695 `type` statements and the `typing_extensions` backport) to their underlying value in `Var.guess_type`, `_isinstance` and `typehint_issubclass`. A state var annotated with an alias like `type Key = Literal["day", "week"]` now compiles and can be assigned to, and event handlers with alias-annotated arguments can be passed uncalled to event triggers. Parameterized generic aliases (`Keys[str]` for `type Keys[T] = list[T]`) and aliases nested in unions (`Key | None`) are resolved as well. ([#6944](https://github.com/reflex-dev/reflex/issues/6944), [#6986](https://github.com/reflex-dev/reflex/issues/6986))
- The generated `vite.config.js` no longer passes options rejected or deprecated by rolldown-vite 8.x: the no-op `rollupOptions.jsx` key is dropped and `output.advancedChunks` migrated to `output.codeSplitting` (same shape), removing the "Invalid input options" and "advancedChunks option is deprecated" warnings from every prod build/export. ([#6987](https://github.com/reflex-dev/reflex/issues/6987))
- Console warnings and errors no longer print literal backslash-escaped brackets (e.g. `dict\[str, str]`). The rich-markup escapes were left over from the legacy console helpers, but the logging pipeline renders messages with markup disabled, so bracketed type names now print verbatim. `VarAttributeError` messages drop the same escapes. ([#6989](https://github.com/reflex-dev/reflex/issues/6989))
- A custom component declaring `library = "react-router-dom"` (including versioned and subpath forms) now fails compilation with an actionable error naming the component, instead of silently installing the removed package — which pulled in a second, unpinned React Router 7 copy that worked in dev by accident and broke production builds. React Router 8 dropped `react-router-dom`: use `library = "react-router"` instead, or `"react-router/dom"` for `RouterProvider`/`HydratedRouter`. ([#6991](https://github.com/reflex-dev/reflex/issues/6991))
- With `REFLEX_ENABLE_FULL_LOGGING`, granian worker records reach the log file again: the file handler now opens in append mode (truncating once up front), so it reopens after the worker's post-fork `logging.config.dictConfig` closes it instead of silently dropping every worker-side record. The legacy console file writer follows the reopened stream through a proxy, so its timestamped lines no longer leak to stdout and break `--json` output. ([#6992](https://github.com/reflex-dev/reflex/issues/6992))

### Performance

- Dev mode no longer pays for React's per-element owner-stack capture: navigation clicks in a large app dropped from ~350ms to ~83ms of main-thread CPU (5.6x prod down to ~1.3x). In exchange `React.captureOwnerStack()` returns no owner frames in dev, which affects React DevTools' owner-stack view and custom error overlays built on that API; set `REFLEX_REACT_OWNER_STACKS=1` to restore them. ([#6905](https://github.com/reflex-dev/reflex/issues/6905))
- `MemoComponent` instances no longer opt out of compiler auto-memoization wholesale. Only the passthrough wrappers the auto-memoize pass generates do, tracked by the new `auto_memo_wrapper` flag on `MemoComponentDefinition`, so state-bound props and event handlers on a `@rx.memo` call site compile their hooks into a generated wrapper instead of the enclosing page. ([#6949](https://github.com/reflex-dev/reflex/issues/6949))
- Speed up prop validation and JSON serialization on hot paths: `_isinstance` now reads `__origin__` once per type, memoizes `get_args`, and caches the deferred `Var`/`LiteralVar`/`Field` imports instead of re-importing on every call, and `json_dumps` caches its deferred `serializers.serialize` lookup. ([#6862](https://github.com/reflex-dev/reflex/issues/6862))
- `vite_config_template` declares a `resolveId` hook filter (`{ id: /react-dom\/server/ }`) on `vite-plugin-always-use-react-dom-server-node`. The plugin runs with `enforce: "pre"`, so without a filter rolldown invoked its JS handler for every import specifier in the graph (~15,800 calls on the Reflex docs build) to redirect the one specifier imported by `entry.server.node.tsx`. The template also imports `./vite-plugin-safari-cachebust.js` with its extension, which Vite's `configLoader: "native"` requires. ([#6959](https://github.com/reflex-dev/reflex/issues/6959))

### Miscellaneous

- Removed the `postcss` entry from `PackageJson.OVERRIDES`, leaving that mapping empty. `postcss` is pinned directly in `DEV_DEPENDENCIES` (8.5.23), and that top-level pin already dedupes every transitive requirer (`autoprefixer`, `postcss-import`, and `vite`'s own `^8.5.15`). Projects that already installed 0.9.8 keep an inert `"postcss": "8.5.23"` override in `reflex.lock/package.json`; it matches the dev-dependency pin and can be deleted by hand. ([#6854](https://github.com/reflex-dev/reflex/issues/6854))
- Bump bundled `vite` from 8.0.16 to 8.2.0. ([#6857](https://github.com/reflex-dev/reflex/issues/6857))
- Internal logging in reflex-base migrated from the legacy console helpers to standard python `logging` per-module loggers. ([#6864](https://github.com/reflex-dev/reflex/issues/6864))
- Property docstrings are now noun phrases rather than "Get the ..." / "Return the ..." (ruff 0.16's new `D421`). `Field.default`, `Field.default_factory` and `Field.default_value()` now admit `None`, matching what they already hold for a field whose annotated type has no computed default, and `chain_updates()` declares its `events` parameter as `Any`, matching the runtime validation it delegates to. ([#6893](https://github.com/reflex-dev/reflex/issues/6893))


## v0.9.8 (2026-08-04)

### Features

- Add `Env.PREVIEW`, the `VITE_MINIFY` and `REFLEX_NO_AUTOPREFIXER` environment variables, a `minify`/`cssMinify` option on the vite config template, and a `REFLEX_NO_AUTOPREFIXER` toggle in the generated `postcss.config.js` to support the new `preview` run mode. ([#6663](https://github.com/reflex-dev/reflex/issues/6663))
- Add a staged `Plugin.register_route` hook with `add_page` and `has_app_page` capabilities that runs once per app before its first compilation, and `rx.plugins.get_plugin()` to look up the configured plugin instance by type (raising `ConfigError` on ambiguous matches). ([#6728](https://github.com/reflex-dev/reflex/issues/6728))

### Bug Fixes

- Preserve runtime value types for unannotated `@rx.memo` component parameters. ([#6659](https://github.com/reflex-dev/reflex/issues/6659))
- Compare timezone-aware datetime Vars by their instants instead of their serialized UTC offsets. ([#6767](https://github.com/reflex-dev/reflex/issues/6767))
- In python 3.13+, the EventProcessor loop was not catching asyncio.QueueShutdown resulting in uncaught exceptions during shutdown. ([#6773](https://github.com/reflex-dev/reflex/issues/6773))
- Prevented edits to unloaded routes from poisoning React Router's browser-side HMR queue and blocking all later hot updates until a full page reload. ([#6774](https://github.com/reflex-dev/reflex/issues/6774))
- Drain queued same-token events during graceful event processor shutdown. ([#6791](https://github.com/reflex-dev/reflex/issues/6791))
- Custom attributes on a `Field` are now carried onto the rebuilt field by reference instead of deep copy, so stateful callable markers keep their identity and markers holding non-copyable values (locks, clients) no longer crash state class creation. ([#6809](https://github.com/reflex-dev/reflex/issues/6809))

### Miscellaneous

- Bumped bundled frontend dependency pins to their current releases:

  - `react` / `react-dom`: 19.2.6 → 19.2.8
  - `react-router`, `react-router-dom`, `@react-router/node`, `@react-router/dev`, `@react-router/fs-routes`: 7.15.0 → 7.18.2
  - `isbot`: 5.1.40 → 5.2.1
  - `universal-cookie`: 7.2.2 → 8.1.2
  - `postcss`: 8.5.14 → 8.5.23
  - `autoprefixer`: 10.5.0 → 10.5.4
  - `@tailwindcss/typography`: 0.5.19 → 0.5.20
  - Bun: 1.3.13 → 1.3.14

  Also raised the `rich` upper bound to `<16` (adopting rich 15). Replaced the now-redundant `cookie` `package.json` override (`universal-cookie` 8 and `react-router` resolve `cookie` to 1.x on their own) with a `postcss` override pinning it to 8.5.23 so transitive resolutions stay on a patched release (>= 8.5.18) for a security advisory.

  ([#6678](https://github.com/reflex-dev/reflex/issues/6678))
- Remove the unused `REFLEX_USE_TURBOPACK` environment variable. Turbopack is a Next.js bundler; the flag has had no effect since Reflex moved to React Router and Vite in 0.8. ([#6803](https://github.com/reflex-dev/reflex/issues/6803))


## v0.9.7 (2026-07-15)

### Deprecations

- `ArrayVar.foreach` is deprecated; use `ArrayVar.map` instead. ([#6701](https://github.com/reflex-dev/reflex/issues/6701))

### Features

- `ArrayVar` gained `map`, `filter`, `reduce`, and `flat_map` operations, and `StringVar.strip` now accepts a `chars` argument alongside new `lstrip`/`rstrip` methods. ([#6701](https://github.com/reflex-dev/reflex/issues/6701))
- Added `default_color_mode` to `rx.Config` (`"system"`, `"light"`, or `"dark"`, also settable via `REFLEX_DEFAULT_COLOR_MODE`) and moved the shared `LiteralColorMode` type and color-mode string constants into `reflex_base.constants`. This lets apps set the initial color mode without depending on the Radix themes appearance prop. ([#6716](https://github.com/reflex-dev/reflex/issues/6716))
- `@rx.memo` now accepts a `wrapper=` argument controlling the JS function that wraps the compiled component definition: keep the default React `memo`, pass a custom function `Var` (e.g. an `rx.vars.FunctionStringVar` carrying its own imports), or pass `wrapper=None` to export the bare function component. ([#6730](https://github.com/reflex-dev/reflex/issues/6730))
- Added `frozen_lockfile` to `rx.Config` (default `True`, also settable via `REFLEX_FROZEN_LOCKFILE`), controlling whether the frontend package manager runs in lockfile-enforcing mode. Reflex still creates, manages, and syncs the lockfile regardless; the option only controls whether a lockfile/`package.json` mismatch is treated as an error. ([#6763](https://github.com/reflex-dev/reflex/issues/6763))

### Bug Fixes

- Custom attributes set on a `Field` are now preserved (deep-copied) when the state metaclass rebuilds fields, instead of being silently discarded. The reserved `annotation` attribute is never carried over so rebuilt fields are not misidentified as pydantic fields. ([#6726](https://github.com/reflex-dev/reflex/issues/6726))
- Fix `_get_all_hooks_internal` mutating each component's cached internal hooks with its descendants' hooks, which made memo tag hashes order-dependent and duplicated hooks into memo bodies. ([#6741](https://github.com/reflex-dev/reflex/issues/6741))

### Performance

- Cache framework-path checks in `console.deprecate`'s call-stack walk, making repeat calls ~150x faster (deprecated attributes on hot paths, like `RouterData.page`, no longer cost multiple milliseconds per access). ([#6736](https://github.com/reflex-dev/reflex/issues/6736))
- Event chaining (`yield OtherState.handler(rows)`) no longer deep-copies payload values that are not attached to any state: only state-bound `MutableProxy` subtrees are copied, making proxy-free payloads ~5x faster to chain. ([#6739](https://github.com/reflex-dev/reflex/issues/6739))
- `Var.to()` and `Var.guess_type()` resolve their target Var subclass through cached registry lookups instead of scanning the full registry with `safe_issubclass` on every call (~70% of the cost of constructing a var operation). ([#6742](https://github.com/reflex-dev/reflex/issues/6742))


## v0.9.6.post1 (2026-06-26)

### Features

- Added the `REFLEX_EXTRA_PLUGINS` environment variable, a colon-separated list of fully qualified plugin import paths appended to the config's `plugins` list. Unlike `REFLEX_PLUGINS`, which replaces the list entirely, this preserves plugins configured in `rxconfig.py`; an entry is skipped when a plugin of the same type is already present or when its type is listed in `disable_plugins`. ([#6685](https://github.com/reflex-dev/reflex/issues/6685))

### Bug Fixes

- Stop warning when a non-built-in plugin is listed in `disable_plugins`, so config can opt out of an env-provided plugin without a spurious warning. ([#6685](https://github.com/reflex-dev/reflex/issues/6685))
- Improve error message when plugin spec from environment cannot be used. ([#6685](https://github.com/reflex-dev/reflex/issues/6685))


## v0.9.6 (2026-06-25)

### Features

- `StringVar` now includes `lstrip` and `rstrip` methods. The `strip` method now accepts an optional `chars` argument for consistency with Python’s str API. ([#5417](https://github.com/reflex-dev/reflex/issues/5417))
- Added `reflex_base.utils.memo_paths`, which translates a memo's Python source module into the mirrored `.web/app_components/` JSX path and `$/...` library specifier used by the compiler. The memo component and compiler plugin now route each memo's compiled output through these helpers so it lands alongside its source module's layout, falling back to the per-name `utils/components/<name>` path when the module can't be mirrored. The helpers also derive a per-module-unique JS symbol for each mirrored memo, and the memo registry is keyed by `(name, source module)` so same-named memos defined in different modules coexist instead of colliding. ([#6457](https://github.com/reflex-dev/reflex/issues/6457))
- `ObjectVar` attribute access now resolves `HybridProperty` descriptors defined on the underlying type, evaluating the property's frontend logic with the object var substituted as `self`. `HybridProperty` moved to `reflex_base.vars.hybrid_property` (still available as `rx._x.hybrid_property`). ([#6617](https://github.com/reflex-dev/reflex/issues/6617))
- Add `AgentsMd` constants (canonical URL, managed-section markers, and `CLAUDE.md` bridge) supporting `reflex init` AGENTS.md generation. ([#6620](https://github.com/reflex-dev/reflex/issues/6620))
- Added `HybridPropertyError`, raised when a hybrid property's frontend logic accesses a backend (underscore-prefixed) var on a state while building its frontend var. ([#6621](https://github.com/reflex-dev/reflex/issues/6621))
- `package_json_template` accepts `**additional_keys` to include extra fields (e.g. `name`, `packageManager`, `engines`) in the rendered package.json. ([#6658](https://github.com/reflex-dev/reflex/issues/6658))

### Bug Fixes

- Preserve extra bound event arguments when `rx.upload_files` is used in an upload handler. ([#5290](https://github.com/reflex-dev/reflex/issues/5290))
- Avoid re-entering config loading when a `State` subclass is defined in `rxconfig.py`. ([#6662](https://github.com/reflex-dev/reflex/issues/6662))
- Bump the bundled `vite` dev dependency to 8.0.16, fixing a `server.fs.deny` bypass on Windows alternate paths (CVE-2026-53571) in the dev server of generated apps. ([#6665](https://github.com/reflex-dev/reflex/issues/6665))
- `pyi_hashes.json` entries are now computed from the final `.pyi` content after `ruff format` / `ruff check --fix` post-processing, instead of the intermediate generator output. A pyi_generator change that only affects pre-format output no longer flags hash changes for stubs whose final content is identical.

### Miscellaneous

- `Component` gained a private `_get_tag_name()` helper returning the JS expression that references the component's tag (quoted for global-scope DOM tags without a library); `Component._render` and `DebounceInput` now share it instead of duplicating the quoting logic. ([#6637](https://github.com/reflex-dev/reflex/issues/6637))


## v0.9.5 (2026-06-10)

### Features

- Event-argument type checking now treats a mapping-style payload as compatible with a `TypedDict`-annotated callback parameter, scoped narrowly to `on_submit` triggers whose payload is a `Mapping[str, ...]` so unrelated mapping events are unaffected. Adds the `FORM_SUBMIT_MAPPING` type var (exposed on the event namespace and `pyi_generator`'s default imports) and a `Component._is_form_control` class marker that a component sets to declare it contributes a named field to form submission data. ([#6301](https://github.com/reflex-dev/reflex/issues/6301))
- `VarData` gained an `app_wraps` field so a `Var` can declare the app-level wrapper components it requires; the compiler injects them around the app root, deduped by `(priority, tag)`. This is how the state and event-loop providers now reach the React tree, since event dispatch reaches `addEvents` via a module-level import (`Imports.EVENTS`) rather than a hoisted hook. The still-reactive `connectErrors` value moves to its own `CONNECT_ERRORS` import/hook, and `Component` deep copies now drop the render cache so compile-time clones (e.g. the app-root wrapper chain) render their mutated children. ([#6447](https://github.com/reflex-dev/reflex/issues/6447))
- Added a `hydrate_fallback` config option (settable via the `REFLEX_HYDRATE_FALLBACK` environment variable), a dotted import path to a callable returning the component shown while the page is hydrating. The app root template now emits a React Router `HydrateFallback` export when a fallback is provided, and the import-path resolution shared with `extra_overlay_function` resolves nested module paths correctly. ([#6630](https://github.com/reflex-dev/reflex/issues/6630))
- Added the `REFLEX_HOT_RELOAD_OVERRIDE_PATHS` environment variable, a colon-separated list of paths that, when set, fully replaces the paths watched for hot reload in dev mode. ([#6639](https://github.com/reflex-dev/reflex/issues/6639))

### Bug Fixes

- The `reflex_base.utils.pyi_generator` build-hook entrypoint no longer rewrites `pyi_hashes.json`: it only emits the `.pyi` stubs bundled in the wheel, so building a component package (or the build triggered by `uv sync`) no longer wipes the hash registry down to a single package's entries. The scanner also tolerates source-less modules (e.g. an empty `__init__.py`) instead of raising `OSError` on Python < 3.13. ([#6614](https://github.com/reflex-dev/reflex/issues/6614))
- Fixed `State.router.url` reflecting a stale query string after the URL was changed with `window.history.replaceState`/`pushState` (e.g. from `rx.call_script`). React Router's location does not observe direct history manipulation, so the query and hash are now read from the live `window.location` when building `router_data`, and the next event sent to the backend reports the correct URL (the path stays basename-relative so `frontend_path` is not applied twice; embedded apps keep using the in-widget memory router). A direct history mutation is intentionally not a navigation and does not itself emit an event — use `rx.redirect(..., replace=True)` when you need the URL change to update the router reactively and trigger `on_load`. ([#6625](https://github.com/reflex-dev/reflex/issues/6625))
- pyi_generator no longer includes underscore-prefixed props in generated .pyi files. ([#6628](https://github.com/reflex-dev/reflex/issues/6628))
- Frontend-only events (e.g. `rx.toast`, `rx.redirect`) returned from a middleware's `preprocess` are now emitted to the client instead of being enqueued on the backend event queue, where they had no registered handler and raised `KeyError`. The frontend/backend split that already applied to handler-yielded events is now shared via a `_route_events` helper and applied to middleware-preprocess updates too. ([#6644](https://github.com/reflex-dev/reflex/issues/6644))

### Performance

- Speed up component creation by resolving field defaults lazily (via class-level descriptors) instead of eagerly on every instance, caching each component class's event triggers, and memoizing `to_camel_case`. ([#6576](https://github.com/reflex-dev/reflex/issues/6576))


## v0.9.4 (2026-06-03)

### Deprecations

- Component-returning `@rx.memo` again accepts `key` without an `rx.RestProp` (with a deprecation warning), so `rx.foreach` call sites that set the react `key` keep working; this fallback is removed in 1.0. Other base props (`id`, `class_name`, `style`, `custom_attrs`, `ref`) and identity fields like `tag`/`library` still raise — declare an `rx.RestProp` to forward them.

### Features

- Dependency tracking now follows through hybrid properties, so computed vars that read a `hybrid_property` correctly recompute when the underlying state vars change. ([#3806](https://github.com/reflex-dev/reflex/issues/3806))
- The component memo implementation now lives in `reflex_base.components.memo` and is exported as `rx.memo`. Added `EMPTY_VAR_STR` and `EMPTY_VAR_INT` sentinel vars as memo-friendly defaults. ([#6517](https://github.com/reflex-dev/reflex/issues/6517))

### Bug Fixes

- Pin `es-toolkit@1.46.1` via package overrides to work around upstream breakage in recharts and es-toolkit. ([#6570](https://github.com/reflex-dev/reflex/issues/6570))
- Unpin `es-toolkit@1.46.1` via package overrides and bump vite to 8.0.14 to work around upstream breakage in recharts and es-toolkit. ([#6571](https://github.com/reflex-dev/reflex/issues/6571))

### Miscellaneous

- Removed the `Templates.CHOOSE_TEMPLATES` and `Templates.REFLEX_TEMPLATES_URL` constants, which supported the now-removed open-source templates `reflex init` option. ([#6592](https://github.com/reflex-dev/reflex/issues/6592))
