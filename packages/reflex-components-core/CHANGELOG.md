## v0.9.5 (2026-06-10)

### Features

- `Form` now validates statically-knowable fields against a `TypedDict`-annotated `on_submit` handler at create time: it walks nested form controls (including components nested in props), collects their static `name`/`id` values, and raises `EventHandlerValueError` listing the missing and present fields when a required `TypedDict` field has no matching control. `input`, `select`, and `textarea` are marked as form controls so their identifiers are collected, and required-field resolution honors `NotRequired` across Python 3.10 and 3.11+. The `on_submit` handler signature also accepts a mapping-style payload via `on_submit_mapping_event`. ([#6301](https://github.com/reflex-dev/reflex/issues/6301))

### Miscellaneous

- The connection-error banner now subscribes only to the dedicated `CONNECT_ERRORS` hook instead of the shared events hook, and the upload component declares its `UploadFilesProvider` through `VarData.app_wraps` rather than `Upload._get_app_wrap_components`. ([#6447](https://github.com/reflex-dev/reflex/issues/6447))
