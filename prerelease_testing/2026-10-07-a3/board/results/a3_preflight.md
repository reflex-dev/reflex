CLUSTER: a3_preflight
SUMMARY: All 20 train packages are on PyPI (reflex/reflex-base 0.10.0a3 since 19:52 UTC), the .pyi packaging audit passes, the published reflex pins reflex-base==0.10.0a3, N-001 is fixed on every Python/installer combination, and a blank app plus an rx.Model app run clean in dev and prod.
ARTIFACTS: prerelease_testing/2026-10-07-a3/a3_preflight/
TESTS:
- [pass] publish check (20/20 wheel+sdist)
- [pass] pyi audit (122 stubs)
- [pass] metadata: reflex-base==0.10.0a3 pin, greenlet>=3.3 in db extra
- [pass] N-001 fresh installs uv/pip x 3.11-3.14 (8/8)
- [pass] N-001 reflex db init/makemigrations/migrate (pip-3.12, uv-3.14)
- [pass] rx.Model CRUD in prod
- [pass] blank-app smoke dev + prod
REVERIFIED:
- N-001: fixed — greenlet 3.5.6 resolves through the db extra; import reflex.model and reflex db * work
ISSUES: none
NOT_COVERED: reflex.dev docs pages (blocked by the sandbox proxy); 3.11/3.14 app smoke and install-path matrix are in a3_upgrade
