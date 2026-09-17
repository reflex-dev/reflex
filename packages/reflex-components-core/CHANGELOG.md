## v0.9.9 (2026-08-28)

### Features

- The "Built with Reflex" badge appends a urlencoded `ref` query parameter to its reflex.dev link when the `REFLEX_REFERRER_PARAM` environment variable is set at compile time. ([#6951](https://github.com/reflex-dev/reflex/issues/6951))

### Bug Fixes

- Sanitize buffered upload filenames the same way streamed upload filenames are sanitized. ([#6753](https://github.com/reflex-dev/reflex/issues/6753))
- `rx.script` head updates now flush synchronously instead of via react-helmet's requestAnimationFrame batching, fixing intermittently missing script tags after hydration (flaky "scripts not loaded" failures). ([#6905](https://github.com/reflex-dev/reflex/issues/6905))
- Upload filenames whose segments contain nothing but dots and spaces (e.g. `".."`, `"./../."`, `".. "`) now sanitize to the fallback name `upload` instead of returning the bare segment. Such names pointed the saved path outside the upload directory — directly on POSIX, and via Win32's trailing dot/space trimming on Windows — and crashed the upload handler with a 500. ([#6971](https://github.com/reflex-dev/reflex/issues/6971))

### Miscellaneous

- Hoist the `RegistrationContext` import in the upload handler to module level. ([#6382](https://github.com/reflex-dev/reflex/issues/6382))
- Internal logging migrated from the legacy console helpers to standard python `logging` per-module loggers. ([#6864](https://github.com/reflex-dev/reflex/issues/6864))
- Property docstrings are now noun phrases rather than "Get the ..." / "Return the ..." (ruff 0.16's new `D421`). ([#6893](https://github.com/reflex-dev/reflex/issues/6893))


## v0.9.8 (2026-08-04)

### Miscellaneous

- Bumped `react-error-boundary` 6.1.1 → 6.1.2. ([#6678](https://github.com/reflex-dev/reflex/issues/6678))


## v0.9.7 (2026-07-15)

### Miscellaneous

- `rx.upload` internals use `ArrayVar.map` instead of the deprecated `foreach`. ([#6701](https://github.com/reflex-dev/reflex/issues/6701))


## v0.9.6 (2026-06-25)

### Bug Fixes

- Deliver extra bound handler arguments to upload handlers, so `on_drop=State.handle_upload(rx.upload_files(...), field)` passes `field` through to the backend instead of raising a missing-argument error. ([#5290](https://github.com/reflex-dev/reflex/issues/5290))
- Preserve literal string types through `rx.cond`, so `rx.cond(State.flag, "green", "red")` infers `Var[Literal["green", "red"]]` instead of widening to `Var[str]` and tripping Pyright on props typed as `Literal[...] | Var[Literal[...]]` such as Radix `color_scheme`. ([#6545](https://github.com/reflex-dev/reflex/issues/6545))
- `rx.debounce_input` no longer crashes the page with `ReferenceError: input is not defined` when wrapping a native DOM element such as `rx.el.input` or `rx.el.textarea`. The `element` prop now passes global-scope tags as string literals (`element:"input"`), while library components keep referencing their imported identifiers. ([#6637](https://github.com/reflex-dev/reflex/issues/6637))


## v0.9.5 (2026-06-10)

### Features

- `Form` now validates statically-knowable fields against a `TypedDict`-annotated `on_submit` handler at create time: it walks nested form controls (including components nested in props), collects their static `name`/`id` values, and raises `EventHandlerValueError` listing the missing and present fields when a required `TypedDict` field has no matching control. `input`, `select`, and `textarea` are marked as form controls so their identifiers are collected, and required-field resolution honors `NotRequired` across Python 3.10 and 3.11+. The `on_submit` handler signature also accepts a mapping-style payload via `on_submit_mapping_event`. ([#6301](https://github.com/reflex-dev/reflex/issues/6301))

### Miscellaneous

- The connection-error banner now subscribes only to the dedicated `CONNECT_ERRORS` hook instead of the shared events hook, and the upload component declares its `UploadFilesProvider` through `VarData.app_wraps` rather than `Upload._get_app_wrap_components`. ([#6447](https://github.com/reflex-dev/reflex/issues/6447))
