# Data editor: macOS second-pass browser evidence

Completed 2026-10-07. No framework source changes. All Python imports came from isolated PyPI environments, guarded by `REFLEX_EXPECT_ENV`; no checkout installation/import was used. macOS 26.6.2 arm64, Python 3.12.14, Playwright 1.63.0 with bundled Chromium 153.0.8010.12. See `de/logs/platform.txt` and full package freezes.

## Outcome

No new 0.10-only regression found in this matrix. Four previously unfinished leads are reproducible defects/anomalies **also present on 0.9.12**:

1. **Medium:** data editors directly inside `rx.foreach` crash the page with `ReferenceError: g_rx_state_ is not defined` and render 0 canvases. The generated `getData_*` callback references the foreach variable outside its lexical scope. Independent minimal verification in `verification/` also confirms the ordinary state-bound editor and memo-wrapped foreach controls render on both versions.
2. **Medium:** selecting a text cell and typing to begin the first edit loses initial characters. Typing `Zed` immediately yielded `d` in all five focused matrices. Separate typing probes produced `low` from `Slow` at 40ms and 120ms per character on stable dev and alpha2 prod; zero-delay produced `low`/`ow`. Pressing `S`, waiting 800ms, then typing `low` preserved `Slow`. Explicitly opening the editor with Enter before typing also works. This supports an overlay timing issue, but does not establish its exact upstream cause.
3. **Medium:** binding `on_delete` sends the correct selection to Python, then Delete throws `TypeError: Cannot read properties of undefined (reading 'length')` in Glide `shiftSelection`; no `on_cell_edited` fires and the selected cell remains unchanged. Independent bound/unbound Delete/Backspace controls in `verification/` confirm this on alpha2 and stable. Generated callbacks return `addEvents(...)`; Glide expects a boolean or GridSelection synchronously. See `de/logs/generated-snippets.txt`.
4. **Low:** the single-image preview remains open after Escape immediately following activation. A multi-image preview closes with Escape after clicking its next arrow; text overlays close correctly. The separate no-outside-click assertion prevents the old driver from hiding this behavior. Seen in all five matrices. Focus routing is a hypothesis; exact cause is unproven.

| Run | Packages (framework / dataeditor) | Checks | Pass | Failed assertions |
|---|---|---:|---:|---:|
| alpha2-dev |0.10.0a2 /0.10.0a1|36|31|5|
| alpha-dev |0.10.0a1 /0.9.3.post1|36|31|5|
| stable-dev |0.9.12 /0.9.3.post1|36|31|5|
| alpha2-prod |0.10.0a2 /0.10.0a1|36|31|5|
| stable-prod, failure-focused |0.9.12 /0.9.3.post1|16|11|5|
| stable-typing |0.9.12 /0.9.3.post1|5|2|3|
| alpha2-prod-typing |0.10.0a2 /0.10.0a1|5|2|3|

The five focused failed assertions represent four behaviors because delete has both an error and an unchanged-cell assertion. Total 170 assertions, 139 pass/31 fail. Alpha's older dataeditor pin is intentional: that package's0.10.0a1 was newly included in the alpha2 train. Complete graphs are frozen; do not re-resolve only the top-level version.

Passing full-matrix checks cover explicit Enter-opened text/int/float edits using macOS Command+A; boolean single/second click toggles; text-overlay Escape; image-carousel CSS and next-arrow selection; Escape after clicking the carousel arrow; independent ComponentState edits; memo rows/title updates; dropdown rendering; static/dynamic theme; client-side filter with backend append; and 5,000-row scrolling and final-row click. Theme samples are RGB255,255,255 →22,22,27 →255,255,255. No scroll long task exceeded 250ms; alpha-dev had one 51ms task, the other full runs none. This is one local measurement, not a general performance guarantee.

## Fixtures and instrumentation

`de/source/` is the old 10-06 `p_dataeditor.py` fixture with only dataeditor pages loaded, the expected-venv import guard corrected, and its package `__init__.py` retained. `de/scripts/driver.py` adapts the old driver to bundled Chromium, full error stacks, and `ControlOrMeta+a`. `focused_driver.py` recalculates grid bounds after every edit (event text changes layout), asserts Escape before any outside click, and captures websocket frames. `typing_driver.py` uses a fresh context per typing-speed probe. No framework/component code was patched.

Every run captured/inspected server logs, console errors and warnings, request failures/HTTP>=400, websocket traffic, and screenshots. Selected key screenshots are retained; all full capture directories remain in the scratch directory. Results files retain all checks, errors, warnings, and counts. Repeated console entries are represented once with `repeat_count`; their full ordered originals are in `full-console.json.gz`. Websocket frames are in `websocket-frames.json.gz`. Both are ordinary gzip JSON, produced by `archive_frames.py` without dropping captured entries.

The old fixture intentionally exercises unsupported `uri`, `markdown`, `bubble`, `drilldown`, and `row-id` type strings. The published helper's default branch logs `Warning: column.type is undefined for column.title=...` repeatedly and renders the type name; these are fixture-generated warnings, not new failures. The old cross-origin test URL atlocalhost:8438 has no server and causes expected connection-refused requests. The intentional `/does-not-exist.png` is404 in prod (dev fallback differs). Other inspected noise: experimental `rx._x`, implicit Radix theme deprecation, bundle-size advice, and successful bun peer-version warnings. No unexplained backend exception remains beyond the frontend errors already recorded.

## Clean reproduction

From a new neutral scratch directory, install the exact published graphs and copy the app/scripts. The bootstrap refuses existing env directories. It requires uv and downloads only from PyPI; Playwright downloads its Chromium browser.

```sh
export REFLEX_TEST_SB=/private/tmp/reflex-dataeditor-repro
ART=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/dataeditor/de
bash "$ART/scripts/bootstrap_from_freezes.sh"
cd "$REFLEX_TEST_SB/apps/dataeditor"
```

Start exactly one server at a time in a separate terminal. Use the same exported `REFLEX_TEST_SB` in both terminals:

```sh
./scripts/start_server.sh alpha2 dev 3420 8420 > logs/alpha2-dev.log 2>&1
# Other matrix choices, each only after stopping its predecessor:
./scripts/start_server.sh stable dev 3421 8421 > logs/stable-dev.log 2>&1
./scripts/start_server.sh alpha dev 3422 8422 > logs/alpha-dev.log 2>&1
./scripts/start_server.sh alpha2 prod 8423 8423 > logs/alpha2-prod.log 2>&1
./scripts/start_server.sh stable prod 8424 8424 > logs/stable-prod.log 2>&1
```

Wait for the log's listening/ready line; run the driver from the neutral work directory. For stable/alpha/prod change base URL, output directory, and label using the table above. Prod uses a single backend/frontend port and the launcher sets its API URL accordingly.

```sh
export UV_CACHE_DIR="$REFLEX_TEST_SB/uv-cache"
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" \
  python scripts/focused_driver.py http://localhost:3420 runs/alpha2-dev \
  --label alpha2-dev --groups de_foreach,de_edit,de_overlay,de_multi,de_theme,de_filter,de_big
```

Stable production used only `--groups de_foreach,de_edit,de_overlay`. Expected exit1 records failed assertions and still writes results. Typing follow-up commands, while their respective server is running:

```sh
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" \
  python scripts/typing_driver.py http://localhost:3421 runs/stable-typing stable-typing
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" \
  python scripts/typing_driver.py http://localhost:8423 runs/alpha2-prod-typing alpha2-prod-typing
```

Actual scratch root for this run: `/private/tmp/reflex-prerelease-macos-pass2`, with the original dev app directories named `alpha2`, `stable`, and `alpha` (identical copied sources). The production directories used the launcher's `alpha2-prod` and `stable-prod` names.

## Cleanup and limits

All owned browsers closed. Every server received SIGINT after its run. Final listener audit found stable dev's frontend/supervisor survived SIGINT after Granian had exited; they were terminated with SIGTERM and final `lsof`/process audits were empty. Before/after evidence is in `de/logs/cleanup-*.txt`, server shutdown log in `stable-dev.log`. This is one incidental stable observation, not a repeatable new-train regression claim. No owned server remains on 3420–3427 or 8420–8427.

Not covered here: alpha1 production, cross-browser coverage (parent scope), remote/cross-origin carousel loading, clipboard paste, drag-resize/sort, writable dropdown selection, and rechecking all unsupported cell kinds. Forms/recharts/misc smoke belong to the parent's parallel scope. Independent minimal verification is separate under `verification/`; these drafts do not edit the shared board or findings.
