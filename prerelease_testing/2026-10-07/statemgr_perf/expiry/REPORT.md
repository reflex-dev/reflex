CLUSTER: statemgr_perf/expiry
SUMMARY: Published alpha2 and stable completed memory/disk idle expiry, long-job/held-lock recovery, disk worker reload, duration probes and 300-context churn on macOS. Alpha2 removes expired disk-session locks; stable retains them (301 after warm-up plus 300 sessions). No new alpha2 regression established. A pre-existing released-background expiry path leaves untouched browser values stale until reload even though the job completes on fresh server state.
ARTIFACTS: prerelease_testing/2026-10-07/statemgr_perf/expiry/
TESTS:
- [pass] Ordinary idle expiry: fresh root/substate/ComponentState values after next click or reload, both managers/trains. Production disk confirmed in Chromium and WebKit.
- [pass] Alpha2 disk file/state/lock expiry under new 250ms and deprecated 0.25 debounce settings. Stable state/files expire but locks remain.
- [pass] Seven-second foreground event keeps its lock beyond five-second TTL; queued click produces expected counts in both versions/managers.
- [pass] Released seven-second background job reacquires fresh state, completes and reloads correctly in both versions/managers.
- [anomaly] Immediately after that background completion, server is root10/child0/components0/0 while DOM is root10/child3/components2/1. Four saved actual DOM/backend comparisons and full frames; ordinary post-idle foreground click correctly refreshes the whole tree. Pre-existing, not a claim that expired application data should persist.
- [pass] Normal development worker reload changes backend PID while preserving disk counters and subsequent events. Full CLI restart deliberately clears disk state on both trains; source/logs explain the distinct persistence boundary.
- [pass] All 1,200 test contexts across four production churn runs complete their event, each run has 300 unique tokens, and states return to zero. Memory locks return to zero on both trains; alpha2 disk locks return to zero.
- [fail] Stable-only disk retained-lock checks: one after idle, 301 after churn. The four recorded assertion failures are this baseline behavior.
- [anomaly] RSS decreases from each sampled peak but remains above warmed baseline. No live-state leak or timing claim inferred from allocator RSS alone; single series per version/manager, one-second sampling.
- [pass] Eleven duration parse/App-construction probes; four warning-once/source-location checks. abc/5x reject clearly. Signed -5s is accepted and means immediate disk writes in the published <=0 branch; no browser test of negative debounce.
- [anomaly] Two historical full-restart runs aborted at a Playwright navigation race; corrected reruns completed. Expected connection-refused logs occur during full CLI downtime. Stable logs lifespan observer cancellation traceback on shutdown; several native dev shutdowns log unexpected worker exit after completed checks. All retained and qualified.
- [pass] Every run records empty owned process group/listeners after cleanup; parent independently confirmed the full allocation quiet at 08:26 UTC before releasing the performance timing gate. No subsequent runtimes started.
REVERIFIED:
- No formal F-number assigned here. The release's expired disk-lock cleanup is supported by direct stable/alpha2 controls and 300-session observations.
ISSUES:
- TITLE: Background job completing after session expiry leaves untouched browser counts stale
  SEVERITY: low
  REGRESSION: no
  REPRO: Follow NOTES bootstrap; run run_case.py with --scenario jobs --expiration 5 using either version and manager. Populate counters, let background work release its context for seven seconds, compare after_job_visible with expired-background-reacquire-server. Reload repairs the discrepancy.
  EVIDENCE: runs/*-jobs-*/chromium-results.json.gz and chromium-frames.json.gz; SUMMARY.json.background_visible_anomalies. Treat as a scoped pre-existing consistency weakness; independent verifier assigned by parent.
NOT_COVERED: Redis and throughput/compile timing belong to other owners. No forced-GC/object-liveness proof, repeated RSS series, negative-debounce browser case, or two-edit automatic-error-reload timing. Browser engines are Playwright Chromium/WebKit, not the full Safari app. Exact initial aborted restart harness revision was superseded by bounded navigation retry, while its original raw evidence remains unmodified.
