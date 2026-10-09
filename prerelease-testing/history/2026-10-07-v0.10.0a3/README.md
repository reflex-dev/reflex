# 0.10.0a3 re-verification (2026-10-07, second pass)

Re-runs the original failing repros of the a2 pass's must-fix findings against the published reflex 0.10.0a3 /
reflex-base 0.10.0a3 and reflex-enterprise 0.9.7a5, and hunts for regressions the fixes introduced.

| item | covers |
|---|---|
| `a3_preflight` | PyPI publish check, metadata and floors, `.pyi` packaging audit, blank-app smoke, N-001 |
| `a3_ent_grid` | N-025 + enterprise#273 regressions, AG Grid and enterprise demo smoke |
| `a3_ent_auth` | N-032 + #7493 regressions in OIDC, auth matrix, MCP, maps |
| `a3_hydration` | core boot/hydration after #7493 (F-002/F-003 stay fixed), local-auth / google-auth |
| `a3_class_state` | N-004/N-005/N-006/N-008/N-039/N-040 + #7495/#7494 regressions |
| `a3_upgrade` | in-place upgrades from 0.9.12 and a2, install paths, upgrade-guide samples, `reflex component`, #7428 |
| `a3_events_tp` | events suite and third-party package sweep vs a2 |

Reuse for the next build: change the versions in `scripts/bootstrap_envs.sh` and `CAMPAIGN_STATE.md`, reset `board/claims`,
and every item's `NOTES.md` has its rerun commands.
