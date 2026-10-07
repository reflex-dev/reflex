ITEM: statemgr_perf
KIND: new
REF: -
TITLE: Background completion after session expiry leaves untouched browser state stale
SEVERITY: low
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: unknown
REPRO: Create the exact PyPI environments using statemgr_perf/NOTES.md. Set SB to that neutral scratch directory and ART to this checkout's prerelease_testing/2026-10-07/statemgr_perf/verify_expiry. From "$SB", run EXPIRY_VERIFY_AUTHORIZED=1 uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env alpha2 --manager memory. Repeat --env stable and --manager disk. The driver seeds an export workspace, releases the lock during eight seconds of simulated external I/O with TTL five seconds, and captures completion before any foreground inspection. Browser displays root100/child11/components13/17; public get_state inspection reports root100/child0/components0/0 and refreshes the stale view. Ordinary idle foreground recovery already shows the correct full reset. Use a fresh --attempt for repeated runs.
EVIDENCE: prerelease_testing/2026-10-07/statemgr_perf/verify_expiry/NOTES.md, report.json and results/*/{chromium,webkit}-background-before-inspection.png, complete compressed browser frames and public receipts; original independent lead in expiry/SUMMARY.json.background_visible_anomalies. Eight of eight verifier background cases reproduce, eight of eight ordinary controls pass, on both versions/managers/engines. Root separately inspected the alpha2 WebKit screenshot.
ROOT_CAUSE_GUESS: Wire evidence shows the background completion sends only the changed root state after reacquiring an expired tree; it omits the untouched child/component reset values still displayed by the client. The following foreground inspection triggers full hydration. This is an inference from actual frames/DOM/public server state, not a source patch.

Severity is deliberately low: configured session expiration is expected, the default timeout is much longer, the external I/O is simulated, and no downstream data corruption or cross-user leakage is demonstrated. This confirms a scoped pre-existing consistency weakness, not a new release blocker. Independent verifier used a separately authored app and driver, without reading or copying the originating browser driver. Production and Redis were not part of that independent matrix.
