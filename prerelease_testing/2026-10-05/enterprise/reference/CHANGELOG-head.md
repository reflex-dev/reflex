# Enterprise release changelog head

Source commit: `40aa7b33af419a6dc354e33873f6cd1270d28205`.

## v0.9.7a2 (2026-10-05)

### Features

- Allow `reflex run --env prod` and `reflex export` on the Free tier when the app shows the "Built with Reflex" badge. Exports now always include the badge when it is enabled, including `reflex export --env dev`. ([#241](https://github.com/reflex-dev/reflex-enterprise/issues/241))


## v0.9.7a1 (2026-10-05)

### Breaking Changes

- Upgrade the AG Grid wrapper from 34.3.1 to 36.2.0 and integrated AG Charts from
  11.2.4 to 14.2.0. Applications with custom grid CSS or chart options should review
  the [migration notes](https://reflex.dev/docs/enterprise/ag-grid/upgrading-to-36-2/).
  Add `suppress_overlays` for the new provided overlays. Fix `row_id_key` callback
  generation, pinned-row prop names (retaining existing aliases), and datasource URL
  query parameters. Add Playwright coverage using the `reflex_app` fixture. ([#ag-grid-36](https://github.com/reflex-dev/reflex-enterprise/issues/ag-grid-36))

### Features

- Add `rxe.google_font` to load a Google Font from the document head, with
  `preconnect` hints and `display=swap`, so the font is fetched during the initial
  HTML parse instead of after the global stylesheet:

  ```python
  app = rxe.App(head_components=rxe.google_font("Inter", weights=[400, 700]))
  ``` ([#239](https://github.com/reflex-dev/reflex-enterprise/issues/239))

### Miscellaneous

- Improve authentication audit hook type annotations. ([#237](https://github.com/reflex-dev/reflex-enterprise/issues/237))


