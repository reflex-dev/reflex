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
