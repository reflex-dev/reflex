## v0.9.4a2 (2026-09-11)

### Breaking Changes

- `rx.moment` now fires `on_change` on mount and remount, including for static dates and `interval=0`. Handlers with side effects should account for the initial call and for React Strict Mode invoking it twice in development. ([#7085](https://github.com/reflex-dev/reflex/issues/7085))

### Bug Fixes

- Keep `rx.moment` locales independent: components without a `locale` render in English even when another component or route imports a different locale. Explicit `locale="en"` also works without importing a nonexistent locale module. ([#7110](https://github.com/reflex-dev/reflex/issues/7110))


## v0.9.4a1 (2026-09-10)

### Bug Fixes

- Migrate `rx.moment` to `react-moment` 2.0.2 and include its duration-format dependency. ([#7003](https://github.com/reflex-dev/reflex/issues/7003))

### Miscellaneous

- Bump `moment-timezone` to 0.6.3. ([#7019](https://github.com/reflex-dev/reflex/issues/7019))


## v0.9.3 (2026-08-04)

### Bug Fixes

- Make `rx.moment` a `MemoizationLeaf` so a stateful date child is not memo-wrapped, which react-moment parsed like `moment({})` (today at midnight).


## v0.9.2 (2026-06-25)

### Bug Fixes

- `rx.moment` now pins its `moment-timezone` dependency to the exact version `0.6.2` instead of a caret range, keeping frontend installs reproducible. ([#6649](https://github.com/reflex-dev/reflex/issues/6649))
