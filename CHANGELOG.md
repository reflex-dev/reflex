## v0.9.4 (2026-06-03)

### Deprecations

- `rx._x.memo` is deprecated in favor of `rx.memo`. The old name remains a working alias for now; update imports to use `rx.memo` directly. ([#6517](https://github.com/reflex-dev/reflex/issues/6517))
- `@rx.memo` now expects each parameter to be annotated as `rx.Var[...]` (or `rx.RestProp`/`rx.EventHandler`) and the function to declare an `rx.Component` or `rx.Var[...]` return type. Memos that still use bare Python types (e.g. `name: str`) or omit the return annotation keep working — the values are coerced to `rx.Var[...]`/`rx.Component` and a deprecation warning points at the parameters and return type that need explicit annotations — but this fallback will be removed in 1.0. ([#6598](https://github.com/reflex-dev/reflex/issues/6598))

### Features

- Added `rx._x.hybrid_property`, a property decorator usable on State classes that works like a normal Python property for backend access while also rendering on the frontend at class level. Use the same method for both, or register a separate frontend implementation with `@<name>.var`. ([#3806](https://github.com/reflex-dev/reflex/issues/3806))
- Promoted the component memo system to a first-class `rx.memo` API. Memo-decorated components now accept `rx.EventHandler` parameters and carry annotated return types so they type-check correctly at call sites. ([#6517](https://github.com/reflex-dev/reflex/issues/6517))
- Added `rx.EMPTY_VAR_COMPONENT`, an empty-component `rx.Var[rx.Component]` sentinel for use as a default on `@rx.memo` `children` slots (and any `rx.Var[rx.Component]` prop) — the component counterpart to `rx.EMPTY_VAR_STR` and `rx.EMPTY_VAR_INT`. ([#6598](https://github.com/reflex-dev/reflex/issues/6598))
- `@rx.memo` now evaluates the decorated function body lazily — on first use (component instantiation) or at compile time — instead of at import time. This speeds up startup and lets a memo reference modules that aren't fully imported yet, sidestepping circular-import errors during decoration. Body-dependent errors (e.g. a var-returning memo that uses hooks or non-bundled imports) now surface when the memo is first used or compiled rather than at import. ([#6598](https://github.com/reflex-dev/reflex/issues/6598))

### Miscellaneous

- Introduced towncrier-based changelog management. Each PR that changes package source now adds a fragment under the affected package's `news/` directory; fragments are assembled into `CHANGELOG.md` at release time. See CONTRIBUTING.md for the full workflow. ([#6350](https://github.com/reflex-dev/reflex/issues/6350))
- Removed the "choose templates" option from `reflex init`. The interactive prompt now offers only a blank app or the AI builder, and no longer opens the open-source templates page. ([#6592](https://github.com/reflex-dev/reflex/issues/6592))
