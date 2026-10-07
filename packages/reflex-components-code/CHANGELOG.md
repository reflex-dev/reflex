## v0.10.0a2 (2026-10-06)

### Breaking Changes

- Require Python 3.11 or newer; Python 3.10 is no longer supported. ([#7449](https://github.com/reflex-dev/reflex/issues/7449))


## v0.10.0a1 (2026-10-05)

### Miscellaneous

- Update Shiki and its transformers to 4.5.0. ([#7424](https://github.com/reflex-dev/reflex/issues/7424))


## v0.9.6 (2026-09-21)

### Bug Fixes

- Give default code-copy buttons an accessible name and prevent them from submitting an enclosing form. ([#7078](https://github.com/reflex-dev/reflex/issues/7078))


## v0.9.5 (2026-09-11)

### Miscellaneous

- Bump `shiki` and `@shikijs/transformers` to 4.4.3. ([#7019](https://github.com/reflex-dev/reflex/issues/7019))


## v0.9.4 (2026-08-28)

### Bug Fixes

- Track state vars referenced in `rx.code_block`'s `custom_style` dict so styles bound to state re-render on updates, and make `wrap_long_lines=True` apply `whiteSpace: pre-wrap` to the code tag even when `code_tag_props` is also provided. ([#6520](https://github.com/reflex-dev/reflex/issues/6520))


## v0.9.3 (2026-08-04)

### Miscellaneous

- Bumped `shiki` and `@shikijs/transformers` 3.3.0 → 4.3.1. ([#6678](https://github.com/reflex-dev/reflex/issues/6678))
