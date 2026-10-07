# Re-verification on train r/pre-2026.10.06-37579583012 (reflex 0.10.0a2) — 2026-10-07

Phase 7 of the campaign: re-run every failing repro from the
[2026-10-06 findings](../2026-10-06/FINDINGS.md) against the newly published train, finish the four
clusters the spend limit interrupted, and sweep for regressions the fixes may have introduced.
[CAMPAIGN_STATE.md](./CAMPAIGN_STATE.md) is the compact context (what shipped, which fix targets which
finding, venvs, paths); [AGENT_BRIEF.md](./AGENT_BRIEF.md) the rules every agent followed;
[briefs/](./briefs/) the per-cluster assignments. Enterprise is tested with the user-supplied OFFLINE
`reflex-enterprise 0.9.7a4` wheel (bypasses the login gate), never the checkout.

Status and results: [FINDINGS.md](./FINDINGS.md) (written incrementally as clusters report).

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
