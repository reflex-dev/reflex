# Findings — reflex 0.11.0a1 pre-release testing (2026-11-11) — DRAFT

**Status: DRAFT, in progress.** Clusters done and verified: `db_models`, `db_upgrade`, `enterprise`. `events_await` verified. `server_net`, `redis_runtime` verified. `compile_memo` done (verification running). `client_vars` (verified) and `examples_ui` done.
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

Blocks (candidates, see RELEASE_PLAN.md): FINDING-022 (new prod CORS default: TLS-proxied same-origin prod and every documented split/CDN deployment never connect), FINDING-001 (double `@rx.event` crashes import, breaks reflex-examples
`overkey`), FINDING-002 / -003 (reflex-enterprise 0.9.11 breaks on 0.11: MCP prod startup, AG Grid API), FINDING-004
(unregistered DeclarativeBase silently drops every table — not a regression but the docs now steer everyone there),
FINDING-005 / -006 (kept hand-edited env.py).

Index:
- FINDING-001: A second `@rx.event` on a handler crashes the app at import (HIGH, regression)
- FINDING-002: [reflex-enterprise] MCPPlugin app dies at prod startup when `deploy_url` is unset (HIGH, regression)
- FINDING-003: Page code reading `refs[...]` throws `ReferenceError: refs is not defined` (raw Var handlers, `rx.call_function`, custom `add_hooks`; reflex-enterprise AG Grid API) (HIGH, regression) *(reflex-side widening: verification running)*
- FINDING-004: Unregistered DeclarativeBase → `makemigrations` silently generates `drop_table` for every table (HIGH, not a regression)
- FINDING-005: Hand-edited 0.10.x `env.py` is now executed; placeholder URL crashes `reflex run` / `reflex db` (MEDIUM, regression)
- FINDING-006: Kept user `env.py` → every `makemigrations` writes an empty revision (MEDIUM, regression)
- FINDING-007: pyright on Python 3.11–3.13 loses the argument types of bare-`@rx.event` handlers (MEDIUM, regression)
- FINDING-008: [reflex-enterprise] MCP OAuth consent redirect points at the backend in dev (404) (MEDIUM, regression)
- FINDING-009: `reflex db migrate` exits 1 on a fresh reflex-enterprise app (MEDIUM-LOW, regression for `migrate` only)
- FINDING-010: `await State.handler()` outside an event handler / `modify_state` runs on a shared empty-token session (MEDIUM)
- FINDING-011: JSON column on a DeclarativeBase model is typed `object`; item access is a compile error (MEDIUM)
- FINDING-012: `mapped_column(default_factory=...)` added to a non-empty table → NOT NULL migration failure (MEDIUM)
- FINDING-013: Same table in two registered metadatas → compared definition random per process (LOW)
- FINDING-014: Admin-dashboard guide gaps: `/admin` 404 without slash; create fails for dataclass models (upstream) (LOW, docs)
- FINDING-015: Clicked handler returning a non-event value is now silently accepted (LOW, regression)
- FINDING-016: `@staticmethod` above `@rx.event` returns an `EventSpec` instead of the result (LOW, regression)
- FINDING-017: A second legacy `env.py` replacement silently overwrites `env.old` (LOW)
- FINDING-018: Serializer silent blanks: `hybrid_property` never sent; expired objects sent as `{}` (LOW)
- FINDING-019: Merged registry metadata drops the Base `naming_convention` for UniqueConstraint (LOW)
- FINDING-020: tables.md custom serializer example breaks for models with relationships (LOW, docs)
- FINDING-021: [reflex-enterprise] `use_single_port=True` dev proxy never mounts (LOW, not a regression)
- FINDING-022: New prod CORS default breaks same-origin prod behind a TLS proxy and every documented split/CDN deployment (HIGH, regression)
- FINDING-023: CORS rejection is reported to the user as "server unreachable"; no hint at deploy_url / cors_allowed_origins (LOW)
- FINDING-024: `rx.App()()` no longer returns Starlette; listed only under Performance (LOW, changelog)
- FINDING-025: A middleware that fails on non-http scopes silently skips a FastAPI transformer's lifespan (LOW)
- FINDING-026: Routes differing only in case are accepted silently; one is unreachable (LOW, not a regression)
- FINDING-027: Prod `reflex run`: repeated Ctrl-C does not force exit while lifespan cleanup is stuck (LOW, not a regression)
- FINDING-028: Deprecation warnings for handlers passed as props point into `site-packages/reflex_components_*` (LOW)
- FINDING-029: First 0.11 run rewrites the committed `reflex.lock/package.json` as one-line JSON (LOW, cosmetic regression)
- FINDING-030: Forked prod workers share one `StateManagerRedis` instance id; oplock waiters passed over ~1 s; #7534 changelog claim false as written (LOW)
- FINDING-031: After a Redis outage > ~5 s, cross-worker updates to connected clients are silently dropped (MEDIUM, not a regression)
- FINDING-032: A dead worker's socket record makes the returning tab look like a duplicate → new token, session lost (MEDIUM, not a regression)
- FINDING-033: kill -9 of one granian worker stops the whole prod server; no respawn knob through `reflex run` (LOW-MEDIUM, not a regression)
- FINDING-034: `rx.client_state` "Give it a name" hint and docstring show a call that does not name the var (LOW)
- FINDING-035: client_state generated identifiers collide (case-only names; one name with two defaults) (LOW)
- FINDING-036: Operations on a None `set[...] | None` / `list[...] | None` var crash the page and fail the prod build (LOW, not a regression)
- FINDING-037: `print` / `str` / `%` / logging of a class-level backend var in server code now raises (LOW, regression by design; changelog gap)
- FINDING-038: Storage-compatible `default_factory` called extra times (once per compile + once per backend worker) (LOW, regression)
- FINDING-039: Unkeyed `rx.foreach` on_unmount / on_mount payloads name the item at that position, not the removed item (MEDIUM, new with #7793) *(verification running)*
- FINDING-040: on_mount / on_unmount inside `rx.cond` inside an `@rx.memo` body fire unconditionally; contradicts the #7694 changelog line (MEDIUM, not a regression) *(verification running)*
- FINDING-041: `rx.foreach` with item hooks inside `@rx.memo` crashes the whole page (documented "not covered yet") (MEDIUM, not a regression)
- FINDING-042: #7674 lucide digit-icon fix does not reach in-place upgraders (lucide floor 1.1.1) (MEDIUM, part of PKG-A) *(verification running)*
- FINDING-043: compile_memo lows: f-string ids in foreach all share one ref (set_focus targets the last row); blocking-monitor blames user handler for reflex's lazy sqlalchemy import; repeated auto_memoize warning; upload handler exception cuts the chunked response (LOW)
- PKG-A (maintainer decision): reflex 0.11.0a1 requires only `reflex-components-lucide>=1.1.1` and `reflex-hosting-cli>=0.2.1`

---

## FINDING-001: A second `@rx.event` on a handler crashes the app at import (HIGH)
- Cluster: `events_await` | Regression vs 0.10.1: yes | Verifier: CONFIRMED (6th pattern too: `@rx.event()` over `@rx.event`; overkey `reflex run` exits 1; rare in the wild — 1 hit in reflex-examples, none in docs or a 100-file GitHub sample)
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
- Root cause: `reflex_base/event/__init__.py:3641-3711` — `wrapper` has no case for an input that is already an
  `EventHandler` and builds `EventHandler(fn=EventHandler)` (3711); with options the background check (3652/3656) or the
  frozen-dataclass `setattr` (3669) fails first.
- Fix shape (verified on a scratch copy): `if isinstance(func, EventHandler): func = func.fn` at the top of `wrapper`,
  merging the existing `EVENT_ACTIONS_MARKER`; all six patterns register with the right background flag; overkey imports.

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

## FINDING-003: Page code reading `refs[...]` throws `ReferenceError: refs is not defined` (HIGH)
- WIDENED by `compile_memo` (verification `verify_cm` running): not only reflex-enterprise. On 0.11.0a1 (dev + prod, every
  auto_memoize × react_compiler cell) a raw `rx.Var("() => { refs['ref_target'].current.value = 'x' }").to(rx.vars.FunctionVar)`
  handler, `rx.call_function(rx.Var("() => refs['ref_target'].current.value"), callback=...)` and a custom component's
  `add_hooks` reading `refs[...]` all throw; 0.10.1 works. Repro app `compile_memo/refsrepro/`,
  `compile_memo/scripts/drive_refs.py`; compiled route imports only `{useRegisteredRef}` (0.10.1: `{refs}`). It can pass by
  accident when a memo wrapper shares a module with a form that imports refs. Reflex's own `rx.set_focus` / `set_value` /
  `scroll_to` / `call_script` and sonner are unaffected.
- reflex-enterprise part:
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
- Cluster: `events_await` | Regression vs 0.10.1: yes | Verifier: CONFIRMED (cause confirmed with patched + unpatched scratch copies)
- Repro: `events_await/typing/run_typing.sh new reveal2.py` vs `prev`; `strict_app.py` (`# pyright: strict`) goes from 4
  to 18 errors on an unchanged app. pyright 1.1.414 / 1.1.411, Python 3.12.
- Evidence: 0.10.1 `S.via_rx` is `EventCallback[int]`; 0.11.0a1 `EventCallback[*tuple[Unknown, ...]]`, wrong-type calls
  not reported. `@rx.event()` with parentheses unaffected; mypy correct; `--pythonversion 3.14` correct (why CI passes).
- Root cause (reporter, confirmed on a scratch copy): `EventCallback: TypeAlias = EventCallback` inside
  `class EventNamespace` (reflex_base/event/__init__.py:3502, #7715) shadows the name in the `__new__` overload's return
  annotation (line 3577).
- Side finding (low, regression): the annotation `rx.event.EventCallback[int]` is a pyright error ("already
  specialized") on every Python version incl. 3.14; 0.10.1 clean.
- Fix shape: point the overload's return annotation at a module-level alias; add a CI pyright run with
  `--pythonversion 3.12` (CI only exercises 3.14 semantics, which hides this).

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
- Cluster: `events_await` | Regression vs 0.10.1: no (new feature; 0.10.1 raised TypeError) | Verifier: CONFIRMED — a real
  cross-caller read between callers of a misusing route; browser sessions not exposed (a blank `?token=` socket is never
  linked: `parse_qs` drops blanks, `app.py:2381-2390`)
- Root cause: `reflex/app.py:390-391` `_RootMiddleware` attaches the event processor's root context (token `""`,
  `event_processor.py:218`) to every request; `execute_event_inline` (`base_state_processor.py:493-517`) only raises when
  no context exists. Fix shape: treat `not ctx.token` as no context and raise the existing `EventHandlerTypeError`.
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
- Cluster: `events_await` | Regression: diagnostics only | Verifier: RECLASSIFIED — deliberate (`base_state_processor.py:614-633`,
  unit test `test_handler_return_value_resolves_future`); the changelog allows return values but does not say the
  TypeError is gone or that `return self.handler` now does nothing. Fix shape: keep raising for values that can only be
  mistaken events (bound handler method, `rx.*` event creator); dev-mode warning when a frontend event's return value is
  dropped; changelog line.
- Repro: legacyapp `/fail`, buttons ret_value / ret_garbage / ret_self_handler
  (`events_await/scripts/drive_legacy.py`). 0.10.1 logs `TypeError: Your handler ... must only return/yield: None, Events
  or other EventHandlers ...`; 0.11.0a1 logs nothing and `chained` never runs.

## FINDING-016: `@staticmethod` above `@rx.event` returns an `EventSpec` instead of the result (LOW)
- Cluster: `events_await` | Regression: yes | Verifier: NARROWED — on a State class the generic "Decorators above @rx.event"
  warning does fire (wrongly implying the method still runs); on a non-state class none. Root cause `reflex/state.py:946-983`
  (staticmethod has no `__code__`, not converted back). Fix: re-wrap as `staticmethod(inner.fn)`.
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

## FINDING-022: New prod CORS default breaks same-origin prod behind a TLS proxy and every documented split/CDN deployment (HIGH)
- Cluster: `server_net` | Regression vs 0.10.1: yes | Verifier: CONFIRMED, WIDER (raised from MEDIUM)
- Repro (split, doc-literal, docs/hosting/self-hosting.md @ v0.11.0a1): `reflex run --env prod --backend-only --backend-port 8348`
  and `REFLEX_API_URL=http://localhost:8348 reflex run --env prod --frontend-only --frontend-port 3348`; open
  http://localhost:3348, click → websocket 403 forever, backend log `http://localhost:3348 is not an accepted origin.`
  0.10.1 works; setting `REFLEX_DEPLOY_URL` (or `REFLEX_CORS_ALLOWED_ORIGINS`) on the backend fixes it. Scripts:
  `verify_net/bin/split.sh`, `server_net/bin/split_doc.sh`.
- Repro (same-origin behind TLS): single-port `reflex run --env prod` behind a TLS terminator that keeps Host and adds no
  `X-Forwarded-*` (`verify_net/bin/tls_run.sh` + `bin/tls_term.py`) → never connects (all 403); raw handshake with
  `Origin: https://H` → 403, adding `X-Forwarded-Proto: https` → 101. 0.10.1 works. The self-hosting guide says this setup
  "needs no api_url configuration at all".
- Root cause: `reflex/app.py:512-515` returns `None` for `cors_allowed_origins` in prod when `deploy_url` is unset;
  `app.py:761-766` passes it to `AsyncServer`; engine.io then accepts only `{ASGI scheme}://{Host}`
  (`engineio/base_server.py:284-300`), and behind TLS termination the ASGI scheme is `http`.
- Affected guides at the tag: self-hosting.md L63-71 (split), L89-109 (API URL), L135-152 (static export), L84-95
  (reverse proxy/TLS claim); scaling.md L62-72 (CDN frontend); docker-example/app-platform-backend README L58-67;
  very likely docker-example/production behind a Render/Heroku TLS edge (Caddy replaces untrusted X-Forwarded-Proto; not
  run end-to-end). OK: docker-example/production-compose (Caddy terminates TLS itself).
- Fix shape: keep the secure default; before final update every guide above (`REFLEX_DEPLOY_URL` on the backend,
  X-Forwarded-Proto/Host for reverse proxies, Caddy `trusted_proxies`) and add an upgrade note; recommended code change:
  a Reflex origin callable for engine.io that also accepts `https://{Host}` behind a TLS proxy and logs a single actionable
  WARNING on rejection (see FINDING-023).

## FINDING-023: CORS rejection is reported as "server unreachable" (LOW)
- Cluster: `server_net` | Regression: no for the message (banner text identical at v0.10.1), but #7641 now triggers it by
  default | Verifier: NARROWED
- Repro: `server_net/bin/cors.sh server_net-main A_unset` — toast "Cannot connect to server: websocket error. Check if
  server is reachable at ws://localhost:8346/_event" while `/ping` answers 200; server logs one engineio WARNING then INFO.
- Also (examples_ui): the backend's debug Config dump still prints `cors_allowed_origins=('*',)` while the effective prod
  value is none, and the rejection line has no Reflex prefix.
- Code: `reflex_components_core/core/banner.py:80-91,107-110`. Fix shape: Reflex-side WARNING naming the rejected origin,
  what the backend saw and the setting to change; optionally a `no-cors` ping to say "reachable but refused".

## FINDING-024: `rx.App()()` no longer returns a Starlette app; listed only under Performance (LOW, changelog)
- Cluster: `server_net` | Regression: yes (by design) | Verifier: CONFIRMED; downstream reliance unlikely (rxe 0.9.11 uses
  `app._api`; docs/examples never call `app()`)
- `reflex/app.py:1010-1023` returns `_RootMiddleware` (no `add_middleware`/`routes`/`mount`). Fix: Breaking Changes entry
  pointing to `api_transformer` / `app._api`.

## FINDING-025: A middleware that fails on non-http scopes silently skips a FastAPI transformer's lifespan (LOW)
- Cluster: `server_net` | Regression: no (lifespan never ran on 0.10.1) | Verifier: CONFIRMED anomaly
- `api_transformer=[FastAPI(lifespan=...), old_docs_middleware]` where the middleware reads `scope["path"]` → only
  `Info: ASGI lifespan appears unsupported by <function ...>: KeyError('path')`. The docs' updated `scope.get("path")`
  example works. Root cause `reflex/app_mixins/lifespan.py:120-132` (any startup exception → INFO), `app.py:987-1007`
  (lifespan sent only to the outermost app). Fix: WARNING naming the transformers whose lifespan will not run, or send
  lifespan to inner Starlette transformers directly; upgrade note.

## FINDING-026: Routes differing only in case are accepted silently (LOW, not a regression)
- Cluster: `server_net` | Verifier: NARROWED (0.10.1: `/foo` already rendered `/Foo` but ran `/foo`'s on_load; 0.11 makes the
  backend agree with the frontend). Root cause `reflex/app.py:1295` exact-string comparison, `route.py:185` IGNORECASE.
  Fix: raise `RouteValueError` on a case-insensitive duplicate.

## FINDING-027: Prod `reflex run`: repeated Ctrl-C does not force exit while lifespan cleanup is stuck (LOW, not a regression)
- Cluster: `server_net` | Not separately verified. Lifespan task sleeping 60 s after `yield`, prod, Ctrl-C ×3 → exits only
  after 60 s. The force-exit handler (`_REPEAT_IGNORE_SECONDS`) is installed only in `_run_dev` (reflex/reflex.py). The
  #7650 changelog implies a later Ctrl-C forces the exit.

## FINDING-028: Deprecation warnings for handlers passed as props point into `site-packages/reflex_components_*` (LOW)
- Cluster: `examples_ui` | Regression: no (frame filter unchanged; `set_value` deprecation is new, so unchanged user code now
  hits it) | Verified by the orchestrator against the tag source
- Repro: reflex-examples overkey (outer `@rx.event` removed) on 0.11.0a1: `on_change=user_input_state.set_value`
  (overkey.py:359) logs `ClientStateVar.set_value has been deprecated ... (.../site-packages/reflex_components_core/el/elements/forms.py:857)`.
- Root cause: `reflex_base/utils/log.py` `_exclude_paths_from_frame_info` excludes click, reflex, typing_extensions,
  socketio, granian, reflex_base and the stdlib, but not the `reflex_components_*` packages split out of reflex.
- Fix shape: add every installed `reflex_components_*` (or any `reflex_*` distribution of the train) to the exclude roots.

## FINDING-029: First 0.11 run rewrites the committed `reflex.lock/package.json` as one-line JSON (LOW)
- Cluster: `examples_ui` | Regression: yes (cosmetic) | Not separately verified
- Any app run once on 0.10.1, then upgraded: `reflex.lock/package.json` (and `.web/package.json`) become compact JSON;
  content identical (`examples_ui/scripts/pkgjson_cmp.py`), `bun.lock` byte-identical. Every upgraded project gets a
  content-free VCS diff. Fix: keep indented output.

## FINDING-030: Forked prod workers share one `StateManagerRedis` instance id; oplock waiters passed over ~1 s (LOW)
- Cluster: `redis_runtime` | Regression vs 0.10.1: no (0.10.1 stalls 5-10 s) | Verifier: NARROWED to a wider root cause
- Repro: `verify_rds/bin/` (see `redis_runtime/NOTES.md` VERIFICATION): prod, Redis, `REFLEX_OPLOCK_ENABLED=true`,
  `GRANIAN_WORKERS=2..4`, pipelined events + `/api/bump` at concurrency 2-4 → 1.0-1.07 s waits in 4/6-5/6 runs (fork);
  0/6 under `REFLEX_BACKEND_START_METHOD=spawn`. Final counts always exact. A probe route sees 4 worker pids but one
  state-manager instance id under fork.
- Root cause: `reflex/istate/manager/redis.py:261` sets `_instance_id` once; the manager is built in the supervisor
  (`app.py:753`, fork preload `exec.py:1118/1148`) and inherited; `app.py:898-900` re-ids only the token manager. Contenders
  are a Redis SET of that id: a repeated SADD (`:1161`) emits no event so the lease is not broken (`:988`), and any waiter's
  SREM (`:1146`) deregisters every worker; the waiter reappears at its `lock_expiration/10` re-check (`:1251`).
- The #7534 changelog sentence "events waiting on other instances are no longer passed over by the next lease" is false as
  written for Linux prod with ≥2 workers. Fix shape (small): reset `_instance_id` per worker next to the token manager's;
  count contenders per waiter (`instance:lock_id` members); or reword the changelog.

## FINDING-031: After a Redis outage > ~5 s, cross-worker updates to connected clients are silently dropped (MEDIUM)
- Cluster: `redis_runtime` | Regression: no (`reflex/utils/tasks.py`, `token_manager.py` byte-identical to v0.10.1) |
  Verifier: CONFIRMED, NARROWED (recovers only when a new socket connects to the same worker)
- Repro: `redis_runtime/bin/faults.sh redis_runtime-stock 0 2 out.jsonl redis_restart` (verifier added `DOWN=`): prod,
  2 workers, 10 s outage, 10 `/api/bump` via `app.modify_state` → deltas received = 10 − bumps landing on the other worker;
  3.3 s outage → 10/10. Log: `_subscribe_lost_and_found_updates: task exceeded exception limit 5 within 60.0s`.
- Root cause: `tasks.py:44-53` re-raises after 5 suppressed errors; `token_manager.py:306-313, 438-453` use the defaults;
  tasks re-created only in `on_connect` (`app.py:2349-2351`) / `link_token_to_sid` (`token_manager.py:332`).
- Fix shape: unlimited capped backoff for these long-lived subscribers and/or re-ensure them on the emit path; re-store
  the worker's socket records after resubscribing.

## FINDING-032: A dead worker's socket record makes the returning tab look like a duplicate → new token (MEDIUM)
- Cluster: `redis_runtime` | Regression: no | Verifier: RECLASSIFIED out of the kill -9 claim (reflex's own bug; happens even
  with respawn on). Relates to registry HYD-07.
- Root cause: the socket record outlives its worker (TTL `redis_token_expiration`, default 3600 s, `token_manager.py:225`);
  `link_token_to_sid` treats the returning tab as a duplicate (`token_manager.py:342-346`). Deleting the stale record keeps
  the token. Fix shape: per-worker liveness key with a short TTL; take over a dead worker's record.

## FINDING-033: kill -9 of one granian worker stops the whole prod server (LOW-MEDIUM)
- Cluster: `redis_runtime` | Regression: no | Verifier: RECLASSIFIED — granian default `respawn_failed_workers=False`
  (`granian/server/common.py:125`, loop breaks at `:549`); reflex builds `Granian(...)` at `reflex/utils/exec.py:1152-1161`
  without it, and `GRANIAN_RESPAWN_FAILED_WORKERS` is read only by granian's CLI. Repro: `redis_runtime/bin/kill9.sh`.
  Fix shape: pass `respawn_failed_workers=True` or expose a setting.
- Side note (not filed): in-process, a manager doing 1000 back-to-back modifies starves a waiter on another manager for
  3.9-4.8 s on 0.11.0a1 (0.10.1: 0.03-0.22 s) via "instaque" barging in `_wait_lock`; a 3 ms gap removes it and the real-app
  matrix is fine. Worth a follow-up look.

## FINDING-034: `rx.client_state` "Give it a name" hint and docstring show a call that does not name the var (LOW)
- Cluster: `client_vars` | Regression: no (new API) | Verifier: CONFIRMED; docs at the tag use `name=` correctly
- `rx.client_state("x").push(1)` → `ValueError: ... Give it a name -- rx.client_state("my_name") -- ...`; following it
  creates an unnamed var whose default is "my_name" and raises the same error. Migration trap: `rx.ClientStateVar.create
  ("user_input")` (old name-first order) silently makes an unnamed var. Repro `verify_cv/a_hint.py`.
- Root cause: `reflex_base/client_state.py:58-62` (`_NOT_GLOBAL_MSG`), `:247` (docstring). Fix: `rx.client_state(default, name="my_name")`.

## FINDING-035: client_state generated identifiers collide (LOW)
- Cluster: `client_vars` | Regression: no (0.10.1 identical; its `capitalize()` setter also collided `searchQuery`/`searchquery`,
  which 0.11 now renders) | Verifier: CONFIRMED, blast radius NARROWED
- `name="item"` + `name="Item"` → `Identifier setItem has already been declared`: dev fails every page importing that
  module's memo file (`/casing2`; a text-only page still renders); prod build fails. One name with two defaults: silent
  (first mounted wins); with `auto_memoize=False` dev 500s on every route.
- Root cause: `client_state.py:315-316` (setter = `set` + capitalized first letter; defaults per name not recorded). Fix:
  setter derived from the getter name; compile-time error for one name with two defaults.

## FINDING-036: Operations on a None `set[...] | None` / `list[...] | None` var crash the page and fail the prod build (LOW)
- Cluster: `client_vars` | Regression: no (0.10.1 `reading 'includes'`) | Verifier: CONFIRMED, wider (every optional collection)
- `maybe: set[str] | None = None`; `S.maybe.contains("m")` → prod prerender `TypeError: Cannot read properties of null
  (reading 'some')` at `pySetHas`, export exits 1; dev render error. Root cause `.templates/web/utils/helpers/set.js:27-31`
  (no null guard; `None` dropped when the Var class is chosen). Fix: null-as-empty in helpers or `?.` for optional vars.

## FINDING-037: `print` / `str` / `%` / logging of a class-level backend var in server code now raises (LOW)
- Cluster: `client_vars` | Regression: yes (intentional #7651) | Verifier: CONFIRMED
- `print(State._secret)`, `str()`, `"%s" %`, `json.dumps(default=str)`, `str()` of mixin fields / `get_fields()` entries raise
  `BackendVarFormatError` ("cannot be used in the UI"); `logging.info("%s", State._secret)` prints `--- Logging error ---`;
  a bare module-level print stops the app importing. f-strings / `.format` already raised on 0.10.1; `repr` works.
- Root cause `reflex_base/vars/base.py:4418-4424` (`Field.__str__`). Fix: changelog sentence (or Breaking Changes) and
  "use repr() to inspect it" in the message.

## FINDING-038: Storage-compatible `default_factory` called extra times (LOW)
- Cluster: `client_vars` | Regression: yes (minor) | Verifier: CONFIRMED, wider
- One extra call per compile and one per backend worker in its first event (`hydrate_and_load` → `_sync_shared_storage` →
  `_shared_storage_groups`, cached per process). Matters for side-effecting / slow factories. Root cause
  `reflex/compiler/utils.py:346-358`, `reflex/state.py:2354-2373`. Fix: skip the factory check on the runtime path.

## FINDING-039: Unkeyed `rx.foreach` lifecycle payloads name the item at that position (MEDIUM)
- Cluster: `compile_memo` | Regression: no (0.10.1 crashes on this page; behaviour new with #7793) | Verifier: running
- cm page /loopnokey: `rx.foreach(S.items, lambda item: rx.text(item, on_mount=S.record_mount(item), on_unmount=S.record_unmount(item)))`,
  items [alpha, beta, gamma], remove first → `record_unmount("gamma")`. foreach keys children by index; the generated
  `useEffect` captures the loop var with `[]` deps. `key=item` fixes it; docs never say a key is needed. Related: the docs'
  per-row `rx.client_state` in an `@rx.memo` row follows the row position (state jumps rows after a removal).

## FINDING-040: on_mount / on_unmount inside `rx.cond` inside an `@rx.memo` body fire unconditionally (MEDIUM)
- Cluster: `compile_memo` | Regression: no (identical on 0.10.1) | Verifier: running
- cm page /memocond: hidden branch's on_mount fires at mount; toggling fires nothing. The cond child's `useEffect(..., [])`
  is hoisted to the memo body's top level. #7694's line "on_mount and on_unmount still follow their rx.cond branch" holds
  only outside `@rx.memo`.

## FINDING-041: `rx.foreach` with item hooks inside `@rx.memo` crashes the whole page (MEDIUM)
- Cluster: `compile_memo` | Regression: no (same on 0.10.1) | Not separately verified (documented gap)
- cm page /loopmemo → error boundary `ReferenceError: it_rx_state_ is not defined`. The changelog says only "not covered yet".

## FINDING-042: #7674 lucide digit-icon fix does not reach in-place upgraders (MEDIUM)
- Cluster: `compile_memo` | Regression: no | Verifier: running. With lucide 1.1.1 (what `pip install -U reflex` keeps):
  `rx.icon(S.icon_name)` with `grid_2x_2` blank, `DynamicIcon not found` ×11; 1.1.2a1 renders. See PKG-A.

## FINDING-043: compile_memo lows (LOW)
- f-string id in foreach (`rx.set_focus(f"rf_{item}")`) → every row registers `ref_rf_item_rx_state_`; focus/set_value hit
  the last row (same on 0.10.1).
- Blocking monitor blames a trivial handler for `_transform_event_arg`'s lazy `from reflex.model import Model` (0.2-0.9 s
  sqlalchemy import) on the first dict-arg event (also seen by enterprise).
- "auto_memoize=False without react_compiler=True" warning logged 2× per compile, 5× per dev run (no dedupe guard).
- Upload handler raising: response cut mid-body (`incomplete chunked read`; 0.10.1 returned 500); exception logged twice.

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
| PKG-09 | fresh reflex[db] on 3.11/3.14/3.15 via pip and uv | fixed (greenlet + aiosqlite present, migrations apply) | examples_ui |
| PKG-05 | pip without --pre resolves the pinned train | fixed | examples_ui |
| PKG-08 | sqlmodel / sqlalchemy cap | fixed (unchanged) | examples_ui |
| TP-04 | overkey restart clears input | changed (no longer reproduces on either version) | examples_ui |
| HYD-08 / HYD-09 | sync=True LocalStorage storms | fixed (0/3; control 0.10.0a3 storms) | client_vars |
| HYD-12 | removeItem of synced key → TypeError in computed var | fixed | client_vars |
| HYD-13 | shared-name synced vars only sync the last | fixed | client_vars |
| STATE-10 | backend-var misuse errors | changed (str/%/!s, id=, add_page now raise; child/typed-prop/event-arg unchanged) | client_vars |
| STATE-22 | storage default_factory on str var | changed (now a compile error; int/list still silent) | client_vars |
| STATE-23 | storage-typed var hydration error | changed (does not reproduce on either version) | client_vars |
| HYD-06 | pre-connect navigation runs left page's on_load | fixed | server_net |
| CLI-16 | dev backend refuses fast while broken | still fixed | server_net |
| CLI-27 (#7510) | `--json` truncated records on TERM | fixed | server_net |
| CLI-26 (#7509) | `--json` SIGINT to pid | changed (control no longer reproduces) | server_net |
| EVT-04 | prod + Redis bg deltas 6/6 | fixed | redis_runtime |
| STATE-20 | schema hash stable; sessions survive 0.10.1 ↔ 0.11.0a1 | fixed | redis_runtime |
| STATE-21 | hash depends on Python version | changed (3.11 vs 3.12 identical) | redis_runtime |
| STATE-26 | py3.14 / spawn state_auto_setters | fixed | redis_runtime |
| CMP-24 | hook component in rx.foreach | fixed | compile_memo |
| CMP-34 | upload_files from toast / call_script | fixed | compile_memo |
| CMP-27 | reproducible export | fixed (3937 files identical across seeds/paths) | compile_memo |
| CMP-01 | hostile upload filenames | fixed (contained on both) | compile_memo |
| CMP-05 | module-scope bundle_library survives prod compile | fixed | compile_memo |
| HYD-15 | dynamic components with bundled libs in prod workers | changed (single-port OK; backend-only untested) | compile_memo |
| CMP-35 | lazy libs heavier on a recharts page | still broken (~70 KB) | compile_memo |
| R101-08 | react_compiler silent bailouts | changed (warning logged) | compile_memo |
| HYD-07 | kill -9 worker → reconnect gets new_token | changed (reproducible on demand; same on 0.10.1) | redis_runtime |

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
### `compile_memo` (pass:17, anomaly:6, fail:4)
auto_memoize × react_compiler matrix in dev + prod (F,T best render counts, 2.2× faster Python compile); #7793 foreach
hooks, #7409 uploads, reproducible exports, per-component lazy libs, callout / code_block / match typing / mapping perf
verified. Issues: FINDING-003 widening (HIGH), FINDING-039 … -043.
### `examples_ui` (pass:13, anomaly:3, fail:2)
Nine non-DB reflex-examples apps (counter, github-stats, overkey, reflexle, upload, clock, quiz, snakegame, lorem-stream)
upgraded in place 0.10.1 → 0.11.0a1, dev/prod/cold: identical results except overkey (FINDING-001; fixed with a one-line
diff, 27/27). Fresh installs 3.11/3.14/3.15 pip+uv OK. Issues: FINDING-028/-029; split-origin prod = FINDING-022.
### `client_vars` (pass:16, anomaly:5, fail:1)
rx.client_state 91/91 + edge 51/51 (incl. auto_memoize=False + react_compiler), SetVar 29 ops × 17 mutations = Python,
storage declaration / shared-name sync / cross-tab clear, @property and backend-var errors, code-point strings; HYD-08/09/12/13
fixed. Issues: dup of FINDING-001; FINDING-034 … -038 (verified); not separately verified, filed as lows: `rx.match` on sets is
order-dependent (JSON compare), `set[str]` handler args arrive as `list`, `StringVar.split()` splits UTF-16 units,
int/list storage `default_factory` still silently ordinary vars, remaining cryptic backend-var errors (child / typed prop /
event arg / `==`), foreach per-row client state follows the index without `key` (docs).
### `redis_runtime` (pass:17, anomaly:5, fail:1)
Lock correctness exact across redis-py 7/8/beta × workers 1/2/4 × oplock; contention stalls 5-10 s → ~1 s; lost release
notification 8.35 s → 0.33 s; #7412/#7696/#7616/#7590 fixed vs failing 0.10.1; py3.11 shutdown no hang. Issues (verified, none regressions): FINDING-030 … -033.
### `server_net` (pass:19, anomaly:9, fail:1)
CORS matrix, lifespan forwarding, case-insensitive routes, HYD-06 prenav, oversized events, state-mismatch event, signals
and `--json`, `--frontend-only/--backend-only` ports, blocking monitor, otel trace ids, hosting-cli exit code. Issues:
FINDING-022 … -027.
### `events_await` (pass:15, anomaly:7, fail:3)
64 await scenarios × dev/prod × memory/Redis; middleware; failure paths; decorators; typing. Issues: FINDING-001/-007/-010/-015/-016, plus low: memory-manager `CancelledError` for a background task awaiting a superseded handler; background task that catches an awaited exception still shows the error toast; deprecation names only the first stacked method per class.
