# Published alpha upload/event-stream campaign

All seven real-network scenarios passed in **dev and prod** against published `reflex==0.10.0a1`, `reflex-base==0.10.0a1` and `reflex-components-core==0.10.0a1`. No framework fix or checkout installation was made. The tests target [PR #7357](https://github.com/reflex-dev/reflex/pull/7357) and [PR #7358](https://github.com/reflex-dev/reflex/pull/7358); their descriptions are retained in the parent `evidence/` directory.

## Plan

Use a real Reflex upload UI and independent browser tokens, with buffered multipart uploads chained to delayed completion tasks. Exercise concurrent responses, unrelated websocket events, consumer disconnection, navigation supersession and intentional upload failure. Add real HTTP enqueue/stream routes and an in-memory OpenTelemetry exporter to verify event lineage under actual request spans. Preserve browser, transport, event-phase, ASGI response and trace evidence.

## Results

| Case | Dev | Prod | What was asserted |
| --- | --- | --- | --- |
| Concurrent buffered uploads | Pass | Pass | Both real multipart responses finish HTTP 200 with their own filename/byte count and delayed chained completion. Top-level txids are independent and children name their actual parent. |
| Another client's slow ordinary event during an upload | Pass | Pass | The upload completes while the other event remains unfinished; that event then completes normally. The upload tail ends 0.757s earlier in dev and 0.763s earlier in prod. |
| Uploading browser disconnect | Pass | Pass | Closing its independent context cancels its own upload tail. Another client's in-flight delayed event completes and a subsequent ordinary event works. |
| Navigation while an upload response stays open | Pass | Pass | `/slow` starts a background on-load chain; navigating to `/new` cancels it and completes the new on-load before the upload's delayed tail finishes. The upload still completes. |
| Failed upload chains delayed recovery | Pass | Pass | The intentional `RuntimeError` ends the HTTP response callable. A recovery event updates the UI through an actual websocket delta **0.351s after** the response exits. The next ordinary event still works. |
| Slow custom HTTP stream consumer disconnect | Pass | Pass | A real HTTPX consumer receives the first NDJSON delta then closes the response. Only that stream's handler is cancelled; another browser's delayed and subsequent ordinary events complete. |
| Actual request/event OpenTelemetry lineage | Pass | Pass | A 328,000-byte streamed-chunk upload and a custom HTTP enqueue create `INTERNAL` event spans beneath `SERVER` request spans, with no `reflex.event.parent_txid` on top-level events. The chained API child names the actual parent's txid and span ID. All six buffered top-level event spans also omit the root-context parent attribute. |

Each mode recorded **25 visible assertions** plus direct request status, ordering, timing, cancellation, independent-token, event-context and span-parent assertions. Browser: headless local Chrome **154.0.8037.98**, controlled by Playwright **1.63.0**, with fresh contexts owned by this test. Neither run had an uncaught page error or an observed failed browser request. Dev had no console errors. Prod logged the automatic `/favicon.ico` 404 because the minimal app has no favicon; its exact console location is retained.

The intentionally failing upload produces `RuntimeError: expected upload recovery probe` in the saved server log. This is the fixture used to prove late recovery delivery. It is not an unexpected framework failure.

## Evidence and reproducibility

- `evidence/summary.json`: compact validated results and timings.
- `evidence/{dev,prod}/browser-results.json`: assertions, console output, upload request lifecycle and real websocket frames.
- `evidence/{dev,prod}/backend-evidence-final.json`: backend event phases/txids, ASGI response-exit timestamps and completed trace spans.
- `evidence/{dev,prod}/*.png`: concurrent upload, navigation and recovered UI screenshots.
- `evidence/{dev,prod}-server.log`: final clean-start compile/server logs including the expected failure probe.
- `evidence/provenance.json`, `evidence/freeze.txt`: isolated import origins and the 52-distribution graph after adding published OpenTelemetry dependencies.

The interpreter remains `/private/tmp/reflex-alpha-core-state/venv/bin/python`. The original core/state graph is retained separately in the parent `evidence/` directory. The added published instrumentation dependencies are `opentelemetry-sdk==1.45.0`, `opentelemetry-api==1.45.0`, ASGI instrumentation/semantic conventions/util-http/instrumentation `0.66b0`, and `asgiref==3.12.1`. No remote collector is used; spans stay in memory and are saved through the test app's local evidence endpoint.

Install only published distributions into a temporary venv, using `requirements.txt` with `uv pip install --python <exact temporary interpreter> --index-url https://pypi.org/simple -r <copied requirements>`. Run from a neutral temporary directory with `PYTHONPATH` unset, never from the checkout or through repository tests. Initialize `upload_probe` with the installed CLI, copy `upload_probe.py` to `upload_probe/upload_probe.py`, and copy `rxconfig.py` and `browser_checks.py`.

Every execution uses this form:

```sh
env -u PYTHONPATH REFLEX_DIR=/private/tmp/reflex-alpha-core-state/runtime UV_CACHE_DIR=/private/tmp/reflex-alpha-core-state/uv-cache /Users/masenf/.local/bin/uv run --no-project --python /private/tmp/reflex-alpha-core-state/venv/bin/python <command>
```

Dev commands: `reflex run --frontend-port 3111 --backend-port 8111`, then `browser_checks.py <evidence directory> http://localhost:3111 http://localhost:8111`.

Prod commands: in a separate initialized temporary app, change both copied config ports and `api_url` to 3112. Run `reflex run --env prod --frontend-port 3112 --backend-port 3112`, then `browser_checks.py <evidence directory> http://localhost:3112 http://localhost:3112`.

Copy `summarize.py` to a neutral directory and execute it with the directory containing `dev/` and `prod/` evidence. It validates all seven cases in each mode before creating `summary.json`. The test app's evidence endpoints and token-accepting test API are purpose-built local fixtures, not production application patterns.

## Adversarial review and limits

1. This covers two concurrent buffered streams, deliberate response delays/disconnects, navigation, a failed upload and a real streamed-chunk body. It does not quantify throughput or claim high-concurrency/load, browser-matrix, or bandwidth-throttled multi-gigabyte coverage.
2. The production favicon warning and intentional upload error are explained above. No product regression was identified in the covered cases.
3. PR #7357 explicitly leaves behavior involving several sibling chained events after the consumer leaves outside its scope; this campaign verifies one awaited upload-tail chain, not that additional sibling scenario.
4. The response-exit proof uses an ASGI wrapper around the actual published backend. Playwright may report the failed response's terminal network callback later, so it is not used as the ordering oracle for the late recovery delta.

Ruff check and format pass for all owned standalone reproduction sources. Framework unit tests and pyright over checkout packages were not run because this campaign requires exclusively published-package imports.
