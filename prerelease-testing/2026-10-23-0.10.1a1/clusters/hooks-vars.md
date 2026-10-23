# Cluster `hooks-vars` — hook ordering, Var operations, compile-time codegen fixes

## Changelog lines (verbatim)
- (reflex-base #7586, DEPRECATION) `VarData(position=...)` and `Hooks.HookPosition` are deprecated and ignored: hooks render in declaration order. Remove the `position` argument; to place a hook after another one, put the one it reads in its `VarData(hooks=...)`.
- (reflex-base #7586) Component hooks render in the order they are declared and merged, so a hook always comes after the hooks it reads. Before, a component whose prop and `add_hooks` Var read the same state could render a hook before the state declaration it reads and fail with a `ReferenceError`. A hook that reads state must carry it: return `rx.Var(f"const x = {State.value}")` from `add_hooks`, not a plain string built with `str(State.value)`.
- (reflex-components-core #7586) `window_event_listener` and `clipboard` hooks now render in declaration order with the rest of the component's hooks instead of being moved after them.
- (reflex-base #7606) Add `reflex_base.vars.get_leaf_vars`, which returns the vars a var reads by unwrapping var operations, casts, literal containers and function bodies.
- (reflex-base #7565) Raising a negative number or a negated var to a power, such as `(-State.x) ** 2`, now compiles to valid JavaScript.
- (reflex-base #7518) Make `StringVar` length, indexing, and slicing count Unicode code points so operations do not split valid surrogate pairs. On a `None` string these operations now behave as if it were empty.
- (reflex-base #7587) Passing a plain `dict` to `format_prop` no longer raises `AttributeError`; the dict is JSON-encoded like any other literal.
- (reflex-base #7403) `LiteralObjectVar.create` is typed to take any value that serializes to a mapping, such as a dataclass, as it does at runtime, not only a mapping.
- (reflex-base #7573) Write the Tailwind `important` option to the generated `tailwind.config.js` under the `important` key. It was emitted as `importants`, so Tailwind ignored it.
- (reflex-base #7405) The CDN fallback for an unbundled sub-path dynamic import now puts the sub-path before jsdelivr's `/+esm`, so it resolves instead of returning 404.
- (reflex-base #7517) Raise descriptive errors when page or compile contexts are accessed outside compilation.

## What to build
Custom components (subclass `rx.Component`) with `add_hooks` returning: plain strings, `rx.Var(...)` reading state, hooks with `VarData(hooks=...)` dependencies, a hook using the deprecated `VarData(position=HookPosition.PRE_TRIGGER)` (expect a deprecation warning, capture it, and confirm it still compiles and runs). A component whose prop AND `add_hooks` read the same state var (the ReferenceError case — baseline on 0.10.0 should fail). `rx.window_event_listener`/`rx.clipboard` alongside custom hooks that read state. Pages exercising `(-State.x) ** 2`, `State.s.length()`, `State.s[0]`, `State.s[1:3]` on emoji/surrogate-pair strings and on a `str | None` var set to None. `rx.el.div(style={...})` with a nested dict prop; `LiteralObjectVar.create(dataclass_instance)`. `rxconfig` with the tailwind plugin `TailwindV3Plugin(config={"important": "#root"})` (and v4 if supported) → inspect generated `.web/tailwind.config.js` and the computed CSS specificity in the browser. A `rx.Var` using a dynamic import of a sub-path from an unbundled library to hit the CDN fallback (check network tab for the jsdelivr URL shape and status).

## Combine it with
- Same custom component used inside `rx.foreach`, under `@rx.memo`, and in `rx.ComponentState`.
- Run `reflex_base.vars.get_leaf_vars` on a handful of derived vars (ops, `.to(str)`, literal dict containing vars, `rx.Var.create(f"...{a}{b}")`) in a repro script and compare its output to expectation.
- Prod mode build must succeed (the pow fix is a build-time failure).
