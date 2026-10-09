# 0.10.0a4 re-verification (2026-10-08)

Re-runs the original failing repros of the a3 pass's findings (`../2026-10-07-a3/`) against the published reflex 0.10.0a4 /
reflex-base 0.10.0a4 (+ reflex-enterprise 0.9.7a5), and spot-checks the three a4 changes (#7505, #7513, #7516) for new
regressions. Context: [CAMPAIGN_STATE.md](./CAMPAIGN_STATE.md). Agent rules: [AGENT_BRIEF.md](./AGENT_BRIEF.md).

| item | covers |
|---|---|
| `preflight` | PyPI publish check, wheel contents vs source, `.pyi` audit, changelog/docs, blank-app smoke |
| `a4_hydration` | A3-11 / A3-12 original repros + #7505 regression hunt (storage sync, cookies, local-auth) |
| `a4_class_state` | A3-01 / A3-02 / A3-04 original repros (now moot) + #7516 regression hunt, docs samples |
| `a4_upgrade_ent` | in-place upgrades 0.9.12 / a3 → a4, third-party packages, enterprise a5 auth / grid / demos |
| `verify_class_state` | independent verification of A4-01 / A4-02 |
| `verify_hydration` | independent verification of A4-03 (+ the boot-window facet) |

Results: [FINDINGS.md](./FINDINGS.md), [RELEASE_PLAN.md](./RELEASE_PLAN.md).

Reuse for the next build: change the versions in `scripts/bootstrap_envs.sh` and `CAMPAIGN_STATE.md`; every item's
`NOTES.md` has its rerun commands.
