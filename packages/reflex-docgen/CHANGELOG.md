## v0.10.0a2 (2026-10-06)

### Breaking Changes

- Require Python 3.11 or newer; Python 3.10 is no longer supported. ([#7449](https://github.com/reflex-dev/reflex/issues/7449))

### Bug Fixes

- Recognize YAML frontmatter after a UTF-8 BOM or leading whitespace and with CRLF line endings, keeping metadata out of rendered page content and tables of contents. ([#7238](https://github.com/reflex-dev/reflex/issues/7238))


## v0.9.5 (2026-08-28)

### Miscellaneous

- Property docstrings are now noun phrases rather than "Get the ..." / "Return the ..." (ruff 0.16's new `D421`). ([#6893](https://github.com/reflex-dev/reflex/issues/6893))


## v0.9.4 (2026-08-04)

### Features

- Added typed `description` and `image` frontmatter fields to `FrontMatter`, parsed from docs and preserved by the markdown writer, for per-page SEO metadata. ([#6464](https://github.com/reflex-dev/reflex/issues/6464))


## v0.9.3 (2026-07-15)

### Bug Fixes

- Fixed `meta_description` and `description` frontmatter keys being misinterpreted as component preview lambdas. ([#6704](https://github.com/reflex-dev/reflex/issues/6704))


## v0.9.2 (2026-06-03)

No significant changes.
