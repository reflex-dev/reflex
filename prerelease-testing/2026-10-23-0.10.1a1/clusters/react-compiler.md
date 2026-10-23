# Cluster `react-compiler` — experimental React Compiler flag and memoization behavior

## Changelog lines (verbatim)
- (reflex #7234) Add an experimental, default-off `react_compiler` configuration flag to enable React Compiler memoization for generated components in development and production.
- (reflex-base #7234) Add the experimental `react_compiler` configuration option, also available as `REFLEX_REACT_COMPILER`, to opt in to automatic React component memoization.
- (reflex-base #7273, PERF) Unchanged objects and arrays in state updates now keep their previous identity on the frontend, so memoized components skip re-rendering them, and an update that changes nothing no longer re-renders at all.

## What to build
A medium app (3 pages, foreach over 200 items, `@rx.memo` components with and without event-handler props, `rx.ComponentState`, `rx._x.client_state`, `rx.cond`, dynamic routes, a form, `rx.upload`, `rx.data_table`/`rx.data_editor`, `rx.plotly` or `rx.recharts` chart bound to state, `rx.call_script`, `rx.window_event_listener`, custom component with `add_hooks`). Run with `react_compiler=False` (default) and `True` (via rxconfig and via `REFLEX_REACT_COMPILER=1`), dev and prod. For each: compiles? bundle builds? every page renders identically (screenshot diff), every interaction works, console warnings (compiler bailouts show up as warnings in dev), the babel-plugin-react-compiler package appears in `.web/package.json` only when enabled.
Instrument renders: a `@rx.memo` leaf with a `useEffect`-free render counter (e.g. a custom component whose `add_hooks` increments `window.__renders[name]`), then do no-op updates, same-value updates, unrelated updates, and compare counts: default vs compiler, and 0.10.1a1 vs 0.10.0.

## Combine it with
- Hooks that are not "React-compiler safe" (mutating refs during render, conditional hooks in custom components) — the compiler should bail out, not break the page.
- Prod build time and bundle size with and without the flag.
- `reflex run` hot reload with the flag on.
