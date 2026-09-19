## v0.9.4a1 (2026-09-18)

### Features

- Added a Recharts Sankey chart wrapper (`rx.recharts.sankey_chart`) with support for custom node and link renderers, and `rx.recharts.use_chart_width()` for reading the rendered chart width as a `Var`. ([#6708](https://github.com/reflex-dev/reflex/issues/6708))

### Bug Fixes

- Fix Recharts component props (e.g. `stroke_dasharray` on `reference_line`, `tick_formatter` on `x_axis`/`y_axis`) being misclassified as CSS and routed to `wrapperStyle` instead of reaching the underlying Recharts component. ([#6833](https://github.com/reflex-dev/reflex/issues/6833))


## v0.9.3 (2026-09-11)

### Miscellaneous

- Bump `recharts` to 3.10.1. ([#7019](https://github.com/reflex-dev/reflex/issues/7019))


## v0.9.2 (2026-08-04)

### Features

- Added `rx.recharts.layer` and `rx.recharts.rectangle`, wrapping the Recharts `Layer` and `Rectangle` components used for constructing custom node elements.
