# Findings — re-verification on reflex 0.10.0a3 / reflex-base 0.10.0a3 + reflex-enterprise 0.9.7a5, 2026-10-07 (second pass)

**Status: IN PROGRESS.** Board: [board/](./board/). Protocol: [COORDINATION.md](./COORDINATION.md). Context: [CAMPAIGN_STATE.md](./CAMPAIGN_STATE.md).
Previous pass (a2 train): [../2026-10-07/FINDINGS.md](../2026-10-07/FINDINGS.md), plan [../2026-10-07/RELEASE_PLAN.md](../2026-10-07/RELEASE_PLAN.md).

## Versions under test
- reflex 0.10.0a3, reflex-base 0.10.0a3 (`r/pre-2026.10.06-37579583012` @ `555b667c1`); all other train packages unchanged from a2.
- reflex-enterprise 0.9.7a5 (offline wheel `reflex_enterprise-0.9.7a5-0offline-py3-none-any.whl`, sha256 aad70d1a…; PyPI wheel 5e394ddb…).
- Baselines: reflex 0.10.0a2 (+ enterprise 0.9.7a4), reflex 0.9.12 (+ enterprise 0.9.7a5 / a4).

## Pre-flight (orchestrator)
- 19:25 UTC: `Release from changelog` run 37673748075 built reflex-base 0.10.0a3; its `publish` job waits for environment
  approval, so reflex / reflex-base 0.10.0a3 are not on PyPI yet (discovery script: 18/20 OK, the two a3 packages
  "NOT ON PYPI"). Agents started with positive controls on a2 / 0.9.12 meanwhile.
- reflex-enterprise 0.9.7a5: the offline wheel and the PyPI wheel differ only in `constants.py` (`IS_OFFLINE = True`).
  a4 → a5 changes only `formatColumnDefs` in `components/ag_grid/aggrid.py` (the `typeof __reflex === 'undefined'` early
  return and the unused `jsx`/`Fragment` lookups are gone) plus the CHANGELOG entry (enterprise#260). Metadata unchanged:
  `reflex[db]>=0.9.6`, `Requires-Python >=3.10,<4.0`.

## Re-verification table (must-fix findings of the a2 pass)
| id | a2-pass status | a3 result | evidence | item |
|---|---|---|---|---|
| N-001 greenlet missing from `reflex[db]` | HIGH, all fresh installs | _pending_ | | a3_preflight |
| N-025 prod AG Grid Var `column_defs` empty | HIGH regression | _pending_ | | a3_ent_grid |
| N-032 OIDC cross-tab logout | HIGH regression | _pending_ | | a3_ent_auth |
| N-004 0.10 state unreadable by 0.9 | MEDIUM, decided: document | _pending_ | | a3_class_state |
| N-005 plain default drops storage | MEDIUM | _pending_ | | a3_class_state |
| N-039 patch/restore of a var default | MEDIUM | _pending_ | | a3_class_state |
| N-008 `_x__y` accepted by the dev guard | LOW regression | _pending_ | | a3_class_state |
| N-006 `BackendVarFormatError` message | LOW docs | _pending_ | | a3_class_state |
| N-002/N-007/N-009/N-024/N-040 docs | LOW docs | _pending_ | | a3_upgrade |
| F-014 `reflex component` message | LOW | _pending_ | | a3_upgrade |

## New findings on 0.10.0a3
_none yet_

## Cluster summaries
_pending_
