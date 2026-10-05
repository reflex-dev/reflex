# Cluster `up_examples_c` — upgrade regression, batch C (components, routing, custom JS)

Follow `UPGRADE_PROTOCOL.md` (same directory) for each app, in this order:
1. `local-component` — wraps a LOCAL React component (custom `library`/`assets`), refs and a
   popover+form: this exercises the auto-memo transparency change (#6850) and the local
   package-specifier fix (#7117) — inspect `.web/package.json` and the rendered component.
2. `nba` — pandas + plotly + statsmodels (pin versions from its requirements): filters, table,
   plotly charts (#6977 `divId`; on-demand pandas/plotly serializers #7049). Data is a bundled
   CSV, no network needed.
3. `quiz` — multi-step form with radio groups, results page; routing between pages.
4. `traversal` — sidebar navigation across many routes, `rx.code_block`, tabs; a good router
   workout for #7068 (watch the navigation websocket deltas and the browser console).
5. `github-stats` — the GitHub API is reachable through the proxy? If not, stub the fetch and
   test the charts (recharts, #6833 prop routing) and the form.
6. `linkinbio` — `rx.moment`, links, `launchdarkly` (stub or disable the SDK); the previous
   campaign used it for the moment on_change behavior — re-check on moment 0.9.4 stable.
7. `json-tree` and `overkey` (small, quick) if time permits — custom components / keyboard.
