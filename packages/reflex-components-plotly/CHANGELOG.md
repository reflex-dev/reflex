## v0.9.4 (2026-08-04)

### Miscellaneous

- Bumped `react-plotly.js` 2.6.0 → 4.0.0, with `plotly.js` (and its dist-min / locale variants) 3.5.x → 3.7.0. ([#6678](https://github.com/reflex-dev/reflex/issues/6678))


## v0.9.3 (2026-06-25)

### Features

- `rx.plotly` (and its dist variants like `rx.plotly.basic`) now accept a `locale` prop to localize Plotly's number/date formatting and modebar labels. The matching locale data from `plotly.js-locales` is resolved and merged into the chart config at render time, so per-chart locales work without any manual setup. ([#6428](https://github.com/reflex-dev/reflex/issues/6428))
