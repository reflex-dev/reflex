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

## VERIFICATION (adversarial re-check, 2026-08-28)

**Claim verified:** "Transient bun warnings 'incorrect peer dependency react-router@7.18.2'
during the one-time 0.9.8->0.9.9a1 package migration."

Reproduced independently with a MINIMAL `reflex init --template blank` app (not the
example apps), fresh Python 3.11 venv from PyPI only, in
`$SB/apps/verify_up_local_basic_1/` (FP 3764 / BP 8764):

1. `reflex==0.9.8` init + dev run to completion (frontend 200; `.web/package.json` has
   react-router family 7.18.2 incl. react-router-dom).
2. In-place `uv pip install --prerelease=allow -U 'reflex==0.9.9a1'`, then first dev run
   with `--loglevel debug` -> `server_run1_099a1.log`:
   - exactly **2x** `Debug: warn: incorrect peer dependency "react-router@7.18.2"`
     (log lines 192/194), emitted during
     `bun add --legacy-peer-deps -d ... @react-router/dev@8.3.0 @react-router/fs-routes@8.3.0 ...`
     while runtime react-router is still 7.18.2 — matching the claimed mechanism;
   - the immediately following `bun add ... react-router@8.3.0 ...` step bumps it;
   - final state consistent: react-router / @react-router/{node,dev,fs-routes} all 8.3.0
     in package.json AND node_modules, react-router-dom removed, app serves 200, no
     tracebacks.
3. Second 0.9.9a1 run: **0** occurrences — one-time, self-resolving, as claimed.

Additional refuting context found:

- **Debug-only visibility.** The warning lines come from bun's stdout, which reflex
  streams via `logger.debug(...)` gated on `logger.isEnabledFor(logging.DEBUG)`
  (`reflex/utils/processes.py::stream_logs`). At the default loglevel nothing is shown —
  narrower visibility than "users watching the first post-upgrade run" suggests.
- **Same-class warnings pre-exist on 0.9.8.** The 0.9.8 baseline's own first install
  logs `warn: incorrect peer dependency "react-router@7.18.3"` and
  `warn: incorrect peer dependency "react@19.2.8"` at the equivalent bun-add steps.
  Transient bun peer-dep warnings during reflex installs are not new in 0.9.9a1.
- Env quirk noted during verification (self-inflicted, not reflex): overriding
  `NO_PROXY=localhost,127.0.0.1` clobbers this sandbox's ambient bypass for
  registry.npmjs.org and makes bun installs fail with ConnectionClosed; run reflex with
  the ambient proxy env untouched.

**Verdict: observation accurate and reproducible, but NOT a defect a fix-agent should act
on** (confirmed=false): cosmetic, debug-loglevel-only, one-time, self-resolving, migration
end-state correct, and the same class of bun warning already occurs on 0.9.8. At most a
nice-to-have: migrate runtime packages before dev deps to avoid the transient mismatch.
Verification artifacts: `$SB/apps/verify_up_local_basic_1/{server_098.log,server_run1_099a1.log,server_run2_099a1.log,package.json.0.9.8,package.json.0.9.9a1}`.

## VERIFICATION (adversarial re-check #2, 2026-08-28): vite configLoader:'native' warning

Claim verified: "reflex-generated vite.config.js imports ./vite-plugin-safari-cachebust
without a file extension; vite 8.2.0 warns about configLoader:'native' incompatibility
twice per dev start on 0.9.9a1; absent on 0.9.8". **CONFIRMED** (severity low, not a
regression in reflex's config code — the warning newly surfaces because 0.9.9a1 bumps
the pinned vite from 8.0.16 to 8.2.0).

Independent reproduction (fresh minimal app, NOT the cluster's example apps), working dir
`$SB/apps/verify_up_local_basic_0/vitewarn/`, shared PyPI-only venv `$SB/envs/smoke`
(reflex==0.9.9a1), FP 3760 / BP 8760:

1. `reflex init --template blank` -> generated `.web/vite.config.js` line 4 is
   `import safariCacheBustPlugin from "./vite-plugin-safari-cachebust";` (no extension).
2. `reflex run --loglevel debug` (`server_run4.log`): frontend reaches 200; log contains
   exactly **2** occurrences of
   `(!) Your Vite config uses features that are unsupported by configLoader: 'native'`
   each citing `import "./vite-plugin-safari-cachebust" without a file extension
   (vite.config.js:4:35)` (log lines 167/173). Twice because `react-router dev` loads the
   vite config in both its typegen watcher and the dev server.
3. Root-cause counter-test: in the same `.web` (same node_modules, vite 8.2.0), adding
   the `.js` extension to that one import and re-running the frontend directly
   (`frontend_direct_fixed.log`) -> **0** occurrences; reverting it
   (`frontend_direct.log`) -> warning is the first thing printed. So the warning is
   caused solely by the extensionless import, not an env quirk.

Source attribution (identical in the 0.9.9a1 wheel and the release checkout):
- Template emitting the import: `packages/reflex-base/src/reflex_base/compiler/templates.py`
  line 658 (`import safariCacheBustPlugin from "./vite-plugin-safari-cachebust";`).
- Vite pin: `packages/reflex-base/src/reflex_base/constants/installer.py` line 154
  (`"vite": "8.2.0"`).

Refutation attempts, all negative:
- Pre-existing on 0.9.8? The extensionless import IS pre-existing (0.9.8 wheel
  `reflex_base/compiler/templates.py` line 579, identical), but 0.9.8 pins vite 8.0.16
  which does not emit this check, so no 0.9.8 log (cluster artifacts or otherwise)
  contains `configLoader`. The user-visible warning is new with 0.9.9a1.
- App bug / misuse? No — reproduced on a pristine `reflex init --template blank` app with
  zero user code changes; the flagged file is 100% reflex-generated and regenerated on
  every `reflex run` (hand-editing `.web/vite.config.js` is not a durable user workaround).
- Env quirk? No — warning text pinpoints the import; counter-test above flips it off/on
  deterministically. (Env quirk hit during verification, unrelated to the claim: as also
  noted by verifier #1, prefixing commands with `NO_PROXY=localhost,127.0.0.1` clobbers
  the sandbox's ambient bypass for registry.npmjs.org and makes bun installs fail with
  `ConnectionClosed`; server_run.log/server_run2.log/server_run3.log show those failed
  installs. Warm bun cache or keep the ambient NO_PROXY to avoid it.)

Visibility nuance: the warning rides on the frontend process's stdout. `reflex run` only
streams it at `--loglevel debug` (lines appear with `Debug:` prefix); at the default
loglevel users don't see it, and `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` suppresses it.
Severity "low" is right. It is however real forward-compat debt: vite states
configLoader:'native' is "planned to become the default in a future major version", at
which point every reflex app's dev server fails to load its config until reflex ships the
one-token fix (add `.js` in templates.py; the sibling file `vite-plugin-safari-cachebust.js`
already sits next to vite.config.js in `.web`).

**Verdict: confirmed=true** — genuine reflex 0.9.9a1 defect (framework-generated config,
trivial fix), not an enterprise incompatibility. Not a behavioral regression today (dev
server works; warning only), so keep severity low.
Verification artifacts: `$SB/apps/verify_up_local_basic_0/vitewarn/{server_run4.log,frontend_direct.log,frontend_direct_fixed.log,init.log}`.

## VERIFICATION 2 (adversarial re-check, 2026-08-28)

**Claim verified:** "basic_crud: GET /products/<missing id> returns HTTP 200 with a
serialized HTTPException body instead of a 404 (api_get_missing step); example-app bug,
identical on 0.9.8 and 0.9.9a1."

Reproduced independently in `$SB/apps/verify_up_local_basic_2/` (fresh copies of the app,
fresh PyPI-only Python 3.11 venvs, `reflex run --backend-only` since this is a pure API
check — no frontend needed):

1. **0.9.9a1** (`basic_crud/`, venv `reflex[db]==0.9.9a1` + fastapi 0.141.1, `reflex db
   migrate`, backend on :8768): `curl http://localhost:8768/products/999999` ->
   `HTTP/1.1 200 OK` body `{"status_code":404,"detail":"Not Found","headers":null}` —
   exactly as claimed. Sanity: `/ping` 200, `GET /products` 200 `[]`, unknown route 404
   (reflex/FastAPI 404 machinery intact). No traceback in `server_099a1.log`.
2. **0.9.8 baseline** (`basic_crud_098/`, venv `reflex[db]==0.9.8` + fastapi 0.141.1,
   backend on :8769): byte-identical response (200, same 55-byte body). **Not a
   regression** — matches the recorded `api_get_missing` step in all three archived
   result.json files (0.9.8 / 0.9.9a1 / cold).
3. **Root cause is pure FastAPI semantics, zero reflex involvement.** `basic_crud/api.py`
   line 18: `return spec if spec else HTTPException(status_code=404)` — the handler
   *returns* the exception instead of *raising* it, so FastAPI serializes it as a 200
   JSON body. Demonstrated in-process against the same fastapi 0.141.1 (TestClient,
   no reflex): returned HTTPException -> `200 {"status_code":404,...}`; raised ->
   `404 {"detail":"Not Found"}`. (`add_product`'s 402 path on line 35 has the same bug.)
4. **Bug pre-exists upstream.** The tested app's `basic_crud/` package is byte-identical
   (`diff -r`) to `/home/user/reflex-dev/reflex-examples/basic_crud/basic_crud` — the
   testing agent did not introduce it.

**Verdict: claim accurate and reproducible, but NOT a defect a fix-agent for the 0.9.9a1
release should act on** (confirmed=false): it is a bug in the upstream reflex-examples
`basic_crud` app (return vs raise), FastAPI behaves by design, behavior is identical on
0.9.8, and reflex's own exception handling is uninvolved. Appropriate follow-up, if any,
is a one-line `raise` fix in reflex-dev/reflex-examples.
Verification artifacts: `$SB/apps/verify_up_local_basic_2/basic_crud/server_099a1.log`,
`$SB/apps/verify_up_local_basic_2/basic_crud_098/server_098.log`.
