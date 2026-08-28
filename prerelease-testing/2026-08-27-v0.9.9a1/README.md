# Pre-release testing artifacts — 2026-08-27 batch (reflex 0.9.9a1)

Independent end-to-end testing of the published PyPI pre-releases:
reflex 0.9.9a1, reflex-base 0.9.9a1, reflex-components-core 0.9.9a1,
reflex-components-radix 0.9.8a1, -code 0.9.4a1, -plotly 0.9.5a1, -sonner 0.9.2a1,
-dataeditor 0.9.2a1, -lucide 1.0.4a1, -react-player 0.9.2a1, reflex-docgen 0.9.5a1,
reflex-hosting-cli 0.1.71a2.

**Start with [FINDINGS.md](./FINDINGS.md)** — executive summary, 29 confirmed findings
(with repros and root-cause analysis), refuted claims, and per-cluster summaries.

## Method

- All installs PyPI-only in isolated uv venvs — never from a checkout. The exact ground
  rules given to every test agent are in [AGENT_BRIEF.md](./AGENT_BRIEF.md).
- Every sample app was run for real (`reflex run`, dev and mostly also prod) and driven in
  headless Chromium via Playwright with console/network/server-log capture and screenshots.
- 0.9.8 stable baselines were run wherever behavior needed differentiation
  (regression vs pre-existing).
- Every claimed issue was independently re-reproduced by a separate adversarial verifier
  agent from the written repro steps alone; NOTES.md files carry their VERIFICATION
  appendices. Only verifier-confirmed items are listed as findings.

## Directory layout

One directory per test cluster; each contains the sample app source(s), Playwright driver
scripts, a NOTES.md (what was tested, how to rerun, observations + VERIFICATION appendix),
logs, and screenshots. Build outputs (.web/, venvs, node_modules) are gitignored.

Phase 1 — feature exploration on 0.9.9a1:

| dir | covers |
|---|---|
| `routing/` | #6593 on_load supersedes/cancellation, #6790 splat matching, #6953 static/dynamic siblings, #6919 chained-event routing |
| `memo/` | #6949 call-site auto-memoization, #6605 RestProp styles, #6945 displayName, #6730 wrapper=; + client_state/ComponentState combos |
| `state_concurrency/` | #6920 background delta race, #6830 lock isolation, #6734 emit_update flush |
| `client_error/` | #6827 delta validation + client_error socket event, abuse hardening |
| `logging_cli/` | #6863/#6865 logging pipeline + --json, #6867 shims, #6924 deploy fallback |
| `pydantic_optional/` | #6786 bare/pydantic/db extras, upgrade path |
| `typing_python/` | #6944 PEP 695 aliases, #6890 py3.14, #6846 annotation shadowing (3.11–3.14) |
| `components/` | #6520 code_block, #6905 rx.script, #6776 App(theme), #6753 upload sanitizer, #6951 badge ref |
| `registration_context/` | #6382 multi-app isolation, AppHarness x2, breaking API surface |
| `prod_export/` | React Router 8 prod/export/preview, custom react-router components, node floor |
| `devtools_perf/` | #6945 runtime fiber naming, #6905 owner stacks, plotly 0.9.5a1 |

Phase 2 — upgrade (reflex-examples, 0.9.8 → 0.9.9a1 in place + cold) and enterprise
(published reflex-enterprise 0.9.4 vs reflex 0.9.9a1, with 0.9.8 baselines):

| dir | covers |
|---|---|
| `up_counter_todo/` | counter, todo |
| `up_upload_clock/` | upload, clock (stable moment package interplay) |
| `up_reflexle_snake/` | reflexle (reflex-global-hotkey), snakegame |
| `up_lorem_form/` | lorem-stream (streaming), form-designer (reflex[db] + reflex-local-auth) |
| `up_local_basic/` | local-component (local JSX asset), basic_crud (db + fastapi) |
| `ent_aggrid/` | ag_grid demo (17 routes), FINDING-001 minimal triggers |
| `ent_map_dnd/` | map + dnd demos, FINDING-001 scope mapping |
| `ent_misc/` | mantine, flow, MCP plugin (real MCP client), OIDC (mock IdP) |

## Reusing for future pre-releases

The apps and drivers are version-agnostic: create a venv, `uv pip install
--prerelease=allow 'reflex==<next-alpha>'`, run the app in the cluster dir on free ports,
and run its `*_drive*.py` / `drive_*.py` script against the frontend URL. NOTES.md in each
dir has exact commands. AGENT_BRIEF.md is a ready-made brief for orchestrating the same
fan-out again.
