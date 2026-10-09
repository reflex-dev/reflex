# 0.10.0a5 final pre-release pass (2026-10-08)

Re-runs every identified-and-fixed regression of the 0.10 train against the published reflex 0.10.0a5 / reflex-base
0.10.0a5 (+ reflex-enterprise 0.9.7a5), with the broken version as positive control, and hunts the three a5 changes
(#7360, #7519, #7504) for new regressions. Context: [CAMPAIGN_STATE.md](./CAMPAIGN_STATE.md). Agent rules:
[AGENT_BRIEF.md](./AGENT_BRIEF.md). Results: [FINDINGS.md](./FINDINGS.md), [RELEASE_PLAN.md](./RELEASE_PLAN.md).

| item | covers |
|---|---|
| `preflight` | PyPI publish check, wheel contents vs tag, `.pyi` audit, changelogs, blank-app smoke |
| `a5_hydration_router` | #7360 router data + credential exposure; F-002, F-003, A3-11, A3-12 |
| `a5_class_state` | #7519 `set_default` / copy-at-definition / error owner; F-004, N-004/005/008/039, A3-01/02/04, A4-01/02 |
| `verify_class_state5` | independent verification of A5-01 … A5-05 |
| `a5_upgrade_ent` | enterprise a5 on reflex a5 (N-032, N-025, auth, deep links), N-001, F-005, F-006, F-014, upgrades, third-party |

Reuse for the final release: change the versions in `scripts/bootstrap_envs.sh` and `CAMPAIGN_STATE.md`; every item's
`NOTES.md` has its rerun commands.
