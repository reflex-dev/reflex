## v0.9.6 (2026-07-15)

### Miscellaneous

- `rx.segmented_control` internals use `ArrayVar.map` instead of the deprecated `foreach`. ([#6701](https://github.com/reflex-dev/reflex/issues/6701))


## v0.9.5 (2026-06-10)

### Miscellaneous

- Mark the Radix form controls — checkbox, checkbox group, radio group, radio cards, select, switch, and both sliders — with `_is_form_control` so their static `name`/`id` is collected when a form validates its fields against a `TypedDict`-annotated `on_submit` handler. ([#6301](https://github.com/reflex-dev/reflex/issues/6301))


## v0.9.4 (2026-06-03)

No significant changes.
