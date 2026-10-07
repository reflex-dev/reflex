CLUSTER: macos_lifecycle
SUMMARY: Published 0.10.0a2 passed macOS arm64 browser startup, Unicode-path and Unicode-input handling, reload, HMR, npm/bun dev execution, and a bun production smoke. The earlier npm SIGTERM failure did not reproduce on macOS with either alpha: alpha2 exited 0 in 0.178–0.288 seconds and alpha1 in 0.182 seconds, while 0.9.12 retained its CLI/npm/node frontend after 30 seconds. This is a platform-scoped comparison and does not close the original Linux F-007. All owned servers and browsers were cleaned up.
ARTIFACTS: prerelease_testing/2026-10-07/macos_lifecycle/
TESTS:
- [pass] Six complete real-Chromium event/reload runs: alpha2 npm twice, alpha1 npm, stable npm, alpha2 bun dev and prod; no browser errors, warnings, failed requests, or HTTP error responses.
- [pass] Four HMR runs under paths with spaces, accented text, and Japanese characters: frontend heading updates, session count survives, modified backend handler increments 2 to 4.
- [pass] Alpha2 production from Unicode path: one-port local build, input event, increment, reload, and SIGTERM cleanup.
- [pass] Alpha2 npm ASCII/no-HMR repeat: single-PID SIGTERM exits 0 in 0.178 seconds, with no listeners or process-group members remaining.
- [fail] Stable npm shutdown baseline: CLI and frontend still running after 30 seconds in 2/2 observations; complete process evidence in stable-npm-dev-2.json.
- [anomaly] Initial stable evidence serialization was interrupted by cleanup EPERM after group TERM removed the processes; repeated with persistent JSON and final empty-group/empty-port verification. This is a test-harness/macOS signal-race limitation, not a framework issue.
- [anomaly] Npm fsevents install-script approval warning on all versions; installation and HMR still passed. Default SitemapPlugin/Radix notices were non-failing.
- [pass] Final independent owned-process/reserved-port scan found no remaining lifecycle processes or listeners.
REVERIFIED:
- F-007: changed — not reproduced on macOS 26.6.2 arm64 / Node26.8.1 / npm11.19.0 with 0.10.0a1 or a2; stable still hangs, with npm remaining alive instead of the original Linux orphan topology. Linux status remains unverified.
ISSUES:
- No new current-train issue found in this scope. The stable shutdown failure is pre-existing and passes on both tested alphas; do not promote it to an alpha2 regression.
NOT_COVERED: Safari/WebKit, Intel macOS, other Node/npm versions, Redis, TTY SIGINT, frontend-only mode, alpha1/stable production, Linux reproduction. See NOTES.md for the brief initial scheduling overlap and repeat methodology.
