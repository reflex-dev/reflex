# item: tooling_a2
ports: frontend 3580-3599 / backend 8580-8599
model: sonnet (max)
status: open
brief: ../../briefs/../../../2026-10-05/tooling/README.md
artifacts: prerelease_testing/2026-10-07/tooling_a2/
covers: reflex-hosting-cli 0.2.0a1 + build-sdk 0.1.0a1 JSON/error/auth contracts against a local fixture (reuse ../../../2026-10-05/tooling and ../../../2026-10-05/components/hosting); reflex-release 0.2.0a1 publish-last lockstep change (#7464) via its CLI; docgen 0.10.0a2 BOM/CRLF; otel 0.2.0a1 on 0.10.0a2 (spans exported for a real app)
