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

## VERIFICATION (independent, adversarial — 2026-08-28)

Verified finding 1 (`library="react-router-dom"` custom component) from the repro steps
alone, with a fresh minimal app (`verification/vapp/` — `BadDomLink(rx.Component)` with
`library="react-router-dom"`, `tag="Link"`, `to: rx.Var[str]`; driver
`verification/drive_verify.py`). **CONFIRMED**, all four claimed behaviors reproduced:

1. **0.9.9a1 dev** (ports 3960/8960): `bun add ... 'react-router-dom' ...` with the bare
   unpinned name among otherwise exactly-pinned deps → `installed react-router-dom@7.18.2`;
   `.web/package.json` gains `"react-router-dom": "^7.18.2"` next to `"react-router": "8.3.0"`
   (nested `react-router@7.18.2` under it); the stray dep is persisted into
   `reflex.lock/package.json`. Playwright: link renders (`<a href="/other">`), click
   navigates, **zero** console errors/warnings, no reflex-side warning of any kind.
   Log: `verification/logs/verify_dev_099a1.log`.
2. **0.9.9a1 prod** (`--env prod`, single port 8960): exit 1 at prerender with the exact
   claimed error — `TypeError: Cannot destructure property 'basename' of
   'React10.useContext(...)' as it is null` at `LinkWithRef` in
   `.web/node_modules/react-router-dom/node_modules/react-router/dist/development/...`
   → `Prerender: Request failed for /: ... 500 ... entry.server.tsx`.
   Log: `verification/logs/verify_prod_099a1.log`.
3. **0.9.8 baseline** (same app file, separate PyPI venv, ports 3961/8961): react-router-dom
   is a first-party dep pinned **exactly** at 7.18.2 (single copy), so the identical
   component works in dev AND prod (prod prerenders `/` and `/other` cleanly; Playwright
   render+navigate pass, no console errors). Logs: `verification/logs/verify_dev_098.log`,
   `verify_prod_098.log`.
4. **Source check** (release branch `origin/r/pre-2026.08.27-33148999938`):
   `PackageJson.DEPENDENCIES` dropped `react-router-dom` (0.9.8 had it at
   `_react_router_version`); `App._get_frontend_packages` treats any library not in
   DEPENDENCIES/DEV_DEPENDENCIES as a generic custom package and installs it unpinned via
   `bun add`; the stale-package pruning in `reflex.utils.js_runtimes.install_frontend_packages`
   is fully generic. There is **no** react-router-dom-specific diagnostic anywhere, even
   though the news fragment explicitly names this exact migration
   (`library = "react-router-dom"` → `react-router`).

Refutation angles ruled out: not an environment quirk (mechanism is structural — two
react-router major versions, the v7 Link reads v7's NavigationContext which is null inside
the v8 router during SSR; dev-mode vite resolution happens to dedupe so dev works); not
pre-existing (0.9.8 works end-to-end); "API misuse" only in the sense that the breaking
change is documented in the release notes — but the framework gives zero runtime signal,
dev actively succeeds, and prod fails with a third-party stack trace, which is exactly the
discoverability gap claimed. Severity **medium** is fair: functional breakage is documented
and intended; the defect a fix-agent should act on is the missing targeted
compile/install-time warning or error for `library="react-router-dom"` (a name the
framework shipped as its own dependency until 0.9.8 and names in its own migration note).
Unpinned install of custom libraries is generic behavior, not specific to this package —
it just makes this case worse (silent drift next to the exact-pinned first-party set).

Caveat: nothing beyond finding 1 was re-verified here (findings 2-10 untouched).

## VERIFICATION (adversarial re-check of finding 2 — "reflex run hangs after fatal node-version error, npm path")

Verified 2026-08-28 by a separate agent, independently from the repro steps alone
(fresh `reflex init --template blank` app, smoke venv reflex==0.9.9a1, own fake-node
shim printing v22.12.0). **CONFIRMED — reproduced on the first attempt and on a
second instrumented run.**

- `PATH=<fakenode>:$PATH REFLEX_USE_NPM=1 timeout 90 reflex run --frontend-port 3964
  --backend-port 8964` → prints the correct fatal error within seconds, then runs
  until killed (exit=124). Same log shape as `oldnode_npm.log`.
  Logs: `verify_oldnode_npm_0.9.9a1.log`, `verify_oldnode_npm_0.9.9a1_run2.log`.
- Mechanism correction vs. the original report: the SystemExit is NOT in a granian
  worker, and `[ERROR] Unexpected exit from worker-1` is not the cause — it appears
  only during SIGTERM teardown (in the instrumented run it was absent for the whole
  240 s hang and showed up only at kill time). During the hang the **backend is
  actually up** (granian worker alive, `GET /ping` on the backend port returns 200)
  while the frontend port never listens. Root cause (0.9.9a1 source):
  `reflex/reflex.py::_run_dev` submits `exec.run_frontend` to a
  `ThreadPoolExecutor` via `processes.run_concurrently_context` and runs granian
  `serve()` on the main thread inside the `with` block; futures are only
  `.result()`-checked *after* the block, i.e. after `serve()` returns (= never). The
  `SystemExit(1)` from `js_runtimes.validate_frontend_dependencies`
  (reflex/utils/js_runtimes.py:377) dies silently inside the thread's Future. Any
  exception in `run_frontend` (bad custom bun path at js_runtimes.py:346, missing
  package managers at :370, or a crash launching vite) is swallowed the same way →
  dev server hangs as backend-only with no frontend and never exits non-zero.
  SIGTERM/Ctrl+C do still terminate it cleanly (timeout's SIGTERM worked; no
  kill -9 needed), so the pain is unattended/CI runs and the missing prompt
  non-zero exit.
- 0.9.8 baseline (own venv, reflex==0.9.8 from PyPI, blank app, shim v22.11.0 which
  is below 0.9.8's floor 22.12.0): the identical thread/Future structure exists in
  0.9.8's source, but the scenario is unreachable there — with REFLEX_USE_NPM=1 the
  npm install itself fails first on the MAIN thread (`npm error code EOVERRIDE:
  Override for postcss@^8.5.23 conflicts with direct dependency`, also with a clean
  node_modules) and `reflex run` exits promptly with code 1. Log:
  `verify_oldnode_npm_0.9.8.log`. So: latent pre-existing flaw, but newly *reachable*
  in 0.9.9a1 (postcss override removed → npm install now succeeds, and the node
  floor was raised 22.12.0 → 22.22.0, so real npm users with a slightly-old node hit
  it). Net behavior change for the npm+old-node case: 0.9.8 = prompt exit 1 (albeit
  from a different bug), 0.9.9a1 = indefinite hang. Severity "medium" seems right.
- Suggested fix direction for the fix-agent: fail fast — e.g. run
  `validate_frontend_dependencies(init=False)` on the main thread before entering
  `run_concurrently_context`, and/or have `run_concurrently_context` propagate a
  future's exception promptly (add_done_callback that signals/kills the server)
  instead of only after the with-body returns.

## VERIFICATION 3 (adversarial re-check of finding 6 — "vite 8.2.0 bump introduces two new prod-build warnings")

Verified 2026-08-28 by a separate agent, independently from the repro steps alone
(fresh `reflex init --template blank` apps, artifacts in `verification3_vite_warnings/`).
**Warnings CONFIRMED as a real, actionable framework defect — but the "introduced by the
8.0.16→8.2.0 bump / not present in 0.9.8-era logs" attribution is REFUTED: 0.9.8 with
vite 8.0.16 emits the exact same two warnings. Pre-existing, NOT a 0.9.9a1 regression.**

- 0.9.9a1 (shared PyPI smoke venv, blank app `vwapp/`): both `reflex export --loglevel
  debug` (exit 0) and `reflex run --env prod --frontend-port 8972 --backend-port 8972
  --loglevel debug` (server serves HTTP 200) log, exactly twice each (client + ssr build):
  `Warning: Invalid input options (1 issue found) - For the "jsx". Invalid key: Expected
  never but received "jsx".` and `WARN advancedChunks option is deprecated, please use
  codeSplitting instead.` Logs: `logs/export_099a1.log` (lines 122-161),
  `logs/prod_run_099a1.log` (lines 136-175). vite pin in `.web/package.json` = 8.2.0.
- 0.9.8 baseline (separate PyPI venv reflex==0.9.8, identical blank app `vwapp098/`,
  vite pin 8.0.16): `reflex export --loglevel debug` logs the SAME two warnings, also
  twice (`logs/export_098.log` lines 117-185, `vite v8.0.16 building ...`). Corroborated
  by two other clusters' 0.9.8 logs (`registration_context/dynapp098_run_prod.log`,
  `pydantic_optional/verify1_prod_warnings/vpapp098_prod_run.log`) and by the independent
  VERIFICATION 2 in `pydantic_optional/NOTES.md`, which reached the same conclusion.
- Root cause (framework, not env/user error): the generated `.web/vite.config.js` emits
  `build.rollupOptions.jsx: {}` and `build.rollupOptions.output.advancedChunks` — from
  `packages/reflex-base/src/reflex_base/compiler/templates.py` (~line 736 on release
  branch `origin/r/pre-2026.08.27-33148999938`); `git show
  reflex-base-v0.9.8:...templates.py` has the identical block (~line 652). rolldown-vite
  rejects `jsx` as a rollupOptions input key and deprecates `advancedChunks` in BOTH
  pinned versions.
- Additional mitigation not in the original claim: the warnings only surface with
  `--loglevel debug`. A default-loglevel `reflex export` shows neither
  (`logs/export_099a1_defaultlog.log`, 5 lines total, 0 matches) — reflex only echoes the
  vite build output at debug level. Build output correctness is unaffected (export exit 0,
  prod server serves and the original cluster's browser passes were clean).
- Verdict for a fix-agent: low-severity template cleanup — drop `jsx: {}` and migrate
  `advancedChunks` → `codeSplitting` in the vite config template. Do NOT file it as a
  vite-bump regression; the changelog framing in finding 6 ("introduced with the
  8.0.16→8.2.0 bump", "not present wording in 0.9.8-era logs") is incorrect. The
  advancedChunks deprecation does carry future-removal risk, which is the real reason to
  act.

Rerun: `cd verification3_vite_warnings/vwapp && REFLEX_TELEMETRY_ENABLED=false
<smoke-venv>/bin/reflex export --loglevel debug 2>&1 | grep -E 'Invalid input|advancedChunks'`
(same for `vwapp098/` with a reflex==0.9.8 venv). Processes: prod server on 8972 killed
after the check; exports self-terminate; verified `ps` clean of this agent's processes.

## VERIFICATION of finding 3 (npm<->bun reflex.lock corruption) — independent, adversarial (2026-08-28)

Reproduced from the repro steps alone with a FRESH blank app (`reflex init --template blank`,
smoke venv 0.9.9a1, ports 3968/8968; evidence in `verification/lockfile_verify/`).
**CONFIRMED as a genuine 0.9.9a1 defect**, with two sharpenings.

Reproduction (all steps as claimed):
1. Baseline bun dev run: healthy, `reflex.lock/` = {bun.lock, package.json} with EXACT pins.
2. `REFLEX_USE_NPM=1` + old-node shim (`fakenode/node` printing v22.12.0): the fatal
   `Reflex requires node version 22.22.0...` fires only AFTER `_compile_app()` already ran the
   full npm install (npm install + npm add, ~6.5 s in `run2b_npm_oldnode.log` line 1550, error
   at line 1554). Result: `.web/package-lock.json` created and the trio
   {bun.lock, package-lock.json, package.json} persisted into `reflex.lock/`, with
   package.json rewritten by npm to CARET ranges (`^19.2.8`...) while bun.lock still records
   exact workspace specs — the inconsistent pair (`snap_after_run2b_npm_oldnode/`).
   Also corroborated finding 2 in passing: the parent stayed alive >60 s after the fatal error.
3. Next plain bun run: `bun install --frozen-lockfile` -> `error: lockfile had changes, but
   lockfile is frozen` -> reflex's actionable "delete the reflex.lock directory" message,
   exit 1 (`run3_bun_after_npm.log`).
4. Recovery works: `rm -rf reflex.lock` -> clean bun-only lock regenerated, frontend 200
   (`run4_recovery.log`).

Sharpening A — the "failed run" aspect is INCIDENTAL: a fully SUCCESSFUL
`REFLEX_USE_NPM=1` run with real node (app compiled, served 200, `run5_npm_goodnode.log`)
persists the identical poisoned trio, and the next plain bun run aborts the same way
(`run6_bun_after_good_npm.log`). Root cause: reflex never invalidates/regenerates the
persisted `bun.lock` when the project is installed with npm; npm's default save-prefix
rewrites package.json pins to `^x.y.z`, desyncing it from bun.lock's exact specs; and
`_persisted_lockfile_implies_npm()` returns False when BOTH lockfiles exist, so the project
auto-selects bun again on the next run. Fix directions for a fix-agent: drop/refresh the
other manager's lockfile on manager switch (or use `--save-exact` on the npm path), and/or
prefer npm when reflex.lock carries a fresher package-lock.json.

Sharpening B — NOT reproducible on 0.9.8, for an unexpected reason: the lockfile-persistence
code is byte-identical in behavior (0.9.8 vs 0.9.9a1 diff of js_runtimes.py /
frontend_skeleton.py is logging-refactor only; the mechanism dates to 0.9.3/0.9.6), BUT on
0.9.8 the same repro dies EARLIER inside the npm install step with
`npm error code EOVERRIDE — Override for postcss@^8.5.23 conflicts with direct dependency`
(0.9.8 ships `PackageJson.OVERRIDES = {"postcss": "8.5.23"}`), so
`sync_web_lockfiles_to_root` never runs, `reflex.lock/` stays clean, and the subsequent bun
run serves 200 (`runB098_npm_oldnode.log`, `runC098_bun_after_npm.log`; app `vlock098`,
ports 3969/8969). 0.9.9a1 removed the postcss override (`OVERRIDES = {}`), which makes the
npm escape hatch complete for the first time — and thereby exposes the poisoning. So: the
REFLEX_USE_NPM path on 0.9.8 was broken outright (EOVERRIDE); on 0.9.9a1 it works but
poisons the persisted lock for bun. In practice the reported breakage is new in 0.9.9a1.

Refutation angles ruled out: not an environment quirk (structural: npm caret rewriting vs
bun.lock exact specs); not API misuse (REFLEX_USE_NPM is reflex's own documented escape
hatch and the poisoning also hits fully successful runs); not pre-existing-in-practice (see
Sharpening B). One repro caveat: the mutation only happens when a (re)compile actually runs —
a run whose compile is cache-skipped (unchanged app, same mode) fails the node check fast
WITHOUT mutating state (`run2_npm_oldnode.log`); any code edit or mode switch triggers the
recompile, so real-world sequences hit it. Severity **low** is fair given the actionable
message and clean recovery, but note the successful-run variant means ANY project that ever
ran with REFLEX_USE_NPM=1 will refuse its next bun run after the next recompile.
