# Pre-release testing artifacts — 2026-09-18 batch (reflex 0.9.12a1)

Independent end-to-end testing of the published PyPI pre-releases of the
`r/pre-2026.09.18-35410916948` release train: **reflex 0.9.12a1, reflex-base 0.9.12a1,
reflex-components-code 0.9.6a1, -core 0.9.10a1, -dataeditor 0.9.3a1, -gridjs 0.9.2a1,
-markdown 0.9.4a1, -plotly 0.9.7a1, -radix 0.9.10a1, -recharts 0.9.4a1, -sonner 0.9.4a1**, plus
the already-stable members of the train (moment 0.9.4, lucide 1.0.4, react-player 0.9.2,
docgen 0.9.5, hosting-cli 0.1.72, otel 0.1.0, release 0.1.1, build-sdk 0.0.2).
Previous stable used for baselines: **reflex 0.9.11.post1**. Published reflex-enterprise: **0.9.5**
(installed from the offline wheel, never from a checkout).

**Start with [FINDINGS.md](./FINDINGS.md)** (executive summary, numbered findings with repro +
evidence + regression status, refuted claims, cluster summaries) and
[RELEASE_PLAN.md](./RELEASE_PLAN.md) (what blocks the release vs what gets filed).

## Method

- All installs PyPI-only in isolated uv venvs — never from a checkout. The ground rules given to
  every test agent are in [AGENT_BRIEF.md](./AGENT_BRIEF.md); the per-cluster assignments
  (changelog lines verbatim, PR numbers, things to build and combine) are in [briefs/](./briefs/).
- Every sample app was run for real (`reflex run`, dev and prod) and driven in headless Chromium via
  Playwright with console / network / websocket-frame / server-log capture and screenshots.
- reflex 0.9.11.post1 baselines were run wherever behavior needed differentiating (regression vs
  pre-existing).
- Claimed issues were re-reproduced by independent adversarial verifier agents from the written
  repro alone; each cluster's `NOTES.md` carries a `## VERIFICATION` appendix.
- Orchestration: `.claude/skills/prerelease-test/` (playbook + discovery/audit scripts), two Workflow
  runs (explore → verify pipeline, Opus 5 at xhigh effort, two agents at a time on a 4-CPU box).

## Directory layout

One directory per cluster: sample app sources, driver scripts, a `NOTES.md` (what was tested, exact
rerun commands, observations, verification appendix), trimmed logs and screenshots. Build outputs
(`.web/`, `node_modules/`, venvs, `reflex.lock/`) are excluded via `../.gitignore`.

| dir | covers |
|---|---|
| `smoke/` | Phase 1 de-risk: blank app dev + prod on the published train, generated `package.json` pins |
| `packaging/` | PyPI presence of all 19 packages, `.pyi` stubs in wheel vs sdist, dependency pins, sdist installability, Python 3.10–3.14 resolution, third-party import surface |
| `orch_probes/` | orchestrator's own probes: the enterprise import sweep that found the OIDC metaclass conflict, a framework-only repro of it, build-sdk rename/URL precedence, hosting-cli non-interactive defaults |
| `orch_otel/` | reflex-otel 0.1.0 on 0.9.12a1: is the initial dev `reflex.compile` span tree exported now (#7155)? |
| `router_vars/` | #7068 router split into per-field vars, #7077 inherited-var shadowing, #7136 reserved names |
| `memo_aschild/` | #6850 transparent auto-memo wrappers / `as_child`, #7176 memo app-wraps, #6708 svg memo, #7122 shared event chains, #7121, #7133, #7130 |
| `event_loop/` | #6946 uncached-var delta dedupe, #7168 supersedes ordering, #7145 re-chain recursion, #7156/#7157 callback routing, #7187 redis health client |
| `render_ctx_statemgr/` | #6181 per-state context providers, #6180 provider re-renders, #7159 StateManagerDisk, #7132 `_get_was_touched` |
| `build_prod_export/` | #7078 prerender/compression/preload/lazy bundled libraries/sitemap, #7153 `frontend_path` prefix routes, #7096, #7165, #7142, #7139, #7112 |
| `components_bumps/` | recharts sankey/props, data_editor image cells, plotly `divId`, sonner toast actions, code copy button, core namespace/badge/upload 400, `use_hook_var`/`use_id` |
| `vars_typing/` | #7015 var hashing, #7189 `Annotated`, #7198 var-op memory, #7115, #7131 EnvVar timedelta, #6930 py3.15/lazy imports, #7080 stubs, #6923 State-var page titles |
| `dev_server_cli/` | #6981 SIGTERM, #7089 nocompile marker, #7114 reload port, #7129 bun/npm lockfiles, #7117 local packages, #7202 node-less/react-router 8.4, #7193 JSON logs, #7152, #7166, #7075, #7049 |
| `db_optional_imports/` | #7049 SQLModel/lazy imports/on-demand serializers, #7083 `rx.Model` without the db extra |
| `up_examples_a/` `up_examples_b/` `up_examples_c/` | upgrade regression 0.9.11.post1 → 0.9.12a1 on reflex-examples apps (protocol in `briefs/UPGRADE_PROTOCOL.md`) |
| `ent_aggrid/` `ent_map_dnd_flow_mantine/` `ent_mcp_oidc/` | reflex-enterprise 0.9.5 demos, MCP plugin and OIDC auth on both reflex versions |
| `tools/` | `ports.py` (listening ports → pids; no `ss` in the container), `checkin.sh` (workflow/process/disk summary) |

## Campaign notes for the next run

- `ss`/`netstat` are not installed in this container; `tools/ports.py` lists listening ports with pids.
- Never `pkill -f "reflex run"` here: the pattern matches the invoking shell and kills it (exit 144). Kill by pid, or
  by listening port via `tools/ports.py`. Terminating `reflex run` orphans the react-router dev process, which keeps
  the frontend port bound and silently serves the previous app to the next test.
- `uv pip install --prerelease=allow sentry-sdk` resolves sentry-sdk 3.0.0a7, which crashes inside `sentry_sdk.init()`
  against the opentelemetry-api reflex pulls in — pin `sentry-sdk<3`. Likewise pin `pydantic<2.14` (2.14.0b2 otherwise).
- Enterprise prod mode is gated by the paid-tier check; `CI=true` bypasses only the dev login gate. The 2026-09-10
  campaign used reflex's `APP_HARNESS_FLAG` to get past it; this one did not (policy call for the team).
- The org's monthly spend limit interrupted the fan-out once; `Workflow({scriptPath, resumeFromRunId})` replayed the
  finished agents from cache and re-ran only the failed ones.

## Reusing for future pre-releases

The apps and drivers are version-agnostic: create a venv **from a neutral cwd** (running uv inside
the reflex checkout makes its `exclude-newer` setting silently filter out fresh alphas),
`uv pip install --prerelease=allow 'reflex==<next-alpha>' <component alphas named explicitly>`, run
the app in the cluster dir on free ports, and run its driver against the frontend URL. Each
`NOTES.md` has the exact commands. `AGENT_BRIEF.md` + `briefs/` are a ready-made fan-out for the
same clusters, and `.claude/skills/prerelease-test/` carries the playbook.
