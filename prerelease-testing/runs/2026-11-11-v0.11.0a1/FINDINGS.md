# Findings — reflex 0.11.0a1 pre-release testing (2026-11-11) — DRAFT

**Status: DRAFT, in progress.** Clusters done and verified: `db_models`, `db_upgrade`, `enterprise`. Done, verification
running: `events_await`. Still exploring: `redis_runtime`, `server_net`, `client_vars`, `compile_memo`, `examples_ui`.
Findings marked *(unverified)* have not yet been through an independent verifier. Numbering is provisional; the final
pass re-ranks by severity.

Method: every package installed from PyPI into isolated venvs (never from the checkout); real apps run end-to-end in
Chromium (dev and prod, memory and Redis state managers), every behaviour baselined against reflex 0.10.1; every claimed
issue reproduced by an independent adversarial verifier from the written repro alone. Agents: 4 planning (haiku/sonnet),
9 exploration + 1 verifier per finished cluster (opus / fable, high effort).

## Versions under test
- reflex 0.11.0a1, reflex-base 0.11.0a1, reflex-components-core / -radix / -code 0.11.0a1, reflex-components-lucide
  1.1.2a1, reflex-hosting-cli 0.2.2a1, reflex-otel 0.2.1a1, reflex-release 0.2.2a1 (new in this train); all other train
  packages unchanged on 0.10.x. 20/20 published (wheel + sdist). Tag `v0.11.0a1` on `r/pre-2026.11.10-42931773407`.
- reflex-enterprise 0.9.11 (PyPI); source `reflex-dev/reflex-enterprise` @ `v0.9.11` for upstream demos.
- Baseline: reflex 0.10.1 with every sibling held to its release time.
- Environment: Linux, 4 CPU / 15 GB, Python 3.12 (3.11 / 3.14 where stated), node 22.23, bun 1.4.4, Chromium (Playwright),
  redis-server; sqlalchemy 2.1.8, sqlmodel 0.0.48, alembic 1.20.1, pydantic 2.14.3; redis-py 8.2.0b1 (`uv --prerelease=allow`)
  / 8.1.0 (stock pip) on 0.11, 7.4.1 on 0.10.1.

## Executive summary (so far)
Works: in-place upgrade of reflex-examples DB apps with existing migrations to the new alembic `env.py` (both orders,
no data loss, no spurious revisions, alembic CLI incl. downgrade/upgrade); rewrite of rx.Model apps to
`MappedAsDataclass` + `DeclarativeBase` with async sessions on the same tables and migration history; the new
DeclarativeBase serializer (dev, prod + Redis, hot reload); awaitable event handlers across 64 scenarios × {dev, prod} ×
{memory, Redis}; middleware gating of awaited handlers; failed/cancelled-handler write fixes (#7696/#7412/#7738);
reflex-enterprise OIDC, demos, REST/WS parity, Redis, lifespan; packaging (.pyi audit, wheel = tag, sdist rebuilds).

Blocks (candidates, see RELEASE_PLAN.md): FINDING-001 (double `@rx.event` crashes import, breaks reflex-examples
`overkey`), FINDING-002 / -003 (reflex-enterprise 0.9.11 breaks on 0.11: MCP prod startup, AG Grid API), FINDING-004
(unregistered DeclarativeBase silently drops every table — not a regression but the docs now steer everyone there),
FINDING-005 / -006 (kept hand-edited env.py).

Index:
- FINDING-001: A second `@rx.event` on a handler crashes the app at import (HIGH, regression) *(verification running)*
- FINDING-002: [reflex-enterprise] MCPPlugin app dies at prod startup when `deploy_url` is unset (HIGH, regression)
- FINDING-003: [reflex-enterprise / reflex compat] AG Grid API calls throw `ReferenceError: refs is not defined` (HIGH, regression)
- FINDING-004: Unregistered DeclarativeBase → `makemigrations` silently generates `drop_table` for every table (HIGH, not a regression)
- FINDING-005: Hand-edited 0.10.x `env.py` is now executed; placeholder URL crashes `reflex run` / `reflex db` (MEDIUM, regression)
- FINDING-006: Kept user `env.py` → every `makemigrations` writes an empty revision (MEDIUM, regression)
- FINDING-007: pyright on Python 3.11–3.13 loses the argument types of bare-`@rx.event` handlers (MEDIUM, regression) *(verification running)*
- FINDING-008: [reflex-enterprise] MCP OAuth consent redirect points at the backend in dev (404) (MEDIUM, regression)
- FINDING-009: `reflex db migrate` exits 1 on a fresh reflex-enterprise app (MEDIUM-LOW, regression for `migrate` only)
- FINDING-010: `await State.handler()` outside an event handler / `modify_state` runs on a shared empty-token session (MEDIUM) *(verification running)*
- FINDING-011: JSON column on a DeclarativeBase model is typed `object`; item access is a compile error (MEDIUM)
- FINDING-012: `mapped_column(default_factory=...)` added to a non-empty table → NOT NULL migration failure (MEDIUM)
- FINDING-013: Same table in two registered metadatas → compared definition random per process (LOW)
- FINDING-014: Admin-dashboard guide gaps: `/admin` 404 without slash; create fails for dataclass models (upstream) (LOW, docs)
- FINDING-015: Clicked handler returning a non-event value is now silently accepted (LOW, regression) *(verification running)*
- FINDING-016: `@staticmethod` above `@rx.event` returns an `EventSpec` instead of the result (LOW, regression) *(verification running)*
- FINDING-017: A second legacy `env.py` replacement silently overwrites `env.old` (LOW)
- FINDING-018: Serializer silent blanks: `hybrid_property` never sent; expired objects sent as `{}` (LOW)
- FINDING-019: Merged registry metadata drops the Base `naming_convention` for UniqueConstraint (LOW)
- FINDING-020: tables.md custom serializer example breaks for models with relationships (LOW, docs)
- FINDING-021: [reflex-enterprise] `use_single_port=True` dev proxy never mounts (LOW, not a regression)
- PKG-A (maintainer decision): reflex 0.11.0a1 requires only `reflex-components-lucide>=1.1.1` and `reflex-hosting-cli>=0.2.1`

---

## FINDING-001: A second `@rx.event` on a handler crashes the app at import (HIGH)
- Cluster: `events_await` | Regression vs 0.10.1: yes | Verifier: running (`reports/verify_evt.md`)
- Repro: `cd $SB && $SB/envs/new/bin/python -I events_await/probes/deco_matrix.py` (copy of
  `runs/2026-11-11-v0.11.0a1/events_await/probes/deco_matrix.py`); same with `envs/prev`: all 18 patterns create the
  class. Real app: copy reflex-examples `overkey` (@ebe19ff) and `python -c "import overkey.overkey"`.
  Minimal: a state method with `@rx.event` directly above `@rx.event(background=True)`.
- Evidence: `@rx.event`/`@rx.event`, `@rx.event`/`@rx.event(background=True)` (overkey/overkey.py:164),
  `@rx.event`/`@rx.event(throttle=300)` → `AttributeError: 'EventHandler' object has no attribute '__qualname__'`
  (reflex_base/utils/format.py:448); `@rx.event(background=True)`/`@rx.event` → `TypeError: Background task must be async
  function or generator.`; `@rx.event(throttle=300)`/`@rx.event` → `FrozenInstanceError`. Changelog: a decorator stacked
  above `@rx.event` "still runs and registers under its own name, with a deprecation warning, until 1.0".
  `events_await/evidence/deco_matrix_{new,prev}.txt`, `evidence/overkey_import.txt`.

## FINDING-002: [reflex-enterprise] MCPPlugin app dies at `reflex run --env prod` startup when `deploy_url` is unset (HIGH)
- Cluster: `enterprise` | Regression vs 0.10.1: yes | Verifier: CONFIRMED (0.10.1 only worked on localhost)
- Repro: `enterprise/scripts/repro_mcp_prod.sh new-ent token|stub` — app `enterprise/src/mcpmin`
  (`rxe.Config(plugins=[rxe.MCPPlugin()])`, one page), `reflex run --env prod` single port, CI=true. Compare prev-ent, and
  new-ent with `REFLEX_DEPLOY_URL=http://localhost:<port>` (workaround). Setting only `REFLEX_API_URL` does not help.
- Evidence: every worker: `ConfigError: MCP OAuth needs the app's public origin for the RFC 8414 issuer, but neither
  MCPPlugin(issuer_url=...) nor the config's deploy_url/api_url is set` (`enterprise/logs/new_prod_default_ConfigError.txt`).
- Root cause: rxe `resolve_server_url()` (`plugins/event_handler_api.py`) returns `config.deploy_url` whenever the frontend
  is mounted in the backend (always in prod); #7641 made the default `None`. 0.10.1 derived `http://localhost:<port>` and
  silently advertised a localhost issuer even for real deployments.
- Fix shape: rxe — `deploy_url or api_url`, fix the error text. reflex — add a CHANGELOG breaking-change line for code
  that reads `config.deploy_url` (point to `frontend_url`); coordinate the 0.11.0 final with a fixed rxe (rxe requires
  `reflex[db]>=0.9.6` with no upper bound).

## FINDING-003: [reflex-enterprise / reflex compat] AG Grid API calls throw `ReferenceError: refs is not defined` (HIGH)
- Cluster: `enterprise` | Regression vs 0.10.1: yes | Verifier: CONFIRMED (latent rxe bug, widened by 0.11)
- Repro: `XC_SRC=$SB/apps/enterprise/src/agapi ACCT=token enterprise/scripts/xc.sh start new-ent prod agapi_new`, then
  `python -I enterprise/scripts/agapi_drv.py http://localhost:8380 new`; repeat with prev-ent. Upstream demo
  `demos/ag_grid` features drop from 46/47 (prev) to 39/48 (new); `aligned_grids` breaks too.
- Root cause: rxe `aggrid.py:253` / `:902` build `refs['ref_<id>']` with no `refs` import. In 0.10.1,
  `Component._get_hooks_imports` (reflex-base `component.py:1833-1838`) imported `refs` into every module with an
  `id`'d component; #7694 now imports only `useRegisteredRef`. `$/utils/state` still exports `refs` (state.js:66).
  Reflex's own `refs[...]` uses all carry their import; third-party libraries that hand-write `refs[...]` would break.
- Fix shape: rxe — attach `refs` var data / `Var._as_ref()`. reflex (recommended) — re-add `ImportVar(tag="refs")`
  next to `useRegisteredRef` for the 0.11 line (one line); otherwise list it under Breaking Changes.

## FINDING-004: Unregistered DeclarativeBase → `makemigrations` silently generates `drop_table` for every table (HIGH)
- Cluster: `db_models` | Regression vs 0.10.1: no | Verifier: CONFIRMED (also in mixed apps; fresh `db init` creates nothing silently)
- Repro: `verify_dbm/v1_noregister.sh` (builds from nothing), `verify_dbm/v1b_noregister_mixed.sh`. A DeclarativeBase
  app without `rx.ModelRegistry.register(Base)`: `reflex db makemigrations` rc 0, no warning, revision drops every table;
  `reflex db migrate` rc 0 leaves only `alembic_version`. With an extra rx.Model table, only the Base tables are dropped.
- Root cause: `reflex/model.py:258-272` `get_metadata()` returns an empty `MetaData()`; `reflex/.templates/alembic/env.py:59`
  passes it as `target_metadata`, bypassing alembic's own refusal (which only triggers for `None`).
- Why it matters now: rx.Model needed no registration; the 0.11 docs move every user to DeclarativeBase, where one missing
  line causes total data loss. Fix shape: refuse autogenerate when target metadata lacks tables present in the DB (or is
  empty), and warn about DeclarativeBase subclasses whose metadata is not registered.

## FINDING-005: Hand-edited 0.10.x `env.py` is now executed; the placeholder URL crashes `reflex run` / `reflex db` (MEDIUM)
- Cluster: `db_upgrade` | Regression vs 0.10.1: yes | Verifier: NARROWED from HIGH (trigger is a half-finished edit)
- Repro: reflex-examples form-designer or chat_v2 @ ebe19ff on reflex[db]==0.10.1; edit only `target_metadata = None` →
  `from sqlmodel import SQLModel` / `target_metadata = SQLModel.metadata`, leave alembic.ini's `driver://` URL. 0.10.1:
  `reflex db migrate` and `reflex run` work. Upgrade in place to 0.11.0a1: `reflex run` dies in 3–6 s with
  `sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:driver`; `reflex db status/migrate/makemigrations`
  exit 1 with a raw traceback; `reflex db init` only says "Database is already initialized". Scripts:
  `verify_dbu/scripts/run_all.sh`; `db_upgrade/combo/fd-H1-env.py`.
- Root cause: `reflex/utils/migrations.py:188` detects "legacy" only by the literal `target_metadata = None` (0.10.x never
  executed env.py at all); `prerequisites.py:878-888` `check_schema_up_to_date` and `reflex.py:1113-1131`
  `_alembic_errors` catch only `CommandError`; `model.py:432-434` import-time `migrate()` runs the same file.
- Real-world exposure: five public Reflex apps with hand-edited env.py found (incl. reflex-dev's reflex-railway template);
  all set a working URL, so none crash, but any exception from a kept env.py (import error, missing env var) would.
- Fix shape: catch any exception from env.py in both places and log the "move env.py aside, run `reflex db init`" hint;
  optionally treat an env.py without the template hooks as foreign (warn once).

## FINDING-006: Kept user `env.py` → every `reflex db makemigrations` writes an empty `pass` revision (MEDIUM)
- Cluster: `db_upgrade` | Regression vs 0.10.1: yes | Verifier: CONFIRMED, wider than reported
- Repro: as FINDING-005 plus a working `sqlalchemy.url`: two `makemigrations` calls write two empty revisions on 0.11,
  none on 0.10.1. An env.py modeled on reflex-railway (all five public apps above) does the same. With
  `rx.model.migrate(autogenerate=True)` at import, one dev `reflex run` start writes three chained empty revisions.
- Root cause: `makemigrations` (`reflex.py` ~1228) and `migrate(autogenerate=True)` (`model.py:435-437`) run a bare
  `alembic revision --autogenerate`; the empty-revision skip lives only in the template env.py.
- Fix shape: run `alembic check` first and write a revision only when it reports changes (as 0.10.1 and the deprecated
  `alembic_autogenerate` do); CHANGELOG note (docs/database/overview.md mentions it, the changelog does not).

## FINDING-007: pyright on Python 3.11–3.13 loses the argument types of every bare-`@rx.event` handler (MEDIUM)
- Cluster: `events_await` | Regression vs 0.10.1: yes | Verifier: running
- Repro: `events_await/typing/run_typing.sh new reveal2.py` vs `prev`; `strict_app.py` (`# pyright: strict`) goes from 4
  to 18 errors on an unchanged app. pyright 1.1.414 / 1.1.411, Python 3.12.
- Evidence: 0.10.1 `S.via_rx` is `EventCallback[int]`; 0.11.0a1 `EventCallback[*tuple[Unknown, ...]]`, wrong-type calls
  not reported. `@rx.event()` with parentheses unaffected; mypy correct; `--pythonversion 3.14` correct (why CI passes).
- Root cause (reporter, confirmed on a scratch copy): `EventCallback: TypeAlias = EventCallback` inside
  `class EventNamespace` (reflex_base/event/__init__.py:3502, #7715) shadows the name in the `__new__` overload's return
  annotation.

## FINDING-008: [reflex-enterprise] MCP OAuth consent redirect points at the backend origin in dev (404) (MEDIUM)
- Cluster: `enterprise` | Regression vs 0.10.1: yes | Verifier: CONFIRMED
- Repro: a4auth `auth_min` app in dev (frontend 3393, backend 8393, mock IdP);
  `python -I enterprise/scripts/mcp_consent_probe.py http://localhost:8393` → `/authorize` 302 to
  `http://localhost:8393/agent-consent` (404); prev → `:3393` (200); new with `REFLEX_DEPLOY_URL` → OK.
- Root cause: rxe `mcp.py:1535` `_resolve_consent_url` uses `config.deploy_url or issuer_url`. Fix in rxe:
  `deploy_url` → `frontend_url` (split ports) → `issuer_url` (single port).

## FINDING-009: `reflex db migrate` exits 1 on a fresh reflex-enterprise app ("Library @radix-ui/themes is not bundled") (MEDIUM-LOW)
- Cluster: `enterprise` | Regression vs 0.10.1: yes for `db migrate` only (`db init` / `makemigrations` / backend-only
  start already failed on 0.10.1) | Verifier: NARROWED; no repro without rxe
- Repro: copy `reflex-enterprise/demos/ag_grid`, `rm -rf reflex.db .web`,
  `CI=true REFLEX_DB_URL=sqlite:///reflex.db reflex db migrate` → rc 1 after the migration ran; 0.10.1 rc 0;
  `reflex compile` first → rc 0. Workaround: `bundle_library("@radix-ui/themes")` at app import.
- Root cause: `reflex/compiler/compiler.py:1278-1292` skip-compile/dry-run branch — `_restore_bundled_libraries()`
  (`compiler/utils.py:302`) only reads `.web`; `_compile_initial_state` then runs without plugin-dependency bundling. New
  trigger: `reflex/reflex.py:1200` `migrations.evaluate_pages()` in `migrate` (#7742). rxe's strict check (`vars.py:166`) raises.
- Fix shape: don't compile the initial state in `evaluate_pages`, or bundle plugin frontend deps in the skip branch.

## FINDING-010: `await State.handler()` outside an event handler / `app.modify_state` runs on a shared empty-token session (MEDIUM)
- Cluster: `events_await` | Regression vs 0.10.1: no (new feature) | Verifier: running
- Repro: `events_await/scripts/srv.sh start new $SB/apps/events_await/awaitapp dev 3180 8180 t`;
  `for i in 1 2 3; do curl -s --noproxy '*' localhost:8180/poke/any-$i; done` (route `poke` does
  `res["outside"] = await Main.add(1)` after its `modify_state` block).
- Evidence: "outside" returns 1, 2, 3, 4 across requests with different tokens (also across workers on prod + Redis);
  log `Warning: Attempting to send delta to disconnected client ''`; Redis keys `_reflex___state____state...`.
  docs/events/chaining_events.md: "awaiting a handler anywhere else raises an error."

## FINDING-011: JSON column on a DeclarativeBase model is typed `object`; item access is a compile TypeError (MEDIUM)
- Cluster: `db_models` | Regression vs 0.10.1: no | Verifier: CONFIRMED, broader (`Mapped[list[str]]`, plain DeclarativeBase)
- Repro: `verify_dbm/v2_json_types.py`. `d: Mapped[dict] = mapped_column(JSON)` in a state var → `S.m.d["city"]` →
  `TypeError: Var of type <class 'object'> does not support item access.` rx.Model equivalent typed `dict`; `.to(dict)` works around.
- Root cause: `packages/reflex-base/src/reflex_base/utils/types.py:1079-1098` returns the column's `python_type` without
  falling back to the `Mapped[]` annotation.

## FINDING-012: `mapped_column(default_factory=...)` added to a non-empty table → NOT NULL migration failure (MEDIUM)
- Cluster: `db_models` | Regression vs 0.10.1: no (but the documented rewrite of a working rx.Model `Field(default_factory=)`
  breaks) | Verifier: CONFIRMED, NARROWED
- Repro: `verify_dbm/v3_default_factory.sh`. Base model with one row, add
  `score: Mapped[int] = mapped_column(default_factory=lambda: 7)`; `makemigrations` → `add_column(... nullable=False)` with no
  server_default; `migrate` rc 1; when the revision rebuilds the table, sqlite batch mode leaves `_alembic_tmp_*` and the
  next migrate fails. `default=` / `insert_default=` work.
- Root cause: `reflex/.templates/alembic/env.py:82-86` reads only `op.column.default`.

## FINDING-013: Same table in two registered metadatas → compared definition random per process (LOW)
- Cluster: `db_models` | Regression: no | Verifier: CONFIRMED, NARROWED (an `SAWarning` is printed every run)
- Repro: `verify_dbm/v4_dup_table.sh`; `alembic check` 3/10 clean, 7/10 add_column.
- Root cause: `reflex/model.py:204` registry is a `set`; `model.py:267-269` keeps the first copy.

## FINDING-014: Admin-dashboard guide gaps (LOW, docs)
- Cluster: `db_models` | Regression: only vs the removed `rx.AdminDash` | Verifier: 5a RECLASSIFIED upstream, 5b NARROWED to docs
- `/admin` (no slash) → 404 through `api_transformer` on 0.10.1 and 0.11 (`reflex/app.py:1000`
  `api_transformer.mount("", asgi_app)`); rx.AdminDash redirected 307; the guide says "existing links keep working".
- "New <Model>" → 500 `TypeError: __init__() missing ... 'name'` for MappedAsDataclass models: starlette-admin
  `contrib/sqla/view.py:581/588` calls `self.model()`; same on 0.10.1's rx.AdminDash. The guide's example uses SQLModel and
  never defines `MyAuthProvider`. Repro: `verify_dbm/v5_admin.sh`.

## FINDING-015: A clicked handler returning a non-event value is now silently accepted (LOW)
- Cluster: `events_await` | Regression: yes | Verifier: running
- Repro: legacyapp `/fail`, buttons ret_value / ret_garbage / ret_self_handler
  (`events_await/scripts/drive_legacy.py`). 0.10.1 logs `TypeError: Your handler ... must only return/yield: None, Events
  or other EventHandlers ...`; 0.11.0a1 logs nothing and `chained` never runs.

## FINDING-016: `@staticmethod` above `@rx.event` returns an `EventSpec` instead of the result (LOW)
- Cluster: `events_await` | Regression: yes | Verifier: running
- Repro: legacyapp `D.static_over(3)`: 0.10.1 `6`, 0.11.0a1 `EventSpec(...)`, no warning
  (`events_await/evidence/deco_page_new_vs_prev.txt`).

## FINDING-017: A second legacy `env.py` replacement silently overwrites `env.old` (LOW)
- Cluster: `db_upgrade` | Regression: no (new code path) | Verifier: CONFIRMED
- Root cause: `reflex/utils/migrations.py:200-201` `env_py.replace(backup)`. Fix: free name or warn.

## FINDING-018: Serializer silent blanks (LOW)
- Cluster: `db_models` | Regression: no (0.10.1 raised for expired objects) | Not separately verified
- `hybrid_property` typed str compiles and is never serialized (blank) while `@property` now raises; with the default
  `expire_on_commit=True` an object stored after commit serializes as `{}`, UI blank, no log. Repro: `db_models/apps/ser`
  + `db_models/scripts/drive_ser.py`.

## FINDING-019: Merged registry metadata drops the Base `naming_convention` for UniqueConstraint (LOW)
- Cluster: `db_models` | Regression: no | Not separately verified. Repro: `db_models/repros/variant.sh db_models-up mixed ...`.

## FINDING-020: tables.md custom serializer example breaks for models with relationships (LOW, docs)
- Cluster: `db_models` | Regression: no | `db_models/probes/probe_legacy_ser.py`: DetachedInstanceError / RecursionError.

## FINDING-021: [reflex-enterprise] `rxe.Config(use_single_port=True)` dev proxy never mounts (LOW)
- Cluster: `enterprise` | Regression: no (both versions) | `XC_SINGLE=1 enterprise/scripts/xc.sh start <venv> dev l` →
  `curl localhost:8380/` 404; "Unable to find the base Starlette app".

## PKG-A: sibling floors (maintainer decision)
reflex 0.11.0a1 requires `reflex-components-lucide>=1.1.1` and `reflex-hosting-cli>=0.2.1`. A stock `pip install
reflex==0.11.0a1` resolves lucide 1.1.1 and hosting-cli 0.2.1 (without the #7674 / #7670 fixes); `uv pip install -U`
moves them. Stock pip resolves redis 8.1.0; `uv --prerelease=allow` resolves the redis-py beta 8.2.0b1.

## Refuted / reclassified claims
- **Admin "New" 500 for dataclass models** (`db_models`): upstream starlette-admin limitation; identical on 0.10.1 rx.AdminDash → docs gap (FINDING-014).
- **`db init` / `makemigrations` regression on fresh rxe app** (`enterprise`): already failing on 0.10.1; only `db migrate` regressed (FINDING-009).
- **Hand-edited env.py HIGH** (`db_upgrade`): narrowed to MEDIUM (half-finished edit; no docs told users to edit env.py).
- **Uploads newly gated by middleware** (planning note): not confirmed — gated on 0.10.1 too (`events_await`).
- **stale `deprecation_version="0.10.2"`** (planning note): shipped wheel says 0.11.0.

## Re-verification table
| registry id | what | result | cluster |
|---|---|---|---|
| ENT-29 | prod AG Grid state-valued column_defs | fixed (4/4 prod+dev, entv s1-s13) | enterprise |
| ENT-16 / DOC-14 | no client_token/session_id/cookie leaks | fixed | enterprise |
| ENT-01 / ENT-02 / CLI-03 | deprecated names still work | fixed (same as 0.10.1) | enterprise |
| ENT-30 (N-032) | OIDC cross-tab logout | fixed | enterprise |
| R101-07 | rxe REST leftmost XFF | fixed | enterprise |
| ENT-07 | prod cookie sync 405 with 2 workers | still broken | enterprise |
| N-028 | mantine page error | changed (0 page errors) | enterprise |
| EVT-15 (#7476) | mutate-then-raise delta | fixed (33 ms vs next event on 0.10.1) | events_await |
| EVT-08 (#7248) | Redis superseded handler partial writes | fixed | events_await |
| EVT-16 | Redis server view after failed event | fixed | events_await |
| EVT-17 (#6122) | superseded handler writes flushed | changed (own delta at cancel time) | events_await |
| EVT-13 | 5-8 arg handler typing | changed (mypy OK; pyright 3.11-3.13 see FINDING-007) | events_await |
| DOC-06 | async_db_url docs | changed (documented; `rx.asession()` without it raises clearly) | db_models |
| PKG-15 | rx.Model deprecation warning location | still broken (points at pydantic internals) | db_models |
| TP-05 | form-designer /login no auto-redirect | still broken (both versions) | db_upgrade |
| TP-07 | basic_crud / twitter ship no alembic dir | unchanged | db_upgrade |

## Cluster summaries
### `db_upgrade` (pass:20, anomaly:6, fail:1)
form-designer, chat_v2 (LLM stubbed), basic_crud, twitter built and driven on 0.10.1, upgraded in place; env.py → template,
env.old byte-identical, no data loss, no spurious revision, alembic CLI incl. downgrade; dev/prod/cold match. Lazily
imported model fix verified. Issues: FINDING-005/-006/-017.
### `db_models` (pass:17, anomaly:6, fail:6)
rx.Model blog app on 0.10.1 → 0.11 → MappedAsDataclass rewrite on the same tables, no revision; serializer e2e in dev,
prod + Redis, hot reload; AdminDash error; deprecated helpers. Issues: FINDING-004, -011 … -014, -018 … -020.
### `enterprise` (pass:14, anomaly:4, fail:2)
rxe 0.9.11 imports clean; OIDC 36/36 + N-032 + deeplink; demos dnd/flow/mantine/map/highcharts/tickets; awaited protected
handlers; REST/WS parity; Redis; lifespan; CORS. Issues: FINDING-002/-003/-008/-009/-021.
### `events_await` (pass:15, anomaly:7, fail:3)
64 await scenarios × dev/prod × memory/Redis; middleware; failure paths; decorators; typing. Issues: FINDING-001/-007/-010/-015/-016, plus low: memory-manager `CancelledError` for a background task awaiting a superseded handler; background task that catches an awaited exception still shows the error toast; deprecation names only the first stacked method per class.
