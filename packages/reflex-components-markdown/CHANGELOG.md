## v0.9.4.post1 (2026-09-21)

### Bug Fixes

- Require `reflex-base >= 0.9.12`. The declared floor was older than the `reflex_base.components.tags.CommonTag` import this package relies on, so a resolver was free to pair it with a `reflex-base` that fails at import time with `ImportError: cannot import name 'CommonTag'`. ([#7268](https://github.com/reflex-dev/reflex/issues/7268))


## v0.9.4 (2026-09-21)

### Miscellaneous

- Annotate `_render` overrides as returning `CommonTag`, the new base of every tag class. ([#7121](https://github.com/reflex-dev/reflex/issues/7121))


## v0.9.3 (2026-06-03)

### Miscellaneous

- Updated markdown custom-code collection to use the new `rx.memo` component API instead of the removed `CustomComponent` handling. ([#6517](https://github.com/reflex-dev/reflex/issues/6517))
