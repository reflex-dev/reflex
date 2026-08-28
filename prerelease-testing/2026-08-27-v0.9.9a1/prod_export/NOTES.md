# prod_export cluster — React Router 8 / PROD / EXPORT / PREVIEW (reflex 0.9.9a1)

Tested 2026-08-28 on the shared smoke venv (`$SB/envs/smoke`, reflex==0.9.9a1, Python 3.11,
Node v22.22.2, bun 1.3.11). App: `prodapp/` — multi-page (/, /about, /post/[pid]) with
counter state, controlled input, foreach, event chain (`yield Other.handler()`), on_load on
the dynamic route, `rx.cond`, and two custom react-router components:

- `RRNavLink` — `library="react-router"`, `tag="NavLink"` (genuine RR8 component import)
- `UseLocationSpan` — `rx.el.Span` subclass importing the `useLocation` hook via
  `add_imports({"react-router": ["useLocation"]})` + `add_hooks`, rendering
  `routerLocation.pathname` into `#location-badge`

## How to rerun

```
SB=<scratchpad>; cd apps/prod_export/prodapp
# prod (NOTE: prod/preview require ONE port for both frontend+backend):
REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex run --env prod --frontend-port 8460 --backend-port 8460 --loglevel debug
# browser pass (18 checks; captures console/pageerrors/4xx+screenshots):
$SB/envs/driver/bin/python ../drive_app.py http://localhost:8460 prod
# export:
$SB/envs/smoke/bin/reflex export --loglevel debug
# static-host test: REFLEX_API_URL=http://localhost:8461 reflex export --frontend-only,
# unzip frontend.zip -> static_site/, python3 -m http.server 3461, and
# reflex run --backend-only --env prod --backend-port 8461, then
# ../drive_app.py http://localhost:3461 export_static --skip-dynamic-direct
# preview:
reflex run --env preview --frontend-port 8462 --backend-port 8462
```

Do NOT export `NO_PROXY=localhost,...` around bun installs in this container — it clobbers
the default no_proxy that whitelists registry.npmjs.org, and bun then dies with
`ConnectionClosed downloading package manifest ...` after ~500 s (that was an env mistake,
not a reflex bug; the driver scripts only need `curl --noproxy`/NO_PROXY for localhost polling).

## Results (all browser passes on Chromium via Playwright)

| Mode | Result |
|---|---|
| prod (`--env prod`, single port 8460) | 18/18 checks pass, hydration clean, no console errors |
| export → static http.server + `--backend-only` | 17/17 pass (SPA-fallback check skipped: python http.server has no fallback) |
| preview (`--env preview`, port 8462) | 18/18 pass + hot path verified (edit source → workers reload → rebuild → refresh shows change) |
| dev (baseline for custom components) | 18/18 pass, zero console noise |

- Backend `REFLEX_ENV_MODE` observed via an event handler: `prod` / `preview` / `dev` as expected.
- Prod prerender: `/` and `/about` served with full prerendered HTML (canary text present in
  raw page source; `/about` 307-redirects to `/about/`). `Prerender (html)` lines in build log.
  Preview mode builds in **SPA mode** instead (no prerender) — intentional-looking, but the
  raw HTML in preview is just the hydration shell.
- `reflex export` exit 0 — **no ECONNREFUSED** (the #6857 fix works in this docker-like env).
  frontend.zip contains index.html, about.html AND about/index.html, 404.html,
  `__spa-fallback.html`, sitemap.xml, gzip twins of everything.
- `REFLEX_API_URL` baked correctly into `assets/reflex-env-*.js` (ping/ws/upload URLs).
- `.web/package.json`: react-router 8.3.0, @react-router/* 8.3.0, vite 8.2.0,
  NO react-router-dom, `"overrides": {}` (postcss override gone). ✔

## Anomalies / findings

1. **`library="react-router-dom"` negative test (per #6854)** — a custom component
   declaring `library="react-router-dom"`, `tag="Link"`:
   - dev: reflex silently `bun add`s **react-router-dom@^7.18.2** (unpinned!) next to
     react-router 8.3.0 (nested react-router@7.18.2 under it). The v7 Link *renders and
     navigates* in dev (vite resolves the nested import to the hoisted v8 copy) — no
     warning at all, and the stray dep is persisted into `reflex.lock`.
   - prod: build FAILS during prerender with
     `TypeError: Cannot destructure property 'basename' of 'React10.useContext(...)' as it is null`
     (stack: `react-router-dom/node_modules/react-router/dist/development/...` at LinkWithRef)
     → `Prerender: Request failed for /: Received a 500 ... from entry.server.tsx`, exit 1.
     The stack *mentions* react-router-dom so a careful reader can find it, but there is no
     targeted "react-router-dom is gone in RR8; use library=\"react-router\"" hint, and the
     dev-mode silence makes it a prod-only surprise. Log: `prod_baddom.log`.
   - Pruning path works: after removing the component, the next install runs
     `bun remove react-router-dom` and package.json is clean again (`export_prune.log`).
2. **`reflex run` hangs after the fatal node-version error (npm path)** — with
   `REFLEX_USE_NPM=1` and an old node on PATH (fake shim printing v22.12.0,
   `fakenode/node`), the error message itself is good
   (`Reflex requires node version 22.22.0 or higher ... detected ... 22.12.0`), and granian
   logs `Unexpected exit from worker-1` — but the parent process then **hangs indefinitely**
   (killed by `timeout` at 90 s and 150 s in two runs; "Reflex app stopped." only appears
   via the atexit handler on SIGTERM). Logs: `oldnode_npm.log`, `oldnode_npm2.log`.
3. **npm↔bun switching corrupts the persisted lockfile pair** — after the failed
   REFLEX_USE_NPM=1 runs (which still wrote `package-lock.json` + copied all three files
   into `reflex.lock/` despite the version-check SystemExit), a subsequent plain bun run
   fails: `bun install --frozen-lockfile` → `error: lockfile had changes, but lockfile is
   frozen`, and reflex prints an actionable message ("The persisted lockfile is out of sync
   ... Delete the reflex.lock directory and rerun"). Deleting `reflex.lock/` did recover
   cleanly. Evidence copy: `reflex.lock.outofsync-evidence/`, log `oldnode_bun.log`.
4. **Old node + bun (default) path**: only a warning
   (`Your version (22.12.0) of Node.js is out of date. Upgrade to 22.22.0 or higher.`) and
   the package executor becomes `['bun', '--bun']` — run continues (my run then hit finding
   3's lockfile error, which is unrelated to node).
5. **Direct-load of a dynamic route returns HTTP 404 in prod/preview** — `GET /post/7`
   returns status 404 with the `__spa-fallback.html` body; the page then hydrates and
   renders pid=7 correctly, so users see a working page but crawlers/health checks see 404.
   Dev mode returns 200 for the same URL. Present in both prod and preview single-port
   granian serving. (Arguably by-design for SPA fallback; noting the dev/prod status
   difference.)
6. **New vite 8.2.0 build warnings on every prod build/export** (not present wording in
   0.9.8-era logs; introduced with the 8.0.16→8.2.0 bump):
   - `Warning: Invalid input options (1 issue found) - For the "jsx". Invalid key: Expected never but received "jsx".`
   - `WARN advancedChunks option is deprecated, please use codeSplitting instead.`
   Both appear twice (client + ssr builds). Cosmetic today, but the advancedChunks one is a
   deprecation on reflex's own vite config.
7. **Known native-loader warning unchanged** — the `configLoader: 'native'` /
   `vite-plugin-safari-cachebust` extension-less import warning is still a warning in
   vite 8.2.0, NOT an error. Seen on every build (dev/prod/preview/export).
8. Prod/preview enforce `frontend and backend must run on the same port` when both flags are
   passed with different values (already on the shared ledger; repeat here because it affects
   scripting this cluster: use a single port).
9. Benign: `Unable to bind to any port for 10: [Errno 97] Address family not supported by
   protocol` debug line on every startup (IPv6 probe in this container), then IPv4 succeeds.
10. My own authoring error worth knowing: subclassing `rx.el.Span` AND setting
    `library="react-router"` makes reflex import the `span` *tag* from react-router →
    prod build fails with `[MISSING_EXPORT] "span" is not exported by ...react-router...`
    (clear, actionable). Import hooks via `add_imports` without overriding `library`.

## Files

- `prodapp/` — app source (rxconfig.py, prodapp/prodapp.py)
- `drive_app.py` — Playwright driver (18 checks; see header for usage)
- `*_console.json` — full console dumps per pass (prod/export_static/preview/dev)
- `*.png` — screenshots per mode (index initial/after, about, post42, direct-load, 404)
- logs: `prod_run.log` (incl. first failed span build at its head... see
  `prod_baddom.log` for the react-router-dom failure), `export.log`, `export_fe.log`,
  `export_prune.log`, `preview_run.log`, `dev_run.log`, `oldnode_npm*.log`,
  `oldnode_bun.log`, `recovery_run.log`, `init.log`
- `fakenode/node` — the fake node shim used for the version-floor tests
- `reflex.lock.outofsync-evidence/` — persisted lockfile trio from finding 3
- `prod_index_source.html`, `prod_about_source.html` — raw prod page sources (prerender proof)
