## v0.9.4 (2026-09-21)

### Bug Fixes

- Fix `rx.toast` `action` and `cancel` buttons not triggering their `on_click` events when the toast is fired from a frontend event trigger. ([#7157](https://github.com/reflex-dev/reflex/issues/7157))


## v0.9.3 (2026-09-11)

### Miscellaneous

- Bump `sonner` to 2.0.8. ([#7019](https://github.com/reflex-dev/reflex/issues/7019))


## v0.9.2 (2026-08-28)

### Bug Fixes

- Qualify the `dict` return annotation on `ToastProps.dict`, which shadowed the builtin for its own annotation. ([#6846](https://github.com/reflex-dev/reflex/issues/6846))
