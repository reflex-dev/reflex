# Cluster `up_upload_clock` — upgrade testing 0.9.8 -> 0.9.9a1 (reflex-examples: upload, clock)

Date: 2026-08-28. Apps copied from /home/user/reflex-dev/reflex-examples (read-only checkout).
Verdict: **no regressions found in either app.** In-place upgrade migration (lockfile save/restore,
react-router-dom pruning, react-router 7.18.2 -> 8.3.0, vite 8.0.16 -> 8.2.0) worked cleanly on both
apps, and the cold fresh-`.web` path produced an identical package.json and identical behavior.

## Procedure (per app)

1. Copy app dir from reflex-examples; per-app venv:
   `uv venv <app>/venv --python 3.11 && uv pip install --python <app>/venv/bin/python -r <app>/requirements.txt 'reflex==0.9.8'`
   (requirements floor `reflex>=0.9.2` resolves to 0.9.8 stable; no prerelease flag).
2. Baseline run on 0.9.8, browser-driven with Playwright (Chromium at /opt/pw-browsers/chromium),
   capturing server log, console, 4xx/5xx/failed requests, screenshots.
3. In-place upgrade in the SAME venv + SAME app dir (preserves `.web/`, `reflex.lock/`,
   package.json state): `uv pip install --python <app>/venv/bin/python --prerelease=allow -U 'reflex==0.9.9a1'`.
   Re-run, watch first-run migration log, re-run the same driver, diff `.web/package.json`.
4. Cold run: `rm -rf .web`, run again on 0.9.9a1, re-run driver.

Ports used: upload FP 3140 / BP 8140, clock FP 3141 / BP 8141. One server at a time.

## Rerun instructions

```sh
WD=<this directory>   # containing upload/, clock/, drive_upload.py, drive_clock.py
DRIVER=<venv with playwright>/bin/python   # chromium at /opt/pw-browsers/chromium

# upload app
cd $WD/upload && REFLEX_TELEMETRY_ENABLED=false setsid ./venv/bin/reflex run \
  --frontend-port 3140 --backend-port 8140 --loglevel debug > server.log 2>&1 &
# poll http://localhost:3140 until 200 (curl --noproxy '*'), then:
cd $WD && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $DRIVER drive_upload.py http://localhost:3140 <artifacts_dir> $WD/upload/uploaded_files <label>

# clock app
cd $WD/clock && REFLEX_TELEMETRY_ENABLED=false setsid ./venv/bin/reflex run \
  --frontend-port 3141 --backend-port 8141 --loglevel debug > server.log 2>&1 &
cd $WD && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $DRIVER drive_clock.py http://localhost:3141 <artifacts_dir> <label>
```

Do NOT export NO_PROXY into the reflex server environment (breaks bun installs through the proxy);
only set it on curl/Playwright processes. Note: backgrounded `reflex run` did not exit on
SIGTERM/SIGINT in this environment; kill its process group (`kill -KILL -<pgid>`).

## upload app (17 checks x 3 runs: 0.9.8 baseline, 0.9.9a1 in-place, 0.9.9a1 cold)

Flows driven for real in Chromium: select files (text + png), re-select (unicode+spaces filename
`héllo wörld 测试 файл.txt` replaces prior selection), upload 3 files via the Upload button,
verify bytes on disk in `uploaded_files/` (content roundtrip incl. unicode name), throttled 5MB
upload via CDP `Network.emulateNetworkConditions` (300KB/s) -> "Uploading..." indicator + progress
bar (`aria-valuenow` advancing) -> click `cancel` link (`rx.cancel_upload`) -> upload aborts, no
partial file on disk -> a subsequent upload (filename with spaces) still works. Fresh browser
context verifies the Files list renders links for all uploads and `/_upload/<name>` serves exact
content (200) for ascii and unicode names.

Results: **identical on all three runs** — every check that passed on 0.9.8 passed on 0.9.9a1
(in-place and cold). No new console messages (zero unexpected console entries on every run),
no failed requests other than the *expected* `net::ERR_ABORTED` on `/_upload` from the cancel test.
Files uploaded under 0.9.8 were still served by the upgraded 0.9.9a1 server (checked before
cleaning the upload dir).

Pre-existing app-level quirks, identical on 0.9.8 and 0.9.9a1 (NOT regressions):

- `State.files` is a dependency-less cached `@rx.var`; it never recomputes for an existing session
  token, so the "Files:" list stays stale after upload even across page reload (session token is in
  sessionStorage). A fresh browser context shows the list correctly. See
  `artifacts/upload/*/03_after_upload.png` (empty list) vs `06_fresh_context_list.png` (full list).
- After reload the progress bar stays at its last persisted value (state persists per token).

### Migration observations (first 0.9.9a1 run, artifacts/upload/099a1/server.log)

- 0.9.8 had already created `reflex.lock/` (app root) with bun.lock+package.json; 0.9.9a1's first
  run logged `Restoring lockfiles` (copied reflex.lock/bun.lock into the refreshed `.web`), then
  re-saved both files back to `reflex.lock/` after installing.
- `bun remove --legacy-peer-deps react-router-dom` -> "Removed: 1"; package.json diff
  (`artifacts/upload/package.json.diff`): `react-router-dom` dropped; `react-router`,
  `@react-router/node`, `@react-router/dev`, `@react-router/fs-routes` 7.18.2 -> 8.3.0; `vite`
  8.0.16 -> 8.2.0; `"overrides": {"postcss": "8.5.23"}` retained unchanged.
- Transient bun `warn: incorrect peer dependency "react-router@7.18.2"` (x2) during the staged
  dev-deps install (react-router still 7.18.2 while @react-router/dev is already 8.3.0); resolved
  by the following `bun add react-router@8.3.0` step. Cosmetic only.
- NEW (not in the 0.9.8 log): Vite 8.2.0 debug-level warning
  `Your Vite config uses features that are unsupported by configLoader: 'native' ... import
  "./vite-plugin-safari-cachebust" without a file extension (vite.config.js:4:35)`, suggesting
  `VITE_CONFIG_NATIVE_IGNORE_WARNING=true`. Benign today (native loader not yet default) but the
  reflex-emitted vite.config.js template will break if/when Vite flips the default; worth fixing
  the template import to include the `.js` extension.
- The 5 React-Router "Future Flag Warning" lines from the 0.9.8 log are GONE on 0.9.9a1
  (react-router 8.3.0) — an improvement.
- Cold run (rm -rf .web): package.json byte-identical to the in-place-upgrade one; lockfile
  restored from `reflex.lock/`; frontend up in ~20s; no bun peer-dep warnings; same behavior.

## clock app (12 checks x 3 runs)

The stock example does NOT use rx.moment (it's a background-task `tick` + pytz app), so to cover
the brief's "alpha core + stable reflex-components-moment 0.9.3" interplay a `/moment` page was
added to `clock/clock/clock.py` BEFORE the 0.9.8 baseline (identical source on all runs):
`rx.moment(interval=1000, format="HH:mm:ss", tz=State.valid_zone, id="moment_clock")` + the same
timezone select. reflex-components-moment stayed at 0.9.3 stable through the upgrade (verified via
`uv pip list`); moment@2.30.1 / moment-timezone@0.6.2 / react-moment@1.2.2 npm packages installed
on both versions.

Flows driven: initial render (analog + digital clock, radix switch + select), clock stopped
on_load, flip switch on -> `@rx.event(background=True)` tick task advances seconds, digital time
correct for default zone US/Pacific (checked against real UTC offset), radix select switch to
Asia/Tokyo -> hour/meridiem correct, `rx.Cookie` zone persists across reload while on_load stops
the clock again, switch off stops ticking, `/moment` page renders ticking moment clock in the
cookie's zone (Tokyo, exact to the second vs driver clock), interval ticking, select London ->
moment shifts to London time instantly.

Results: **12/12 pass on 0.9.8, 12/12 on 0.9.9a1 in-place upgrade, 12/12 on cold run.** Zero
unexpected console messages, zero failed requests, no server-log tracebacks on any run.
Screenshots visually identical across versions (artifacts/clock/*/0*.png). Migration log pattern
identical to the upload app (lockfile restore, react-router-dom "Removed: 1", same staged
upgrade to react-router 8.3.0 + vite 8.2.0, same transient peer-dep warns, same vite configLoader
notice); moment npm packages re-added cleanly. package.json diffs saved
(`artifacts/clock/package.json.diff`); cold-run package.json identical to the upgraded one.

Note: `rx.switch(is_checked=State.running, ...)` — `is_checked` is not a real radix Switch prop;
the switch is effectively uncontrolled, but on_change wiring makes behavior correct. Identical on
both versions (visible in 02_ticking.png: switch shows checked after click on both).

## Artifact map

- `upload/`, `clock/` — app sources + requirements (venv/.web/uploaded_files/reflex.lock stripped
  in the repo copy). `clock/clock/clock.py` contains the added `/moment` page (marked by comment).
- `drive_upload.py`, `drive_clock.py` — Playwright drivers (usage strings at top).
- `artifacts/<app>/{098,099a1,cold}/` — per-run: `server.log`, `results.json`, `console.json`,
  `bad_responses.json`, `page_errors.json`, `package.json`, screenshots `0*.png`.
- `artifacts/<app>/package.json.diff` — 0.9.8 `.web/package.json` vs 0.9.9a1 (in-place).
- `artifacts/<app>/reflex.lock/` — the app-root lockfile dir as saved by the 0.9.9a1 migration.

## Known-benign environment noise (do not re-report)

- `registry.npmmirror.com` "Failed to connect" x3 during init (proxy blocks mirror; fallback OK).
- SitemapPlugin "enabled by default, but not explicitly added" warning: present on BOTH 0.9.8 and
  0.9.9a1 logs (apps don't list it in plugins) — not new in the alpha.
- 0.9.8 logs a "Your version (0.9.8) of reflex is out of date. Upgrade to 0.9.8.post1" warning.
