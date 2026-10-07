# item: verify_hydration
ports: frontend 3660-3679 / backend 8660-8679
model: opus (high)
status: open
brief: ../../briefs/verify_hydration.md
artifacts: prerelease_testing/2026-10-07-a3/a3_hydration/verification/ + findings-inbox/verify_hydration-*.md
covers: independent verification of A3-11 (sync=True boot-echo ping-pong, regression vs a2) and A3-12 (concurrent sync=True writes loop)
