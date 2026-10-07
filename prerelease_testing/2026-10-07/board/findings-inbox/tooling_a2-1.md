ITEM: tooling_a2
KIND: reverify
REF: 2026-10-05 FINDINGS.md item 8
TITLE: Initial rejected-token guidance still omits the post-authentication login hint
SEVERITY: low
STATUS: still-broken
REGRESSION_VS_0.9.12: unknown
REGRESSION_VS_0.10.0a1: no
REPRO: Follow tooling_a2/cli/NOTES.md to create the exact published environment, then run hosting.py through that environment from neutral scratch. Its localhost fixture returns 401 at /authenticate/me for an explicit synthetic token with --no-interactive. The CLI exits nonzero and preserves the different stored fixture token, but omits reflex login. Compare the fixture's 401 after successful initial authentication, which includes the hint. No real account or user credential file is involved.
EVIDENCE: prerelease_testing/2026-10-07/tooling_a2/cli/hosting-a2-run3.json contains full argv/output/HTTP sequences for current hosting CLI0.2.0a1; prior-auth-baseline.json copies the original 0.1.73a1 evidence and provenance from 2026-10-05/tooling/results.json. Independent review checked this copy byte-for-data against its source. Old hosting CLI was not reinstalled; stable-baseline status is unknown.
ROOT_CAUSE_GUESS: Distinct initial whoami-style authentication error path and later request-expiry path provide different guidance. This is the already documented message/changelog boundary, not authentication bypass, secret exposure, destructive credential handling or a new release blocker.
