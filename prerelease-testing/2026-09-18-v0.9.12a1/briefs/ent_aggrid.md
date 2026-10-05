# Cluster `ent_aggrid` — reflex-enterprise 0.9.5 ag_grid demo + ag_grid_finance on reflex 0.9.12a1 vs 0.9.11.post1

The enterprise venvs are prebuilt (READ-ONLY): `$SB/envs/ent` (0.9.12a1 train + `reflex-enterprise[mcp]==0.9.5`
from the wheel) and `$SB/envs/entprev` (0.9.11.post1 + the same wheel). Make your own copies if you need
extra packages (faker, pandas, aiosqlite, greenlet for the demo — install the demo's `requirements.txt`
MINUS its reflex/reflex-enterprise lines, then the wheel + train).

Demo source: `/home/user/reflex-enterprise/demos/ag_grid` (17 routes) — copy it to
`$SB/apps/ent_aggrid/demo_new` and `demo_prev`. `ag_grid_finance` is at
`/home/user/reflex-dev/reflex-examples/ag_grid_finance` (yfinance is blocked by the proxy; the
previous campaign wrote an offline data generator patch — reuse it:
`git -C /home/user/reflex archive origin/claude/reflex-prerelease-testing-t0sd90 prerelease-testing/2026-09-10-v0.9.11a1/ent_aggrid | tar -x -C $SB/apps/ent_aggrid/`
gives you `NOTES.md` (read "Demo patch" and "Finance patch"), the driver `scripts/`, and the
patched app copies. The previous campaign also found four shipped rxe 0.9.5 defects that block its
own demos (stale bundle path, ModelWrapper URL encoding, ag-grid/ag-charts version mismatch,
`column_def()` dropping unknown kwargs) — apply the same demo-side patches, note them, do not
count them as new.

Run EVERY route of the ag_grid demo on both reflex versions with `CI=true`, dev mode (and prod if
the login gate allows it under `CI=true` — record what happens), driving each route as a user:
sort/filter columns, edit a cell (ModelWrapper → sqlite write-back), paginate, select rows, use the
formatters/renderers page (python-callable renderers → LambdaVar), the `@rx.memo` row counter,
the `@rxe.static` raw-data dialog, the AG Charts page, the datasource/infinite-row-model page,
column state persistence. Diff the two versions' console/network/action results route by route.
Then `ag_grid_finance` the same way.

Things this train changed that ag_grid touches: `RegistrationContext` (bundled libraries via
`rxe.vars.get_bundled_libraries`), `EventChain.create` interning (#7122), the router split (#7068:
`state.router`, `router_data`), `VarData` field tracking (#7068), the auto-memo transparency
(#6850: every ag-grid wrapper is an auto-memoized component now receiving parent props), the
`Tag`/`CommonTag` render change (#7121: rxe overrides `_render`?), the lazy `reflex.utils.lazy_loader`
attribute caching (#6930: rxe uses `lazy_loader.attach`). Grep the enterprise wheel source
(`$SB/apps/packaging/entwheel/reflex_enterprise`) for each and test the code path it feeds.
Report every difference between versions; a route that works on 0.9.11.post1 and breaks on 0.9.12a1
is a release-blocking regression.
