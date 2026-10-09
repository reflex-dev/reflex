# Re-verification on train r/pre-2026.10.06-37579583012 (reflex 0.10.0a2) — 2026-10-07

Phase 7 of the campaign: re-run every failing repro from the
[2026-10-06 findings](../2026-10-06/FINDINGS.md) against the newly published train, finish the four
clusters the spend limit interrupted, and sweep for regressions the fixes may have introduced.
[CAMPAIGN_STATE.md](./CAMPAIGN_STATE.md) is the compact context (what shipped, which fix targets which
finding, venvs, paths); [AGENT_BRIEF.md](./AGENT_BRIEF.md) the rules every agent followed;
[briefs/](./briefs/) the per-cluster assignments. Enterprise is tested with the user-supplied OFFLINE
`reflex-enterprise 0.9.7a4` wheel (bypasses the login gate), never the checkout.

Status and results: [FINDINGS.md](./FINDINGS.md) (executive summary, re-verification table, N-001..N-043, cluster summaries) and [RELEASE_PLAN.md](./RELEASE_PLAN.md) (what blocks 0.10.0 vs what gets filed). All 14 clusters are done; each cluster dir has a NOTES.md with rerun commands and a `verification/` subdir where an independent verifier re-tested its medium/high claims.

**Working on this from another session?** Read [COORDINATION.md](./COORDINATION.md): claim an item from
[board/items/](./board/items/) with `scripts/claim.sh <item>`, build envs with `scripts/bootstrap_envs.sh`,
drop findings in `board/findings-inbox/`, release with `scripts/release.sh`.

| dir | covers |
|---|---|
| `packaging/` | `.pyi` audit of all 20 new-train packages: PASS |
| `smoke/` | blank app on 0.10.0a2 driven in Chromium: clean |
| `reverify_core/` | F-001/004/011/012/013/014/016/018 + #7456/#7461/#7465 semantics + enterprise AG Grid model wrapper |
| `reverify_hydration/` | F-002/003/008/010/017 + #7460 regression sweep of the hydration probe app |
| `reverify_db_install/` | F-005/006/007/015 + Python 3.10 drop, install paths, AppHarness #7359, hosting-cli 0.2.0a1 |
| `upgrade_sweep/` | 0.9.12 → 0.10.0a2 in-place upgrades of example apps + stock-install smoke |
| `ent_grid/` | enterprise demos: AG Grid prod leads, dnd, flow, mantine, highcharts, tickets |
| `ent_auth/` | enterprise OIDC/MCP/maps on Redis and in prod |
| `dataeditor/` | data editor / forms / recharts leads with 0.9.12 baselines |
| `events/` | event-loop and Var leads with 0.9.12 baselines |
| `statemgr_perf/` | memory/disk expiry, durations, Redis pool, perf claims |
| `thirdparty_a2/` | 22 third-party packages, local-auth/magic-link/google-auth demos, F-007..F-014/F-018 re-verification; `verification/` for N-039/N-040 |
| `browser_cache_bundle/` | (other session, macOS) prod bundle/network payloads, cache invalidation, nested state, deployments, history |
| `macos_lifecycle/` | (other session, macOS) startup/shutdown, Unicode paths, HMR, npm/bun; F-007 on macOS |
| `pymatrix_a2/`, `tooling_a2/` | (other session) Python-version matrix and local tooling/telemetry coverage — see `board/` |
| `board/` | git-native coordination board: items, claims, results, findings-inbox |
