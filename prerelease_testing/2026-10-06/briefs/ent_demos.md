# Cluster `ent_demos` — reflex-enterprise 0.9.7a4 demos NOT yet run on 0.10.0a1 (dnd, flow, mantine, highcharts, tickets, ag_grid advanced)

Ports: frontend 3300-3319, backend 8300-8319. Work dir: $SB/apps/ent_demos/. DEST: /home/user/reflex/prerelease_testing/2026-10-06/ent_demos/

## Why this cluster exists
Downstream breakage is the most common release blocker. The previous campaign ran the enterprise AG Grid
regression app, maps, OIDC, MCP and the Free-tier guard on 0.9.7a4 + 0.10.0a1 and found them passing,
but explicitly did NOT run: DnD/kanban, React Flow, Mantine, Highcharts, AG Charts standalone, the
tickets demo, nor AG Grid model wrappers (SQLModel-backed server-side row model), master-detail, tree
data, pivot, cell selection/fill handle, aligned grids, custom cell renderers beyond the formatter demo.
Enterprise changelog head (0.9.7a1..a4) is in `/home/user/reflex-enterprise/CHANGELOG.md` (read it).
Demos: `/home/user/reflex-enterprise/demos/{ag_grid,dnd,flow,highcharts,mantine,map,tickets,oidc}` —
COPY each demo out to `$SB/apps/ent_demos/<demo>/` before running (never run inside the checkout).

## Setup
Own venv: `cd $SB && uv --no-config venv --python 3.12 $SB/envs/ent_demos && uv --no-config pip install --python $SB/envs/ent_demos/bin/python --prerelease=allow 'reflex==0.10.0a1' 'reflex[db]==0.10.0a1' 'reflex-enterprise[mcp]==0.9.7a4' 'pydantic<2.14'` plus whatever each demo's requirements list.
Assert `reflex_enterprise.__file__` is inside that venv in every driver. Run with `CI=true REFLEX_TELEMETRY_ENABLED=false`.
Baseline venv for any failure: `reflex==0.9.12` + `reflex-enterprise==0.9.6` (stable pair) AND, to separate
"enterprise alpha broke it" from "core alpha broke it", `reflex==0.9.12` + `reflex-enterprise==0.9.7a4`.

## What to do (each demo: dev mode drive + prod mode drive; console/network/server-log capture; screenshots)
1. **dnd**: drag items between lists/columns with Playwright mouse (`page.drag_and_drop` AND manual
   `mouse.move/down/up` steps — react-dnd needs real pointer events); verify State updates, reorder
   persists across reload, works inside `rx.foreach` with State-bound lists, and with a second tab.
2. **flow** (React Flow): add/connect/move nodes, delete an edge, check State callbacks fire, reload.
3. **mantine**: exercise every widget the demo shows (select, multiselect, date, spotlight, rich text,
   etc.); bind a couple to State vars yourself if the demo doesn't; check prod build size warnings.
4. **highcharts**: render, hover, click a series, update data from State; check license/console messages.
5. **tickets**: whatever the demo does end-to-end (read its README/source first).
6. **ag_grid** advanced: run the demo app's pages you have not seen listed as covered: model wrapper
   (`rxe.ag_grid.model_wrapper` / SSRM backed by an `rx.Model` + sqlite — create the db, seed rows,
   sort/filter/paginate/edit through the grid and verify the db changes), master-detail, tree data,
   pivot/row grouping with aggregation, cell selection + fill handle + clipboard, aligned grids,
   custom JS cell renderers/editors, `row_id_key` callback, pinned rows (new names AND the old
   aliases), `suppress_overlays`, datasource URL query parameters. Also `rxe.ag_grid` inside an
   `@rx.memo` component and inside a `ComponentState`, with column defs from `rx.foreach`-style State data.
7. AG Charts standalone (`rxe.ag_chart` if present): render + update from State.
8. Also `rxe.App` specifics: `rxe.google_font` in head, the enterprise badge, `rxe.App(...)` with
   `rx.App` plugins; `reflex export` of one enterprise app and inspect the zip.
For any failure: run the two baselines above before reporting; say which combination fails.
Expected/benign: AG Grid/AG Charts unlicensed trial banners in the console; the dev login gate bypass via CI=true.
