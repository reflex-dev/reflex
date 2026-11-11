# Campaign state — 0.11.0a1 pass on the reflex 0.11.0 train (2026-11-11)

Agents read this first, then `AGENT_BRIEF.md` in this directory.

## What is under test
- **reflex 0.11.0a1 + reflex-base 0.11.0a1**, released from `r/pre-2026.11.10-42931773407` @ `cb08dfa9c` (tag
  `v0.11.0a1`). Re-released in this train: reflex-components-core / -radix / -code 0.11.0a1, reflex-components-lucide
  1.1.2a1, reflex-hosting-cli 0.2.2a1, reflex-otel 0.2.1a1, reflex-release 0.2.2a1. Unchanged siblings stay on 0.10.x.
  Separately published 2026-11-05: reflex-workflow 0.0.1a1 (reflex-otel 0.2.1a1 instruments it).
  `check_release_versions.py --ref v0.11.0a1`: **20/20 OK** (wheel+sdist).
- Preflight: `check_wheel_sources.py` — 73 changed source files byte-identical in `$SB/envs/new` (not installed:
  reflex-components-internal, reflex-otel, reflex-release, reflex-site-shared, reflex-workflow). `.pyi` audit: PASS, 122
  stubs in both wheel and sdist, no foreign stubs. Blank app dev + prod: clean in Chromium; SIGINT stops the whole tree.
- Published `reflex` 0.11.0a1 `Requires-Dist`: `reflex-base==0.11.0a1`, core/code/radix `>=0.11.0a1`, but
  **`reflex-components-lucide>=1.1.1`** and **`reflex-hosting-cli>=0.2.1`** (the train's lucide #7674 and hosting-cli
  #7670 fixes are not pulled in by an in-place `pip install -U reflex`). radix 0.11.0a1 requires `reflex-base>=0.10.1`,
  `reflex-components-core>=0.10.1`; code 0.11.0a1 requires `>=0.10.0` floors. `redis<9.0,>=6.4`.
- **reflex-enterprise 0.9.11** (PyPI, uploaded 2026-11-10, `reflex[db]>=0.9.6`) — run with `CI=true`. Source checkout
  (read-only, for demos/tests only, never install from it): `/home/user/reflex-enterprise` @ `b9ec0a9` = tag `v0.9.11`.
  A short-lived, no-permission `REFLEX_ACCESS_TOKEN` supplied by the user is at `$SB/secrets/reflex_access_token`
  (mode 600, scratch only): `REFLEX_ACCESS_TOKEN="$(cat $SB/secrets/reflex_access_token)"`. NEVER write its value
  under the repo; grep copied logs for `rfx_` and redact. The account stub (`fixtures/enterprise/lib.sh acct_stub`)
  remains the fallback.

## What changed since 0.10.1 (82 commits; every CHANGELOG.md top entry)
| PR | Change | Risk (what to hunt) |
|---|---|---|
| #7742 | alembic `env.py` template; `reflex db` = thin alembic wrappers; old stock env.py auto-replaced (kept as `env.old`) by next `reflex db`/`migrate()`; `reflex.model.alembic_autogenerate`/`get_migration_history`/`format_revision` deprecated | upgrade of apps with existing revisions; user-edited env.py; `rx.model.migrate()` at import; multiple metadatas; spurious autogenerate diffs; alembic CLI from app dir |
| #7756 | built-in serializer for SQLAlchemy `DeclarativeBase` models; `synonym()` typing | MappedAsDataclass models as state vars; relationships; detached/expired attrs; asession; mutation tracking |
| #7679 | db docs rewritten around SQLAlchemy models; `db` extra adds `aiosqlite` | following the new docs verbatim; `rx.asession` on sqlite |
| #7739 | starlette-admin `rx.AdminDash` removed (`AdminDashRemovedError`) | error quality; docs guide via `api_transformer` works |
| #7673 / #7770 / #7782 / #7715 / #7752 / #7755 / #7754 | `@rx.event` returns `EventHandler`; awaitable handlers with return values; decorators above `@rx.event` deprecated; stateless handlers REVERTED (#7770, module-level fn stays plain + warns); awaited handlers pass middleware | stacked decorators in real apps; await in background task / `async with self` / redis / substates / cross-state; middleware blocking; typing |
| #7696 / #7412 | failed/cancelled handler's writes after last yield are sent / persisted (redis) | supersedes + redis; exceptions mid-yield; background |
| #7534 / #7751 / #7757 / #7738 | redis lock/lease rewrite (oplock), subscriber loop, redis-py 8 + `socket_timeout=None`, bg-task `get_state` cancellation unlock | multi-worker prod + redis; cancellation; redis restart; redis-py 7 vs 8 |
| #7616 / #7590 | cached vars recomputed after hot reload; workers load rxconfig before app (`state_auto_setters` under spawn) | disk/redis managers + hot reload; spawn start method |
| #6936 | `rx.client_state` promoted (named = global, unnamed = scoped to page / `@rx.memo` instance), `.set` replaces `.set_value`; `rx._x.client_state` deprecated | memo instances, foreach, navigation reset, push/retrieve from backend, prod |
| #7642 | `SetVar` for `set`/`frozenset` vars; array ops on sets deprecated | foreach, cond, computed vars, mutation (`add`/`discard`), JSON round-trip, sets of tuples |
| #7582 / #7637 / #7652 | storage var declaration rules; shared-name LocalStorage sync in writing tab; localStorage clear resets | existing apps with `default_factory`; multi-tab |
| #7648 / #7651 / #7548 | `@property` on model via Var raises; backend-var misuse raises `BackendVarFormatError`; unicode code point ops | existing apps that relied on these; error messages |
| #7694 / #7793 / #7276 / #7057 | `auto_memoize` + `react_compiler`; foreach per-item hooks; lazy libs load per component; mapping sampling perf | hooks in foreach in memo; compiler + client_state; dev vs prod |
| #7564 / #7707 / #7691 | reproducible prod builds; f-string ref ids stable | export twice → identical; ids in foreach |
| #7409 / #7721 | upload from toast/call_script callbacks; repeated upload updates | upload + middleware (#7782) + awaited handler |
| #7641 | prod CORS default: none unless `deploy_url` / `cors_allowed_origins`; `deploy_url` default None; `Config.frontend_url` | split-origin prod, enterprise REST/MCP, uploads, sitemap |
| #7624 | ASGI lifespan forwarded to `api_transformer` apps; `rx.App()()` returns plain ASGI app (no Starlette wrapper) | FastAPI lifespan + `register_lifespan_task`; enterprise plugins; code expecting Starlette |
| #7599 / #7522 / #7621 / #7653 | case-insensitive backend routes; hydration uses current route; oversized polling body; `reflex:state-mismatch` event | dynamic routes + case; navigation during connect |
| #7650 / #7693 | `reflex run` shutdown ownership; `--frontend-only/--backend-only` with config ports; `supervise_output` moved | signals, `--json`; downstream imports |
| #7672 / #7746 | dev event-loop blocking monitor | sync sleep in async handler; noise in normal apps |
| #7668 / #7635 | trace ids in JSON logs; otel + reflex-workflow | `REFLEX_LOG_JSON` + otel |
| #7716 / #7753 / #7750 / #7674 / #7747 | callout icon component; code_block "text"; rx.match typing; lucide digit icons; input clear_events typing | lucide fix needs lucide 1.1.2a1 (floor is 1.1.1) |
| #7789 / #7784 | form `id` submission removal postponed to 0.12; sibling floors | deprecation messages say 0.12 |
| #7670 | `reflex cloud config` exits 1 without PyYAML | |

PR intent surveys (planning agents; verify against the tag): `$SB/notes/pr_survey_runtime.md`, `$SB/notes/pr_survey_vars_db.md`.

## Findings to re-verify
See `$SB/notes/registry_summary.md` (digest of `prerelease-testing/REGISTRY.md`). Each cluster brief names the registry
items in its area. Known and filed items: do NOT re-report unless changed.

## Items and ports
| item | covers | model | ports (fe / be) |
|---|---|---|---|
| preflight (orchestrator) | publish, wheel sources, `.pyi` audit, sdist rebuild, blank smoke | — | 3050-3059 / 8050-8059 |
| 0 `db_upgrade` | reflex-examples DB apps 0.10.1 → 0.11.0a1 in place, legacy env.py → new template, alembic CLI | opus high | 3100-3119 / 8100-8119 |
| 1 `db_models` | MappedAsDataclass/DeclarativeBase rewrite of rx.Model apps, serializer, asession, AdminDash | opus high | 3140-3159 / 8140-8159 |
| 2 `events_await` | @rx.event / awaitable handlers / middleware / failed-handler writes | opus high | 3180-3199 / 8180-8199 |
| 3 `redis_runtime` | redis locks, redis-py 8, bg-task cancellation, hot reload, spawn | opus high | 3220-3239 / 8220-8239 |
| 4 `client_vars` | client_state, storage vars, SetVar, var errors, unicode | opus high | 3260-3279 / 8260-8279 |
| 5 `compile_memo` | auto_memoize, react_compiler, foreach hooks, lazy libs, reproducible builds, uploads, components | opus high | 3300-3319 / 8300-8319 |
| 6 `server_net` | CORS, lifespan/api_transformer, routes, hydration, CLI shutdown/ports, blocking monitor, otel | opus high | 3340-3359 / 8340-8359 |
| 7 `enterprise` | reflex-enterprise 0.9.11 on 0.11.0a1 vs 0.10.1 | opus high | 3380-3399 / 8380-8399 |
| 8 `examples_ui` | non-DB reflex-examples in-place upgrade (storage, stacked decorators, ClientStateVar, upload, hotkey) | opus high | 3420-3439 / 8420-8439 |
| verifier *i.j* | per the port map | opus high | `3600+40i+4j`..+3 / `8600+40i+4j`..+3 |

## Environment
- `SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`; venvs `new`, `prev`, `driver`,
  `new-ent`, `prev-ent`. 4 CPU / 15 GB RAM: at most ~3 agents, 2 with dev servers. Python 3.12 venvs (3.11–3.15 available).
- node 22.23, bun 1.4.4, Chromium `/opt/pw-browsers/chromium`, redis-server in PATH.
- reflex-examples @ `ebe19ff00dfe` in `$SB/downloads/reflex-examples` (read-only; copy apps out).
- Artifacts: `prerelease-testing/runs/2026-11-11-v0.11.0a1/<item>/` on branch `claude/vibrant-pasteur-3921g3`
  (auto-committed every 10 min by `$SB/autocommit.sh`; stop with `touch $SB/STOP_AUTOCOMMIT`).

## Progress (orchestrator keeps this current — read it to resume)
| item | status | report |
|---|---|---|
| preflight | done (see `preflight/NOTES.md`) | |
| 1 db_models | DONE + verified (5/5 reproduce; 3 narrowed, 1 reclassified upstream; 0 regressions) | `reports/db_models.md`, `reports/verify_dbm.md` |
| 0 db_upgrade | DONE + verified: I-1 hand-edited env.py executed/crash NARROWED to medium regression; I-2 empty revisions CONFIRMED wider (medium regression); I-3 env.old overwrite low |
| 7 enterprise | explore DONE (3 rxe regressions: MCP prod crash w/o deploy_url HIGH, MCP consent redirect dev, AG Grid `refs` ReferenceError HIGH; 1 reflex regression: db migrate on fresh rxe app); DONE + verified: rxe #1 MCP prod crash CONFIRMED high, #2 consent redirect CONFIRMED medium, #3 AG Grid `refs` CONFIRMED high (rxe fix + optional reflex one-line shim), #4 reflex `db migrate` NARROWED medium-low | `reports/enterprise.md`, `reports/verify_ent.md` |
| 2 events_await | explore DONE (HIGH regression: double @rx.event crashes at import, overkey; medium regression: pyright Unknown args on py3.11-3.13; +5 low); verified: #1 CONFIRMED (trivial fix), #2 CONFIRMED, #3 CONFIRMED cross-caller read, #4 RECLASSIFIED (diagnostics), #5 NARROWED | `reports/events_await.md`, `reports/verify_evt.md` |
| 3 redis_runtime | explore DONE (0 regressions; medium: cross-worker updates lost after >5 s Redis outage, kill -9 of a worker stops server; low: oplock same-instance waiter 1 s stall contradicts #7534 text); verifier `verify_rds` running | `reports/redis_runtime.md` |
| 6 server_net | DONE + verified: #1 CORS CONFIRMED WIDER → HIGH (TLS-proxied same-origin prod + all documented split/CDN guides); #2/#3 NARROWED; #4/#5 CONFIRMED low | `reports/server_net.md`, `reports/verify_net.md` |
| 4 client_vars | explore DONE (high = dup of FINDING-001; 9 low non-regressions; HYD-08/09/12/13 fixed); verifier `verify_cv` running | `reports/client_vars.md` |
| 5 compile_memo | explore running (opus high; also checks reflex's own `refs` surface after the rxe ReferenceError) | `reports/compile_memo.md` |
| 8 examples_ui | DONE (no new regressions; overkey = FINDING-001; 2 low verified inline: FINDING-028/-029) | `reports/examples_ui.md` |

To resume an interrupted cluster: read its `NOTES.md` "Status / resume here", reuse its venvs under `$SB/envs/<cluster>-*`, and
continue; a cluster whose `reports/<item>.md` exists is finished. Each finished cluster's issues go to a verifier
(`verify_<short>`), which appends `## VERIFICATION` to the cluster NOTES.md.
