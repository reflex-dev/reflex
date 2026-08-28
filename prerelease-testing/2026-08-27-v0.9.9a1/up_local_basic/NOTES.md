# up_local_basic — upgrade testing 0.9.8 -> 0.9.9a1

Apps under test (copied from /home/user/reflex-dev/reflex-examples, read-only source):

- **local-component** — app embedding a local React component: `hello.jsx` shipped via
  `rx.asset(path="hello.jsx", shared=True)` and imported with
  `library = f"/public/{component_asset}"`. NOT a packaged custom component
  (`reflex component init` style) — it exercises the local-JSX-asset path, forwardRef,
  event passthrough (`on_context_menu`), `rx.color_mode_cond`, popover+form, `rx.scroll_to`.
  **No `react-router-dom` is declared anywhere in the app source** (checked; the only
  react-router-dom reference exists in reflex's generated `.web/package.json` on 0.9.8).
- **basic_crud** — `reflex[db]` + FastAPI `api_transformer`: SQLModel `Product` table,
  custom `APIRouter` under `/products`, UI query console, `@rx.event(background=True)`
  polling task that reloads the product list every 2s after DB changes.

## Verdict

**No regressions found in either app.** All browser flows and API flows behave
identically on 0.9.8 and 0.9.9a1 (both after the in-place upgrade preserving
`.web/` + `reflex.lock/`, and on a cold 0.9.9a1 run with `.web` deleted).
Migration on first 0.9.9a1 run is clean: lockfiles restored from `reflex.lock/`,
`react-router-dom` pruned from `.web/package.json` (`bun remove` -> "Removed: 1"),
react-router family 7.18.2 -> 8.3.0, vite 8.0.16 -> 8.2.0, postcss/postcss-import
installed. Two cosmetic log observations (below).

## Environment / how to rerun

- Python 3.11 venv per app dir (`<app>/venv`), installed from PyPI only:
  - baseline: `uv venv <app>/venv --python 3.11 && uv pip install --python <app>/venv/bin/python -r <app>/requirements.txt 'reflex==0.9.8'`
  - upgrade in place: `uv pip install --python <app>/venv/bin/python --prerelease=allow -U 'reflex==0.9.9a1'`
- Ports: local-component FP 3260 / BP 8260, basic_crud FP 3261 / BP 8261.
- Run (from the app dir): `REFLEX_TELEMETRY_ENABLED=false venv/bin/reflex run --frontend-port <FP> --backend-port <BP> --loglevel debug > server.log 2>&1 &`
- basic_crud DB setup BEFORE first run (on 0.9.8): `venv/bin/reflex db init && venv/bin/reflex db migrate`
  (creates `alembic/` + `reflex.db` with the `product` table; the same sqlite DB is
  carried through the upgrade).
- Drivers (Playwright venv `$SB/envs/driver`, Chromium at /opt/pw-browsers/chromium):
  - `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_local_component.py http://localhost:3260/ <outdir>`
  - `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_basic_crud.py http://localhost:3261/ http://localhost:8261 <outdir>`
  - Exit 0 iff every step passed; each writes `result.json` (steps + full console log +
    failed requests + >=400 responses) and numbered screenshots into `<outdir>`.
- Cold-run check: kill server, `rm -rf .web`, run again (same command), re-drive.

## Flows exercised

local-component (5 steps, ran identically on 0.9.8 / upgraded 0.9.9a1 / cold 0.9.9a1):
1. initial_render — local JSX component renders "Hello world!"
2. popover_edit_submit — click greeting, popover opens, type "Reflex" (live updates via
   on_change), Enter submits form, popover closes, "Hello Reflex!"
3. context_menu_caps — right-click h1: `rx.console_log` passthrough fires exactly once,
   caps toggle -> "HELLO REFLEX!"
4. color_mode_bg — color-mode toggle flips Hello div background papayawhip
   (rgb(255,239,213)) <-> rebeccapurple (rgb(102,51,153)) via rx.color_mode_cond
5. scroll_to — button 150vh down scrolls back to #greeting (scrollY 1335 -> 429)

basic_crud (11 steps, ran identically on 0.9.8 / upgraded 0.9.9a1 / cold 0.9.9a1):
1. initial_render — "0 products found"
2. ui_post — POST /products via UI console -> Status 200; background task
   (`@rx.event(background=True)` + 2s poll) updates list to "1 products found"
3. ui_get — GET products via UI -> markdown JSON block contains created code
4. ui_put — PUT products/{id} rename -> list shows new label via background reload
5. ui_delete — DELETE products/{id} -> count back to 0
6. api_ping — GET :8261/ping -> 200 "pong" (API mounting through api_transformer intact)
7-10. api_post_list / api_get_one / api_put / api_delete — direct httpx CRUD against
   the FastAPI router mounted via `rx.App(api_transformer=fastapi)`
11. api_get_missing — GET /products/999999 -> 200 with serialized HTTPException body
   (app bug: it *returns* HTTPException instead of raising; identical on both versions,
   recorded as pre-existing app quirk, NOT a reflex issue)

## Migration observations (first 0.9.9a1 run, in-place upgrade)

Both apps, from `server_run1.log` under artifacts `<app>/0.9.9a1/`:

- "Restoring lockfiles." — `reflex.lock/{bun.lock,package.json}` round-trip works; a
  `reflex.lock/` dir appears in the app root and survives `.web` deletion (used by the
  cold run: `bun install --legacy-peer-deps --frozen-lockfile` -> "no changes").
- `bun remove --legacy-peer-deps react-router-dom` -> "Removed: 1" — react-router-dom
  pruned from package.json (verified in package.json.diff; also absent after cold run).
- react-router / @react-router/node / @react-router/dev / @react-router/fs-routes
  7.18.2 -> 8.3.0; vite 8.0.16 -> 8.2.0 (see `package.json.diff` in each app's
  artifacts dir).
- Transient `warn: incorrect peer dependency "react-router@7.18.2"` x2 during the
  dev-deps `bun add` step — ordering artifact (dev deps at 8.3.0 installed while
  runtime react-router is still 7.18.2; the very next step bumps it). Harmless, but
  visible to users at debug loglevel on the first post-upgrade run.
- React Router v7 "Future Flag Warning" spam present on every 0.9.8 dev run is GONE
  on 0.9.9a1 (expected: RR8).

## Anomalies (cosmetic, not regressions in app behavior)

1. **NEW vite warning on every 0.9.9a1 dev run** (both apps, upgraded and cold; not
   present on 0.9.8): `(!) Your Vite config uses features that are unsupported by
   configLoader: 'native' ... import "./vite-plugin-safari-cachebust" without a file
   extension (vite.config.js:4:35). Add the file extension`. The offending import is in
   reflex's own generated `.web/vite.config.js`, so every reflex app on vite 8.2.0 logs
   this twice per dev-server start. Cosmetic today; becomes real breakage whenever vite
   flips `configLoader: 'native'` to default. Suggest reflex add the `.js` extension in
   its template.
2. `warn: incorrect peer dependency "react-router@7.18.2"` transiently during the
   in-place upgrade's package migration (see above). One-time, self-resolving.
3. Baseline (0.9.8) log noise for context, unchanged or improved on 0.9.9a1:
   SitemapPlugin enabled-by-default warning (still present on 0.9.9a1), "version out of
   date -> 0.9.8.post1" upgrade nag (0.9.8 only), `warn: incorrect peer dependency
   "react@19.2.8"` during 0.9.8 install, RR7 future-flag warnings (0.9.8 only),
   granian "[ERROR] Unexpected exit from worker-1" on SIGTERM shutdown (both versions,
   shutdown noise).
4. basic_crud JSON key ordering in API responses differs between runs/versions
   (serialization order of the app's own `dict()` override) — inconsequential.

## Artifacts layout

- `drive_local_component.py`, `drive_basic_crud.py` — Playwright drivers (also under
  artifacts/)
- `local-component/`, `basic_crud/` — app source as tested (minus .web/node_modules/venv/db;
  `reflex.lock/` included as produced by the 0.9.9a1 migration)
- `artifacts/<app>/0.9.8/` — baseline: server_run1.log, result.json, screenshots
- `artifacts/<app>/0.9.9a1/` — in-place upgrade: first-run server log (migration),
  result.json, screenshots
- `artifacts/<app>/cold/` — fresh-.web 0.9.9a1 run: server_cold.log, result.json,
  screenshots
- `artifacts/<app>/package.json.0.9.8`, `package.json.0.9.9a1`, `package.json.diff`
- `artifacts/basic_crud/0.9.8/db_init.log` — reflex db init/migrate output
