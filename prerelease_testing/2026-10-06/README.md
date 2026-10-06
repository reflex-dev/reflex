# Pre-release gap validation — 2026-10-06 (reflex 0.10.0a1 train + reflex-enterprise 0.9.7a4)

Follow-up to the [2026-10-05 campaign](../2026-10-05/README.md), which tested the same published
pre-releases and left numbered findings in its [FINDINGS.md](../2026-10-05/FINDINGS.md). The task for
this run was to validate that **no other such issues exist**: identify what the earlier campaign did not
cover, and exercise those gaps end-to-end against the PUBLISHED packages only (PyPI, isolated venvs;
never the checkout).

Start with [FINDINGS.md](./FINDINGS.md) (executive summary, new findings with repro + evidence +
regression status, refuted claims, cluster summaries) and [RELEASE_PLAN.md](./RELEASE_PLAN.md).
The rules every agent followed are in [AGENT_BRIEF.md](./AGENT_BRIEF.md); the per-cluster assignments
(changelog lines verbatim, PR numbers, things to build and combine) are in [briefs/](./briefs/).

## Versions under test

Unchanged from 2026-10-05 except where noted: reflex / reflex-base 0.10.0a1; reflex-components-code,
-core, -gridjs, -markdown, -moment, -plotly, -radix, -recharts 0.10.0a1; reflex-docgen 0.10.0a1;
reflex-hosting-cli 0.1.73a1; reflex-release 0.1.2a1; reflex-build-sdk 0.0.5; reflex-otel 0.1.0;
lucide 1.0.4; react-player 0.9.2; sonner 0.9.4; **reflex-components-dataeditor 0.9.3.post1 (new:
published 2026-10-06 16:35 UTC, after the previous campaign; replaces the yanked 0.9.3)**;
**reflex-enterprise 0.9.7a4**. Previous stable for baselines: reflex 0.9.12 (+ enterprise 0.9.6).
`reflex-workflow` exists in the release branch but is unreleased (no CHANGELOG, not on PyPI).

Environment: Linux x86_64, 4 CPU / 15 GB, Python 3.10–3.14 via uv, Node 22.22, bun 1.4.2,
Playwright 1.63 + Chromium 1194 build, redis-server local.

## Gap analysis → clusters

| dir | gap it covers |
|---|---|
| `smoke/` | Phase 1 de-risk: blank app on the published train, driven in Chromium (clean) |
| `packaging/` | `.pyi` stub audit of all 19 packages in wheel+sdist, now including dataeditor 0.9.3.post1 (PASS) |
| `thirdparty/` | breaking-change surface vs the third-party ecosystem (reflex-local-auth, -global-hotkey, -google-auth, -magic-link-auth, …), removed-name probes, downstream State patterns |
| `upgrades_a/` | in-place 0.9.12→0.10.0a1 upgrades of reflex-examples apps with third-party deps and client storage (form-designer, reflexle, github-stats, clock) |
| `upgrades_b/` | in-place upgrades of db/upload/streaming/custom-component examples (twitter, upload, lorem-stream, local-component, nba, quiz, snakegame) |
| `hydration/` | #7064 combined hydrate+connect: LocalStorage/SessionStorage/Cookie vars, on_load variants, reconnect, multi-tab, dynamic routes, dev vs prod |
| `statemgr_perf/` | #7318 memory/disk expiry with a real app, duration settings + deprecation locations, Redis pool under load, perf claims measured vs 0.9.12 |
| `ent_demos/` | enterprise demos not run before: dnd, flow, mantine, highcharts, tickets, AG Grid model wrapper/master-detail/tree/pivot |
| `ent_auth_mcp_redis/` | enterprise OIDC + MCP + maps under Redis/multi-worker, expiry/revocation, MCP scope/consent/rate-limit/background paths |
| `pymatrix_install/` | Python 3.10/3.14, user-realistic install paths (`pip install` without --pre → stable components + alpha base), node/npm checks, `reflex component` removal, AppHarness, ty/pyright |
| `dataeditor_components/` | dataeditor 0.9.3.post1 on alpha and stable, form-submission/match/memo-naming/plotly/recharts/radix/shiki/moment interactions |
| `events_vars/` | supersedes/background/nested event lists, throttle/debounce/temporal, Var slicing/deep_equals/_replace, type-check logging, state API edge cases |

Build outputs (`.web/`, `node_modules/`, venvs, `reflex.lock/`, `.states/`, `*.db`) are excluded via
`.gitignore`.
