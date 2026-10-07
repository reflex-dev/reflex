# item: verify_upgrade
ports: frontend 3640-3659 / backend 8640-8659
model: opus (high)
status: open
brief: ../../briefs/verify_upgrade.md
artifacts: prerelease_testing/2026-10-07-a3/a3_upgrade/verification/ + findings-inbox/verify_upgrade-*.md
covers: independent verification of A3-06 (guide gap), A3-07 (--json ignores pid SIGINT), A3-08 (#7428 cap truncates last record)
