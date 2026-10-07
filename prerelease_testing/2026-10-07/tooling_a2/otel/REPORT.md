CLUSTER: tooling_a2/otel
SUMMARY: Published reflex-otel 0.2.0a1 with Reflex 0.10.0a2 passed the real local-collector browser matrix on macOS/Python 3.11.16. The final dev/prod Chromium/WebKit runs passed 116/116 checks, including fresh linked browser/backend exports on the existing page after actual collector refusal, before reload. No user events were lost; telemetry batches during the outage may be dropped and are not claimed durable.
ARTIFACTS: prerelease_testing/2026-10-07/tooling_a2/otel/
TESTS:
- [pass] Final four browser executions: 29/29 each, 70 real JSON/protobuf exports and 392 spans. Original supplementary runs add 104 passing assertions; total 220/220 across eight executions.
- [pass] PRODUCER→CONSUMER trace IDs/parentage, INTERNAL chained audit, background flag, successful status, intentional handler ERROR status plus exception event, compile child links and one span per handler before outage.
- [pass] React render timing in dev/prod, browser-supported web vitals, socket spans and HTTP/websocket ASGI spans.
- [pass] All seven foreground/audit events and six background increments survive collector refusal; fresh export resumes on the same page before reload in both engines/modes.
- [pass] Full exported requests omit synthetic input/state markers and captured raw session tokens; event session IDs match SHA-256 prefixes and ASGI token query attributes are REDACTED.
- [pass] Python >=3.11 metadata verified; actual plugin/app executes on 3.11.16; complete Python and frontend dependency graphs retained.
- [anomaly] Expected collector-refusal console/network/exporter diagnostics and WebKit development preload warnings retained. No claim of error-free logs.
- [anomaly] Initial startup fixture used the wrong exception-handler argument name; corrected fixture, original error/clean termination evidence retained. No framework changes.
- [pass] All 18 owned groups, ports 3586/8586/8588 and Playwright processes empty at 09:17:34 UTC. Source/driver/scripts, full gzip logs/frames/exports, screenshots and exact replay commands retained.
REVERIFIED:
- None assigned; new plugin end-to-end coverage.
ISSUES:
- No new functional release issue found.
NOT_COVERED: Hosted observability authentication/storage/querying, metrics, gRPC, other sampling settings, auto-instrumentation CLI mode, full stable/a1 plugin browser matrix, other OSes and native Safari. No timing or telemetry-durability claim.
