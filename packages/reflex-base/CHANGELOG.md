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
