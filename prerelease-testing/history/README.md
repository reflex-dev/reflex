# Pre-release campaign history

The narrative record of every pre-release QA pass: what was tested, what was found, how it was triaged. Each directory
keeps the campaign's top-level documents (`README.md`, `FINDINGS.md`, `RELEASE_PLAN.md`, and where they existed
`CAMPAIGN_STATE.md`, `PLAN.md`, `REVIEW.md`, publish-validation notes). The 0.10.0a3–a5 passes also keep every work
item's `NOTES.md` under `notes/<item>.md` (exact rerun commands and per-check observations).

| directory | pass | outcome (details in its RELEASE_PLAN.md) |
|---|---|---|
| `2026-08-27-v0.9.9a1` | reflex 0.9.9a1 pre-release | 29 confirmed findings triaged into fix-before-release vs filed |
| `2026-09-10-v0.9.11a1` | reflex 0.9.11a1 pre-release + published validation | maintainer decisions and PR / issue disposition; final release preflight |
| `2026-09-18-v0.9.12a1` | reflex 0.9.12a1 pre-release | five fix-before-release items fixed and re-verified on 0.9.12a2 + enterprise 0.9.6a1; deferred findings filed |
| `2026-10-05-v0.10.0a1` | 0.10.0a1 exploration (+ enterprise 0.9.7a4) | release gate held on an enterprise logout-recovery security weakness (enterprise #245); see FINDINGS.md / REVIEW.md |
| `2026-10-06-v0.10.0a1-gaps` | 0.10.0a1 gap validation | FINDING-001… (later referred to as F-0xx); F-001…F-006 fixed in a2 |
| `2026-10-07-v0.10.0a2` | a2 re-verification + new findings | N-0xx; N-025 / N-032 / N-004 / N-005 / N-039 / N-008 fixed or decided for a3 |
| `2026-10-07-v0.10.0a3` | a3 re-verification (+ enterprise 0.9.7a5) | A3-11 / A3-12 storms fixed by #7505; class-default assignment layer backed out by #7516 |
| `2026-10-08-v0.10.0a4` | a4 re-verification + spot check | nothing new blocking; A4-01 / A4-02 / A4-03 low |
| `2026-10-08-v0.10.0a5` | final pre-release pass for 0.10.0 | every fixed regression re-verified; A5-01 shipped in 0.10.0 as a documented breaking change |

Paths inside these documents (`a3_hydration/src/...`, `reverify_core/...`, `logs/...`, `shots/...`) refer to each
campaign's original layout. The reusable inputs among them were consolidated into `../fixtures/` (each fixture README
says where a fixture came from); the full original trees — logs, screenshots, frame dumps, results and every
intermediate fixture copy, about 320 MB — are preserved on branch `claude/reflex-prerelease-testing-t0sd90` at commit
`008ce80ef546c40ae574d641f425094afc632a6f`, under `prerelease-testing/` (0.9.x passes) and `prerelease_testing/`
(0.10.0 passes, directories `2026-10-05`, `2026-10-06`, `2026-10-07`, `2026-10-07-a3`, `2026-10-08-a4`,
`2026-10-08-a5`). Read one with `git show 008ce80ef:<path>`.

The deduplicated status of every finding across all passes is in `../REGISTRY.md`.
