# Browser reload and compilation-cache experiments

Status: complete. Owns only `browser_cache_bundle/reload_cache/`; reserved ports
3710–3719 and 8710–8719. All Python packages are published PyPI installations in
the campaign's read-only environments. No checkout package was imported or
installed, and no framework file was edited. Host: macOS 26.6.2 (25G83), arm64.
Browsers: Chromium 153.0.8010.12 and Playwright WebKit 26.6.

## Hypotheses and method

The alpha2 memo-body analysis cache stores rendered output and collected artifacts
for automatic passthrough memo components. Its reuse check includes root styles,
and the registration context clears these caches between compilations. The
package synchronization change compares parsed `package.json` objects, avoiding
unnecessary installs caused solely by formatting/key ordering.

The app is a small two-route metrics dashboard with two instances of an imported
`@rx.memo` component. It uses backend state, memo parameter defaults, an explicit
parameter override, an imported event increment rule, app-level button styling,
and an optional Moment frontend dependency. It models an ordinary developer
editing an imported settings module while the app remains open.

For each run the same application directory and `.web` are retained throughout:

1. Cold development compile and Chromium/WebKit interaction baseline.
2. Imported-module HMR changes memo text/default caption, background color,
   app-level button radius, state default, and increment rule (1→3).
3. Add a Moment component inside the memo body, requiring frontend packages.
4. Remove it, verify UI and package manifests lose the dependency, and change
   the increment rule to 5.
5. Rewrite root and `.web/package.json` with sorted keys/pretty formatting but
   identical parsed content, then trigger another imported-module HMR change.
   The npm cases use the stricter `.web`-only variant (`--format-target web`).
6. Stop and restart dev without deleting generated assets; reload the old tabs.
7. Build production in that same directory, reload the old tabs, stop, change
   source again (body, style, event step, Moment dependency), rebuild production,
   and reload those same browser tabs once more.

Each browser has its own persistent context. Every phase verifies the updated
memo output and CSS, increments state with the new rule, verifies both cards see
the same new total, edits a customer name, and navigates to the second route and
back. Fresh contexts independently verify changed state defaults; the experiment
does not assume a class-default edit should overwrite an existing session.

The npm variant adds two automatically memoized components with identical rendered
JSX and distinct `on_mount` handlers. Their labels change at each source revision.
Both existing and fresh contexts must receive both correct handler labels. This
targets collected hook artifacts that cannot be identified from rendered JSX alone.

## Reproduce

The campaign bootstrap creates the alpha2, alpha, stable, and driver environments.
The driver environment needs Playwright's Chromium and WebKit installed. Existing
campaign package and browser versions are recorded in each run's `results.json.gz`.

```sh
export SB=/private/tmp/reflex-prerelease-macos-pass2
export UV_CACHE_DIR="$SB/uv-cache"
export ART=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/browser_cache_bundle/reload_cache
cd "$SB"
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env alpha2 --out "$ART/results" --port 3710 --backend 8710 --production
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env alpha --out "$ART/results" --port 3710 --backend 8710 --production
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env stable --out "$ART/results" --port 3710 --backend 8710 --production
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env alpha2 --out "$ART/results" --port 3710 --backend 8710 --manager npm --hooks --format-target web --production
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env stable --out "$ART/results" --port 3710 --backend 8710 --manager npm --hooks --format-target web
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env alpha --out "$ART/results" --port 3710 --backend 8710 --manager npm --hooks --format-target web
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/compact.py"
```

Run these sequentially. The harness refuses existing app directories: use a new
`--attempt` value when repeating a case. `--manager npm` runs the same workflow
with npm. Production uses frontend port 3710 for both services; dev uses 3710/8710.
The harness records exact commands and process groups, stops each group before
the next start, verifies cleanup, and gzips server logs after each case. `compact.py`
losslessly compresses complete results and writes `summary.json` for quick review.
It retains representative screenshots from both browsers and all failure images.
Read full diagnostics with `gzip -cd results/<case>/results.json.gz | jq ...`.

## Results

No 0.10-specific stale output, style, state default, event handler, provider, route,
or package dependency regression was observed. All three versions update imported
memo text/default props, root style, backend rules, fresh-session defaults, and
added/removed Moment dependencies in both browsers. The distinct mount-hook cases
also pass. Existing browser tabs load the correct rebuilt production assets.

| Case | Dev/HMR/warm checks | Production/rebuild checks |
| --- | --- | --- |
| alpha2 Bun | 11 pass, 1 driver protocol failure | 4 pass |
| alpha1 Bun | 12 pass | 4 pass |
| stable Bun | 12 pass | 4 pass |
| alpha2 npm + hooks | 12 pass | 4 pass |
| alpha1 npm + hooks | 12 pass | Not repeated |
| stable npm + hooks | 12 pass | Not repeated |

Install counts below are **additional** occurrences of the frontend install log
message during each edit, excluding the cold install. Package manifests and full
install commands are retained; this is a count of install work, not a timing claim.

| Manager / release | Source-only edit | Dependency add | Dependency remove | Formatting-only edit |
| --- | ---: | ---: | ---: | ---: |
| Bun / alpha2 | 0 | 1 | 1 | 0 |
| Bun / alpha1 | 0 | 1 | 1 | 0 |
| Bun / stable | 1 | 1 | 1 | 1 |
| npm / alpha2 | 1 | 1 | 1 | 1 |
| npm / alpha1 | 1 | 1 | 1 | 1 |
| npm / stable | 1 | 1 | 1 | 1 |

The package synchronization improvement is confirmed for Bun. The following
minimal experiment explains why npm still reinstalls on source-only edits.

## Pre-existing npm cache miss and causal control

`npm_minimal.py` uses `minimal_app/`: a heading, counter, and button, with no
custom memo function, mount handler, or added component dependency. Its only source
edit changes an imported string from `revision-A` to `revision-B`. On all three
versions this causes another npm install despite identical root/web lockfile
semantic hashes before and after the edit. Both browsers keep correct state.

After npm has run, `.web/package.json` omits `devDependencies`. The next framework
render supplies `devDependencies: {}`. The recorded semantic comparison differs
only at that field. As a causal control, the driver adds exactly that empty object
to `.web/package.json` before another text edit (`revision-C`). Alpha2 and alpha1
then skip the install (cumulative counts 1→2→2); stable's byte comparison still
reinstalls (1→2→3). All 18 minimal browser checks pass. This is an existing npm
cache-efficiency gap, not a release regression or browser correctness failure.

The published source involved is `reflex/utils/frontend_skeleton.py`,
`sync_root_package_json_to_web` / `_compile_package_json`, called by the frontend
install cache invalidation path in `reflex/utils/js_runtimes.py`. No fix was applied.

```sh
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/npm_minimal.py" --sb "$SB" --env alpha2
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/npm_minimal.py" --sb "$SB" --env stable
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/npm_minimal.py" --sb "$SB" --env alpha
```

These runs write `minimal_results/<env>-minimal-1/results.json`, gzip server logs,
and a WebKit screenshot. The script records parsed manifests, full manifest-render
differences, byte/semantic lock hashes, event counts, console/network/ws diagnostics,
and process cleanup. Use `--attempt 2` to repeat without overwriting its scratch app.

## Diagnostic anomalies and limits

Alpha2's first Chromium warm-restart `page.reload()` encountered Playwright's
DevTools protocol error `Not attached to an active page` while Vite was reconnecting.
The same page later reloaded both production builds and passed all functionality.
The original failure is preserved in `alpha2-bun-1/results.json.gz`. Subsequent
driver revisions retain that exact protocol error and retry once by navigating
the same tab; they do not retry application assertion failures. Alpha1's complete
workflow passes without this transient. This is currently a driver/reconnect
anomaly, not evidence of a framework regression.

All three releases and both package managers also produce transient React
`Invalid hook call` / null `useContext` errors while adding Moment through HMR.
These are captured in the `dependency-add` console records; React's error boundary
catches them, so `pageerrors` is empty. The server log records dependency optimizer
reloads at the same point. The page recovers automatically and all subsequent
assertions pass without a manual reload. This is pre-existing behavior and does
not occur as a persistent production failure in the tested rebuilds.

Console, page errors, failed requests, HTTP errors, and bounded websocket frames
are retained per browser and phase. Planned server downtime can produce Vite or
websocket reconnect errors; classify these against the controlled stop/start
timeline instead of treating every connection refusal as app breakage. No
performance claim is made from compile/startup timing under concurrent load.
WebKit also logs unused-preload warnings after HMR. Four canceled resource requests
occur in the first alpha2 Bun warm restart; all other cases have no failed requests.
No case records an HTTP error or uncaught page error. Each server's process group
and reserved port listeners are empty after cleanup.
