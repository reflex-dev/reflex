# Pre-release testing artifacts — 2026-09-10 batch (reflex 0.9.11a1)

Independent end-to-end testing of the published PyPI pre-releases of the
`r/pre-2026.09.10-34457666442` release train: reflex 0.9.11a1, reflex-base 0.9.11a1,
reflex-components-radix 0.9.9a1, -code 0.9.5a1, -moment 0.9.4a1, -plotly 0.9.6a1,
-recharts 0.9.3a1, -sonner 0.9.3a1, reflex-hosting-cli 0.1.72a1, reflex-release 0.1.1a1
and the brand-new **reflex-otel 0.1.0a1**.

**Start with [FINDINGS.md](./FINDINGS.md)** — executive summary, numbered findings with
repros and evidence, and per-cluster summaries. [RELEASE_PLAN.md](./RELEASE_PLAN.md)
triages them into fix-before-release vs file-as-issue.

## Method

- All installs PyPI-only in isolated uv venvs — never from a checkout. The ground rules given
  to every test agent are in [AGENT_BRIEF.md](./AGENT_BRIEF.md).
- Every sample app was run for real (`reflex run`, dev and mostly prod too) and driven in
  headless Chromium via Playwright with console / network / websocket-frame / server-log
  capture and screenshots.
- reflex 0.9.10.post2 baselines were run wherever behavior needed differentiating
  (regression vs pre-existing).
- Claimed issues were re-reproduced by independent adversarial verifier agents from the
  written repro alone; NOTES.md files carry their `## VERIFICATION` appendices.

## Directory layout

One directory per cluster: sample app sources, driver scripts, a NOTES.md (what was tested,
exact rerun commands, observations, verification appendix), logs and screenshots. Build
outputs (`.web/`, `node_modules/`, venvs) are excluded.

| dir | covers |
|---|---|
| `smoke/` | Phase 1 de-risk: blank app dev + prod, Bun 1.4 / lockfile v2, generated pins, CLI startup |
| `packaging/` | PyPI presence of all 17 packages, `.pyi` stubs in wheel vs sdist, dependency pins vs changelog, sdist installability |
| `hmr_runtime/` | #7071 hot-update runtime stability, #7048 Safari cache-bust streaming, #7021 dev-server knobs |
| `hybrid_property/` | #6812 hybrid_property overhaul, #7014 dataclass proxy metadata, #6929 ForwardRef probes (incl. Python 3.14) |
| `bg_rehydrate/` | #6995 background flush on raise, #7072 redis post-eviction rehydrate, #7073 routeless rehydrate |
| `event_hotpath/` | #7025 event-loop hot path: ordering, substates, interval vars, route matching, socket handlers, A/B throughput |
| `orch_probes/` | orchestrator's own offline probes: AppHarness extra, otel inertness, `_load_config` deprecation, `reserve_stdout`, `frontend_path` validation, full `reflex cloud` CLI sweep |
| `up_counter_todo_clock/` | upgrade 0.9.10.post2 → 0.9.11a1: counter, todo, clock, linkinbio (+ full-alpha-train path) |
| `up_upload_traversal_quiz/` | upgrade: upload (sanitizer), traversal (sonner), quiz (shiki, table) |
| `up_dataviz_local_lorem/` | in-place upgrade (same venv, app dir, `.web/`, sqlite db) of `local-component` (local React component, refs, popover+form), `lorem-stream` (background streaming tasks) and `data_visualisation` (rx.Model + alembic + 36-row table); also the `reflex-release` 0.1.1a1 gates against a worktree of the release branch |
| `ent_aggrid/` | enterprise ag_grid + ag_grid_finance demos, dev and prod, both reflex versions |
| `ent_map_dnd_flow/` | enterprise map, dnd and flow demos |
| `ent_mcp_oidc/` | enterprise MCP plugin and OIDC auth: a purpose-built MCP exercise app, an `AuthPlugin` app and a self-contained OIDC provider (discovery, JWKS, PKCE S256, refresh, userinfo, RP-initiated logout) driven end to end |
| `otel/` | the new reflex-otel 0.1.0a1: instrumentor, spans and metrics, the documented env-var recipe, browser plugin |
| `components_bumps/` | all six bumped component libraries (moment, code, plotly, radix, recharts, sonner) in dev and prod, with the previous stable as baseline |

Never run, for want of budget, and none covering a surface this train changes:
`ent_mantine_highcharts_tickets`, `config_assets_cli`, `memo_hash`, `reverify_prev` and four
further reflex-examples apps.

## Reusing for future pre-releases

The apps and drivers are version-agnostic: create a venv, `uv pip install --prerelease=allow
'reflex==<next-alpha>'` **from a neutral directory** (running uv inside the reflex checkout
makes its `exclude-newer` setting silently filter out fresh alphas), run the app in the cluster
dir on free ports, and run its driver script against the frontend URL. Each NOTES.md has the
exact commands. AGENT_BRIEF.md is a ready-made brief for orchestrating the same fan-out again,
and `.claude/skills/prerelease-test/` carries the campaign playbook and the discovery /
packaging-audit scripts.

## Campaign notes for the next run

- Background agents only make progress while the session is awake; schedule check-ins close
  together, or keep foreground work running, or the fan-out stalls between wakes.
- `uv pip install --prerelease=allow 'reflex==<alpha>'` **without `--upgrade`** leaves the old
  stable component packages in an existing venv — reflex pins `reflex-base` exactly but the
  component packages only by floor. You can believe you are testing the train and be testing new
  core against old components. Use a fresh venv, or pass `--upgrade` and name the component
  alphas explicitly.
- `rxe.App()` exits with "reflex-enterprise is free to use but you must be logged in" for an
  anonymous tier whenever the frontend is served. `CI=true` (or `REFLEX_BACKEND_ONLY`) skips the
  check; there is no way to exercise enterprise **prod** mode without a licence.
- Terminating `reflex run` from a script can orphan the vite frontend process, which keeps the
  port bound and makes the next run fail with `Address already in use`.
  `up_dataviz_local_lorem/cycle.sh` carries a `/proc/net/tcp` sweep that cleans it up.
- This campaign was interrupted repeatedly by the organisation's monthly spend limit. Workflows
  were resumed from cache each time (`Workflow({scriptPath, resumeFromRunId})`), and the
  remaining clusters were re-ordered highest-risk-first into one script so that a truncated run
  still covers what matters. That ordering is worth adopting from the start.
