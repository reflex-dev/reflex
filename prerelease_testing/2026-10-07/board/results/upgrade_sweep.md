CLUSTER: upgrade_sweep
SUMMARY: In-place and cold 0.9.12 -> 0.10.0a2 upgrades of form-designer, github-stats, clock, twitter (disk state) and twitter + Redis (prod), driven in Chromium with identical flows before and after, plus a1 -> a2 in place and a stock blank-app install smoke. No upgrade regression: every check that passes on 0.9.12 passes on a2 (dev, prod, cold), console/network signatures identical to 0.9.12 and to the 10-06 a1 run, client storage restored with no first-load write-back, DB rows/alembic heads unchanged, Redis sessions survive. Agent was cut off by the spend limit after writing NOTES.md and copying artifacts; this results file was written by the orchestrator from NOTES.md.
ARTIFACTS: prerelease_testing/2026-10-07/upgrade_sweep/ (NOTES.md with rerun instructions, app copies, bin/, scripts/, freeze/, pkg/, logs/, shots/<app>/<tag>.json).
TESTS:
- [pass] form-designer full/entry: 0.9.12 16/0/4 + 14/0/1; a2 in place 12/0/1 + 14/0/1; cold same; prod 12/0/1 + 15/0/0.
- [pass] github-stats fresh/persist (GraphQL stub): 0.9.12 14/0/2; a2 in place 12/0/2; cold 12/0/2; prod 13/0/1 (one 0.9.12-only driver timing race).
- [pass] clock 17/0/0 on every version; one-browser-context stop/upgrade/restart 10/0/1 (control 0.9.12->0.9.12 identical).
- [pass] twitter dev disk state: base 21/0/0, up 14/0/0 in place and cold; disk `.states` wiped on every restart on 0.9.12 too.
- [pass] twitter prod + Redis: base 19/0/2, up 12/0/2, stale 0.9.12 tab 8/0/3 against the a2 backend; pickled SQLModel session row survives.
- [pass] client storage: 0.9.12-written LocalStorage/cookie restored, nothing newly written on first load (#7460); positive control catches the a1 bug.
- [pass] DB: alembic heads unchanged, every 0.9.12 row digest unchanged, `db migrate`/`makemigrations` after upgrade rc 0 with no new migration.
- [pass] a1 -> a2 in place (clock): clean; `.web/package.json` identical.
- [pass] stock smoke: `reflex init --template blank` + dev + prod on a fresh a2 venv clean; package.json byte-identical to the 10-06 a1 smoke; Python 3.10 refused cleanly by uv and pip.
- [fail] fresh `reflex[db]` install (0.9.12 and a2 alike) resolves SQLAlchemy 2.1.3 without greenlet -> `import reflex.model` ImportError (N-001, fix PR reflex-dev/reflex#7466).
REVERIFIED:
- F-002 fixed; F-003 fixed (deterministic); F-005 fixed (UTCDateTime migrations apply, no downgrade); F-006 fixed (pip -U without --pre moves all 13 component packages); F-014 unchanged; F-019 unchanged (stale prod tab gets only a server-side version warning).
ISSUES:
- N-001 (HIGH, environment drift, hits 0.9.12 too): greenlet missing from fresh `reflex[db]` installs.
- F-014 (LOW, unchanged), F-019 (LOW, unchanged).
NOT_COVERED: the other reflex-examples apps (covered on 10-06), Windows/macOS, hosting deploys. A stray `/apps` directory at the filesystem root was created by a mistyped export and left for a human to remove.
