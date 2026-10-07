# item: a3_preflight
ports: frontend 3500-3519 / backend 8500-8519
model: orchestrator
status: done
brief: ../../briefs/a3_preflight.md
artifacts: prerelease_testing/2026-10-07-a3/a3_preflight/
covers: phase 0/1/5: PyPI publish check of the a3 train, metadata and sibling floors, packaging (.pyi) audit, blank-app smoke dev+prod, N-001 fresh reflex[db] without greenlet on 3.11-3.14
