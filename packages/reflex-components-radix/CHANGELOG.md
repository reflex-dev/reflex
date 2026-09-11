## v0.9.9a2 (2026-09-11)

### Bug Fixes

- Avoid retaining stale Radix Themes library registrations when recompiling an app that no longer uses Radix components. ([#7109](https://github.com/reflex-dev/reflex/issues/7109))


## v0.9.9a1 (2026-09-10)

### Miscellaneous

- Bump the Radix primitives: `@radix-ui/react-accordion` 1.2.20, `@radix-ui/react-dialog` 1.1.23, and `@radix-ui/react-form` 0.1.16. ([#7019](https://github.com/reflex-dev/reflex/issues/7019))


## v0.9.8 (2026-08-28)

### Bug Fixes

- Deprecated `App(theme=...)` now keeps applying its theme when an explicit `RadixThemesPlugin` is configured, instead of being silently ignored until its removal in 1.0. ([#6776](https://github.com/reflex-dev/reflex/issues/6776))


## v0.9.7 (2026-08-04)

### Miscellaneous

- Bumped Radix UI primitive pins:

  - `@radix-ui/react-accordion`: 1.2.12 → 1.2.18
  - `@radix-ui/react-dialog`: 1.1.15 → 1.1.21
  - `@radix-ui/react-form`: 0.1.8 → 0.1.14
  - `@radix-ui/react-progress`: 1.1.8 → 1.1.14
  - `@radix-ui/react-slider`: 1.3.6 → 1.4.5

  ([#6678](https://github.com/reflex-dev/reflex/issues/6678))


## v0.9.6 (2026-07-15)

### Miscellaneous

- `rx.segmented_control` internals use `ArrayVar.map` instead of the deprecated `foreach`. ([#6701](https://github.com/reflex-dev/reflex/issues/6701))


## v0.9.5 (2026-06-10)

### Miscellaneous

- Mark the Radix form controls — checkbox, checkbox group, radio group, radio cards, select, switch, and both sliders — with `_is_form_control` so their static `name`/`id` is collected when a form validates its fields against a `TypedDict`-annotated `on_submit` handler. ([#6301](https://github.com/reflex-dev/reflex/issues/6301))


## v0.9.4 (2026-06-03)

No significant changes.
