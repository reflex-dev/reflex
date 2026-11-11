## v0.10.1 (2026-10-26)

### Features

- `checkbox_group` and `checkbox_cards` now support a controlled `value` with `on_value_change`, and the native form props that `radio_group` and `radio_cards` already have. ([#7345](https://github.com/reflex-dev/reflex/issues/7345))
- Expose `FormData` on the form namespace as `rx.form.FormData`. The `rx.form` stub now declares the namespace as a class, so `rx.form.FormData[str, str]` works in type annotations; calls such as `rx.form(...)` and `rx.form.root(...)` type the same as before. ([#7386](https://github.com/reflex-dev/reflex/issues/7386))

### Bug Fixes

- Avoid Emotion's unsafe `:first-child` SSR warning for Radix Accordion items in development mode. ([#7098](https://github.com/reflex-dev/reflex/issues/7098))
- `rx.input`'s `auto_complete` now takes the HTML autocomplete value, such as `"off"` or `"email"`, which used to raise a `TypeError`. A bool still works and now becomes `"on"` or `"off"`; before, React dropped it and browser autocomplete stayed on. ([#7418](https://github.com/reflex-dev/reflex/issues/7418))
- Forward progress values to the Radix Root so its state and ARIA attributes reflect the displayed progress. ([#7431](https://github.com/reflex-dev/reflex/issues/7431))
- Remove the `as_child` prop from `rx.radio_cards.root` and `rx.radio_cards.item`. Radix Themes does not accept `asChild` on either component: on the root it crashed the page or dropped the grid container, and on the item it did nothing. ([#7555](https://github.com/reflex-dev/reflex/issues/7555))

### Miscellaneous

- Update the Radix primitives to the versions bundled with the current `radix-ui` release that Radix Themes depends on (accordion 1.3.1, dialog 1.3.1, form 0.3.0, progress 1.2.1, slider 1.6.1), so apps load a single copy of each primitive. ([#7645](https://github.com/reflex-dev/reflex/issues/7645))


## v0.10.0 (2026-10-08)

### Breaking Changes

- Require Python 3.11 or newer; Python 3.10 is no longer supported. ([#7449](https://github.com/reflex-dev/reflex/issues/7449))

### Miscellaneous

- Update the Radix slider and progress dependencies to 1.4.7 and 1.1.16. ([#7424](https://github.com/reflex-dev/reflex/issues/7424))


## v0.9.10.post1 (2026-09-21)

### Bug Fixes

- Require `reflex-base >= 0.9.12`. The declared floor was older than the `reflex_base.components.tags.CommonTag` import this package relies on, so a resolver was free to pair it with a `reflex-base` that fails at import time with `ImportError: cannot import name 'CommonTag'`. ([#7268](https://github.com/reflex-dev/reflex/issues/7268))


## v0.9.10 (2026-09-21)

### Bug Fixes

- Stop `rx.form.message` from passing `force_match` to the DOM when `match` is not set. ([#7133](https://github.com/reflex-dev/reflex/issues/7133))

### Performance

- The segmented control no longer keeps a permanent reference to the vars it builds its selected-index expression from. ([#7198](https://github.com/reflex-dev/reflex/issues/7198))

### Miscellaneous

- Annotate `_render` overrides as returning `CommonTag`, the new base of every tag class. ([#7121](https://github.com/reflex-dev/reflex/issues/7121))


## v0.9.9 (2026-09-11)

### Bug Fixes

- Avoid retaining stale Radix Themes library registrations when recompiling an app that no longer uses Radix components. ([#7109](https://github.com/reflex-dev/reflex/issues/7109))

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
