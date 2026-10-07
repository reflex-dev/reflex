# item: a3_upgrade
ports: frontend 3200-3239 / backend 8200-8239
model: opus (high)
status: open
brief: ../../briefs/a3_upgrade.md
artifacts: prerelease_testing/2026-10-07-a3/a3_upgrade/
covers: 0.9.12->a3 and a2->a3 in-place upgrades (pip vs uv, reflex-base floor), upgrade-guide samples, reflex component pointer, run --json drain (#7428), 3.11/3.14 smoke
