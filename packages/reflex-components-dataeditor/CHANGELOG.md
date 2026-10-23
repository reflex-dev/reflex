## v0.10.1a1 (2026-10-23)

### Bug Fixes

- `rx.data_editor` columns backed by state now get the same defaults as literal columns: `type` defaults to `"str"`, `id` to the lowercased `title`, and a column may be given as just its title string. The column dicts passed to `columns` are no longer modified in place. ([#7607](https://github.com/reflex-dev/reflex/issues/7607))

### Performance

- Faster redraws for `rx.data_editor` grids whose `columns` or `data` come from state. ([#7607](https://github.com/reflex-dev/reflex/issues/7607))


## v0.10.0 (2026-10-08)

### Breaking Changes

- Require Python 3.11 or newer; Python 3.10 is no longer supported. ([#7449](https://github.com/reflex-dev/reflex/issues/7449))


## v0.9.3.post1 (2026-10-06)

### Bug Fixes

- Require `reflex-base >= 0.9.12` so image columns render correctly in data editor grids. ([#7439](https://github.com/reflex-dev/reflex/issues/7439))


## v0.9.3 (2026-09-21)

### Features

- Ensure `rx.data_editor` image previews include Glide Data Grid's required carousel styles. ([#7081](https://github.com/reflex-dev/reflex/issues/7081))


## v0.9.2 (2026-08-28)

### Miscellaneous

- Internal logging migrated from the legacy console helpers to standard python `logging` per-module loggers. ([#6864](https://github.com/reflex-dev/reflex/issues/6864))
