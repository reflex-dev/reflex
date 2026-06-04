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
