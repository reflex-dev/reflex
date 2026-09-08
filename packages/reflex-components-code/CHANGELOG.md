## v0.9.4 (2026-08-28)

### Bug Fixes

- Track state vars referenced in `rx.code_block`'s `custom_style` dict so styles bound to state re-render on updates, and make `wrap_long_lines=True` apply `whiteSpace: pre-wrap` to the code tag even when `code_tag_props` is also provided. ([#6520](https://github.com/reflex-dev/reflex/issues/6520))


## v0.9.3 (2026-08-04)

### Miscellaneous

- Bumped `shiki` and `@shikijs/transformers` 3.3.0 → 4.3.1. ([#6678](https://github.com/reflex-dev/reflex/issues/6678))
