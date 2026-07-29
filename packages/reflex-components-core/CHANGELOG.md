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
