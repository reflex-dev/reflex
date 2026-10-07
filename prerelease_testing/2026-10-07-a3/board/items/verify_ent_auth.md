# item: verify_ent_auth
ports: frontend 3620-3639 / backend 8620-8639
model: opus (high)
status: open
brief: ../../briefs/verify_ent_auth.md
artifacts: prerelease_testing/2026-10-07-a3/a3_ent_auth/verification/ + findings-inbox/verify_ent_auth-*.md
covers: independent verification of A3-09 (stale tab stays on protected page) and A3-10 (Redis nav erases protected client storage)
