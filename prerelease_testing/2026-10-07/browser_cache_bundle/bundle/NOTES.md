# Production bundle, payload, and browser-cache comparison

Completed 2026-10-07 on local macOS 26.6.2 arm64. Published packages only; no framework changes. No material bundle/cache regression or functional release blocker found. Stable→alpha2 adds about 9.3 KB to the cold landing HTTP transfer in this app, while the initial websocket application payload shrinks by about 7.4 KB. Alpha1→alpha2 is effectively unchanged in HTTP payload. These are separate measurements, not a combined wire-byte estimate.

## App and coverage

The same modular app has four ordinary routes: lightweight home; small stateful task dashboard; optional Plotly revenue report; catalog data editor with SQL syntax highlighting. Heavy pages live in separate Python modules. All three published package graphs were tested in production with the public `frontend_lazy_bundled_libraries` config false and true. Environments `forms-alpha2`, `forms-alpha`, and `forms-stable` are read-only exact PyPI graphs with Plotly added; full freezes are in `logs/`. App imports assert their expected environment path.

Each Chromium/WebKit journey checks cold home, warm reload, client navigation to dashboard, task event, first chart navigation, chart update, first editor/code navigation, catalog edit using Command+A, return home, and return chart with preserved state. There are six original configurations, twelve browser journeys, plus four browser recheck journeys. The originals include two WebKit focus-driver timeouts (7 passes/1 timeout each); both full rechecks pass all 10 checks. Across actual executions: 154 passing assertions and 2 original driver timeouts; all 120 distinct configuration/browser functional checks have passing coverage after rechecks.

Chromium153.0.8010.12 and Playwright WebKit26.6, Playwright1.63.0, Python3.12.14, Node26.8.1, Bun1.4.0. WebKit is the Playwright engine, not a Safari application run. Screenshots are selected essentials; all captures remain in the neutral scratch directory.

## Measurements and interpretation

Built raw/gzip estimates below sum **every generated JS chunk**, including unused syntax grammars and heavy routes. They are not landing-page payloads. The gzip estimate is deterministic Python gzip, not a substitute for recorded transfer sizes. CSS is709,730 raw bytes /85,164 estimated gzip bytes in all six builds.

| Train | Lazy libraries | All JS raw bytes | All JS gzip estimate | Cold home RT transfer | Cold home Chromium CDP bytes |
|---|---:|---:|---:|---:|---:|
| stable0.9.12 | false |6,444,630|2,023,817|321,627|323,127|
| alpha0.10.0a1 | false |6,475,647|2,033,111|330,907|332,407|
| alpha2 0.10.0a2 | false |6,475,648|2,033,109|330,909|332,409|
| stable0.9.12 | true |6,515,416|2,030,113|327,039|328,223|
| alpha0.10.0a1 | true |6,546,428|2,039,416|336,328|337,512|
| alpha2 0.10.0a2 | true |6,546,430|2,039,422|336,331|337,515|

Both engines report the same cold Resource Timing totals. RT transferSize includes the browser's standardized header allowance; CDP loadingFinished.encodedDataLength is Chromium's measured encoded network length. Cold encoded **body** bytes for default mode: stable316,827, alpha326,107, alpha2326,109. Do not treat Playwright request sizes or warm encodedBodySize as wire usage: cached responses can retain their logical body sizes. All original API readings are preserved in the evidence.

Default cold HTTP increase stable→alpha2 is9,282 bytes (RT+2.89%, CDP+2.87%). Whole-build JS raw increase is31,018 bytes (+0.48%). This is accompanied by legitimate frontend dependency upgrades: React/ReactDOM19.2.8→19.3.0, react-error-boundary6.1.2→6.1.6, socket.io-client4.8.3→4.8.4. The entry-client chunk accounts for most of the raw/gzip difference, but this experiment does not isolate individual dependencies' causal contributions.

The lazy setting increases this app's cold RT payload by about5.4 KB (+1.6–1.7%), while reducing the number of initial resources from16 to13. It targets optional registered dynamic-component namespaces, so it is not a general heavy-route optimization. Both modes preserve existing heavy-route splitting: the first reports route transfers about1,374,140–1,374,164 RT bytes; first editor route about129,035–129,068. Small recheck differences (2–3 bytes or one300-byte RT header allowance) are preserved, not presented as stable performance effects. No elapsed-time speed claims are made under concurrent host load.

## Cache and network evidence

Responses actually use `Content-Encoding:gzip` with Content-Length matching the precompressed representation. Static/HTML responses expose ETag and Last-Modified; Cache-Control is absent on this bundled local production server. Warm reload reuses bodies with conditional304 responses or cache hits. Chromium RT reload totals range300–4,800 bytes; WebKit about3,587–3,636. CDP records164-byte document revalidation and, when assets revalidate,164/256-byte responses. The different mixes are heuristic freshness/revalidation observations, not a train regression.

Client return-home and warm revisit-report phases transfer0 resource bytes in both engines on every completed journey. Counter and chart edits survive navigation. Heavy Plotly/editor libraries are not included in the cold home requests. No browser console warnings/errors, pageerrors, failed requests, HTTP>=400 responses, or instrumentation errors occurred in the measured journeys.

Websocket figures are UTF-8 **application payload** bytes, not websocket framing/per-message-compression wire bytes:

| Default train | Initial received, Chromium | Initial received, WebKit | Task reply | Chart update reply | Catalog edit reply |
|---|---:|---:|---:|---:|---:|
| stable |9,446|9,527|121|6,824|223|
| alpha |1,981|2,062|121|6,824|223|
| alpha2 |2,011|2,092|121|6,824|223|

Stable's initial delta includes all catalog/dashboard/report defaults and the full Plotly figure. Alpha sends router metadata without unchanged defaults; alpha2 additionally sends hydration state. All subsequent visible actions work. Both lazy settings produce the same event payload sizes. Chart update size includes Plotly's figure template; it is not a new regression.

## Anomalies investigated

Two original WebKit runs (alpha2 lazy=true, alpha lazy=false) did not open the editor when Enter followed the canvas click immediately. Screenshots show a selected cell and no browser/server exception. The corrected driver waits250ms for focus, matching the previous dataeditor test's natural input spacing. Full rechecks on both affected versions/configurations pass10/10 per engine. Original failures are retained; this evidence supports a driver-focus race, not a release defect claim.

Server logs contain the expected App(theme=...) deprecation (the supported compatibility path is intentionally identical across versions), successful bun peer-version warnings, and bundle-size notices. Stable additionally logs one tuple-position argument-transformation warning for CatalogState.edit; its published event processor explicitly falls back to the original payload, and catalog editing succeeds. The warning is absent in both alphas. No unexplained runtime server error remains.

## Exact clean reproduction

Choose a new neutral scratch root. Bootstrap refuses existing envs, installs only exact PyPI freezes, downloads the two Playwright engines, and copies the source/scripts. No uv/Python command runs from the repository.

```sh
export REFLEX_TEST_SB=/private/tmp/reflex-browser-bundle-repro
ART=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/browser_cache_bundle/bundle
bash "$ART/scripts/bootstrap_from_freezes.sh"
cd "$REFLEX_TEST_SB/apps/browser-bundle"
export UV_CACHE_DIR="$REFLEX_TEST_SB/uv-cache"
```

First server, in a separate terminal using the same variables:

```sh
./scripts/start.sh alpha2 0 8700 > logs/alpha2-lazy0-server.log 2>&1
```

After its ready/listening message:

```sh
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" \
python scripts/browser_matrix.py http://localhost:8700 alpha2-lazy0 runs/alpha2-lazy0 \
> logs/alpha2-lazy0-browser.log 2>&1
uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" \
python scripts/measure_assets.py alpha2-lazy0 runs/alpha2-lazy0/assets.json
```

Stop the first server and verify its descendants/listener closed. The remaining five modes run sequentially, managing only their own process groups:

```sh
uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" \
python scripts/run_remaining.py > logs/matrix.log 2>&1
```

This uses alpha2-lazy1:8701, alpha-lazy0:8702, alpha-lazy1:8703, stable-lazy0:8704, stable-lazy1:8705. Optional exact repetitions of the investigated focus cases:

```sh
uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" \
python scripts/run_focus_rechecks.py > logs/focus-rechecks.log 2>&1
uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" \
python scripts/summarize.py . > logs/comparison.txt
```

Rechecks use8706/8707. The current driver includes the focus delay. The final browser script records failures/exceptions, completes both engines, then exits1 if any check failed. Both orchestration scripts record child exit failures, continue their remaining intended cases, and exit1 at the end if any case failed. Historical measured runs used the earlier record-only exit behavior; no measured result was changed. An unreachable reserved-port negative control (localhost:8709, no server) produced two driver-exception checks and exit1; see logs/harness-negative*. No full matrix was repeated for this exit-only change. `comparison.json` and `logs/comparison.txt` aggregate the complete dataset.

Actual run scratch: `/private/tmp/reflex-prerelease-macos-pass2/apps/browser-bundle`. Raw source and scripts are under `source/` and `scripts/`; built assets are inventoried with SHA256, raw bytes, gzip estimates and exact installed frontend versions in each `assets.json`. Full browser events/websocket frames are in `*-full.json.gz`; readable summaries retain headers, Resource Timing, CDP request/cache details and assertions. Full server logs are gzip-compressed, no entries removed.

## Cleanup and limits

All owned browsers and server process groups closed. Final `logs/cleanup-listeners.txt` and `cleanup-processes.txt` are empty for3700–3709/8700–8709 and owned app processes. No git/board or framework mutation was performed.

This tests the bundled local production server, not a CDN/reverse proxy or hosting provider. It does not claim timing/CPU improvements, all optional-library APIs, Safari application behavior, stale open tabs across deployment, or cache invalidation after source changes; those are separate workstreams. Cold heavy direct-entry and multi-user state isolation are not covered by this artifact. No finding inbox entry is warranted from these results.
