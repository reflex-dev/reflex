CLUSTER: pymatrix_a2/browser
SUMMARY: Published alpha2 passed all 216 exact browser checkpoints across Python 3.11.16/3.13.15/3.14.7, dev/prod and Chromium 153/WebKit 26.6. Python 3.10.21 cleanly refuses installation; supported interpreters report the right version and graceful missing-DB-extra diagnostics. No new functional regression was found; pre-existing Pydantic warnings and two cleanup-only worker-exit messages are qualified in NOTES.
ARTIFACTS: prerelease_testing/2026-10-07/pymatrix_a2/browser/
TESTS:
- [pass] Six server runs, 12 browser executions, 18 checkpoints each: 216/216, zero browser anomalies.
- [pass] Exact annotation serialization and repeated nested mutations; computed foreach rows; nullable reset; dataclass/Pydantic/list/factory defaults remain isolated across tabs and contexts.
- [pass] ABC inherited event, postponed annotations, background completion, client navigation and full reload persistence.
- [pass] Actual Python 3.10 install exits 1 with Python>=3.11,<4.0 explanation; import spec absent.
- [pass] Three reflex --version checks and three no-DB-extra db init diagnostics; three supported-interpreter app imports.
- [anomaly] Pydantic __fields__ deprecations reproduced by a minimal public fixture on 0.9.12/a1/a2; pre-existing.
- [anomaly] Dev 3.13/3.14 worker-exit errors follow intentional stopping/flush; CLI 0 and empty cleanup evidence.
- [anomaly] Exploratory stable whole-fixture import fails on new ABC support before warning probe; retained separately, replaced with compatible minimal warning control. Alpha1 whole-fixture import passes.
- [pass] All six owned process groups, ports 3540/8540 and Playwright processes empty at 08:48:59 UTC.
REVERIFIED:
- None assigned to this browser subtree; parent owns F-011/F-016 and typing.
ISSUES:
- No new release-blocking or browser-functional issue found.
NOT_COVERED: Full stable/a1 browser matrix, native Safari/Firefox, other OSes, alternate dependency versions, separate blank-template wizard flow, DB operations, malformed annotations and typing. No performance claims.
