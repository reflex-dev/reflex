# PR survey: vars / client state / storage / compiler / DB (reflex v0.10.1..v0.11.0a1)
Source: commit messages, diffs, news fragments, tests in /home/user/reflex (read-only). "Tests" = what the PR itself added. "UNTESTED" = my suggestions, not verified against running code unless stated.
Note: GitHub PR API not used; commit messages (squash bodies) were sufficient.

====================================================================
PART A. DATABASE (deep)
====================================================================

## #7742 Move migration logic to alembic env.py and add CLI wrappers (d8e3984e8)
Intent: `reflex db *` become thin wrappers over the alembic CLI; the `alembic` command line works on a reflex app identically (e.g. `alembic downgrade -1`).
Runtime: new template `reflex/.templates/alembic/env.py` (shipped in wheel; must be checked in wheel+sdist), new `reflex/utils/migrations.py` (run/init/install_env/is_legacy_env/update_legacy_env/load_app/evaluate_pages), `reflex/reflex.py` db commands, `reflex/model.py` (custom EnvironmentContext code deleted; migrate()/alembic_init() kept as wrappers), `prerequisites.check_schema_up_to_date/check_db_initialized`, `compiler.compile_app` (skip-compile + dry_run now evaluates every page, writes no stateful_pages marker). pyproject: ruff INP001 exemption for template. Both a news deprecation + feature + 3 bugfix fragments.
Command mapping: init = `alembic init alembic` (stock alembic templates, stdout swallowed) + overwrite env.py with reflex template + `revision --autogenerate -m "Initial revision"` + `upgrade head`. migrate = `upgrade head`, then evaluate_pages(), then `check_schema_up_to_date()` (= `alembic --quiet check`). makemigrations = (evaluate pages) `revision --autogenerate`. status = `history --indicate-current`. Errors: alembic CommandError -> logged + exit 1; db_url unset or not initialized -> exit 1 (was exit 0 before: scripts/CI that tolerated rc=0 now fail).
Deprecated (0.11.0 -> removal 1.0.0, NOT removed): `reflex.model.alembic_autogenerate`, `get_migration_history`, `format_revision` and `rx.Model.alembic_autogenerate/get_migration_history`. `alembic_autogenerate` now ignores its `connection` arg and runs `check` + `revision --autogenerate` via env.py. Removed outright: private `_alembic_config`, `_alembic_render_item`, `_alembic_upgrade` (only matter to anyone importing privates). `migrate()` and `alembic_init()` still exist; `rx.Model.migrate/alembic_init` still exist.
Tests (tests/units/utils/test_migrations.py, 822 lines, 20+ tests, sqlmodel and sqlalchemy params): init creates env+initial revision; init writes missing env.py; no db_url; makemigrations/migrate follow model changes; callable default -> server_default for existing rows; utc datetime; schema check hints; status; commands need initialized db; legacy env updated with env.old for each entry point (migrate, status, init, model.migrate, alembic_autogenerate); migrate(autogenerate=True) at import before app exists; import-time migrate() not nesting alembic runs; bare `alembic` CLI standalone + evaluates pages when comparing; deprecated helpers via env.py; logging not reconfigured by migrate().

### The new template (reflex/.templates/alembic/env.py @ v0.11.0a1), condensed but faithful
```python
config = context.config
if config.config_file_name is not None and not invoked_by_reflex():   # fileConfig only under bare `alembic`
    fileConfig(config.config_file_name, disable_existing_loggers=False)

def compares_models() -> bool:   # True under `alembic revision --autogenerate` and `alembic check`
    cmd_opts = config.cmd_opts
    return cmd_opts is not None and (getattr(cmd_opts, "autogenerate", False) or cmd_opts.cmd[0] is command.check)

load_app(with_pages=not invoked_by_reflex() and compares_models())   # get_app() import; optional page evaluation; then ModelRegistry._metadata = None
target_metadata = ModelRegistry.get_metadata()
writer = Rewriter()

@writer.rewrites(ops.AddColumnOp)
def add_column_with_server_default(context, revision, op):
    default = op.column.default
    if default is not None and op.column.server_default is None:
        value = default.arg(None) if default.is_callable else default.arg
        op.column.server_default = sqlalchemy.DefaultClause(sqlalchemy.literal(value))
    return op

def process_revision_directives(context, revision, directives):
    autogenerate = getattr(config.cmd_opts, "autogenerate", False)
    if autogenerate and directives[0].upgrade_ops.is_empty():
        directives[:] = []          # no empty revisions
        return
    writer(context, revision, directives)

def render_item(type_, obj, autogen_context):   # adds `import sqlmodel` to revisions when a sqlmodel type (AutoString) is rendered
    if type_ == "type" and type(obj).__module__.startswith("sqlmodel"):
        autogen_context.imports.add("import sqlmodel")
    return False

def configure(**kwargs):
    context.configure(target_metadata=target_metadata, render_item=render_item,
        process_revision_directives=process_revision_directives,
        compare_type=False,                                   # column TYPE changes are never detected
        include_schemas=environment.ALEMBIC_INCLUDE_SCHEMAS.get(),
        render_as_batch=True, **kwargs)                      # sqlite ALTER emulation

def run_migrations_offline():   # url=get_config().db_url, literal_binds=True
def run_migrations_online():    # with get_engine().connect() as connection: configure(connection=connection) ...
```
- DB URL comes from rxconfig `db_url` via `reflex.model.get_engine()` (sync engine!). `sqlalchemy.url` in alembic.ini is ignored. `async_db_url` is not used by migrations.
- Default template is alembic's stock `generic` script.py.mako (no `import sqlmodel` line in the template itself; render_item adds the import per revision).
- Template was written for sqlmodel-or-SQLAlchemy: `ModelRegistry.get_metadata()` unchanged vs 0.10.1.

### How target_metadata is chosen (reflex/model.py ModelRegistry; identical code in 0.10.1 and 0.11.0a1)
- `ModelRegistry.models` is a set of registered CLASSES. `rx.Model.__init_subclass__` registers every rx.Model subclass (they all share `sqlmodel.SQLModel.metadata`). A user DeclarativeBase must be registered explicitly with `rx.ModelRegistry.register(Base)` (docs say this).
- `get_models(include_empty=False)` drops classes whose `.metadata.tables` is empty (so an un-registered or table-less Base contributes nothing).
- If exactly ONE registered class has non-empty metadata -> that class's `MetaData` is used as-is. Otherwise (2+ classes, which is the normal case for several rx.Model subclasses, or Model + Base) a fresh `MetaData()` is built and every table of every registered model's metadata is copied in with `table.to_metadata()`. So YES it combines multiple metadatas (SQLModel.metadata + each registered Base.metadata) into one merged copy.
- Caveats of the merge (my analysis, UNVERIFIED at runtime): (1) `naming_convention`/schema of the source metadata is not carried to the fresh MetaData -> named constraints computed from a convention may render unnamed; on sqlite batch mode needs names to drop/alter constraints. (2) several classes sharing one metadata means `to_metadata` is called repeatedly for the same table -> "Table already exists within the given MetaData - not copying" warnings. (3) the same table name defined in two bases -> second is skipped silently/with warning, no error. (4) with ZERO non-empty registered models the merged metadata is empty -> autogenerate emits `drop_table` for every table in the DB.
- Cache: `ModelRegistry._metadata` cached; new in 0.11: `load_app()` resets it to None at the end of every alembic run (fixes models imported lazily by pages being missed by the post-migrate schema check).
- Models imported only inside page functions/plugin hooks register only once pages are evaluated: `reflex db init/makemigrations/migrate(check)` and bare `alembic check`/`revision --autogenerate` now evaluate every page (`compile_app` skip-compile + dry_run) before comparing; bare `alembic upgrade`/`reflex db status` do not. Pre-fix bug (also present in 0.10.1): once `.web/backend/stateful_pages.json` existed, makemigrations missed lazily imported models and emitted `drop_table`.

### How an app initialized by 0.10.x gets upgraded
- 0.10.x `reflex db init` ran `alembic init` (stock alembic env.py, stock script.py.mako, alembic.ini) but its own in-process EnvironmentContext did the real work, so that stock env.py was NEVER executed by reflex.
- Trigger (`is_legacy_env`): env.py exists AND its text contains the literal string `target_metadata = None`. Any such file, even one with other user edits, is treated as legacy.
- Entry points that perform the upgrade automatically: `reflex db init` (on an already-initialized project; logs "Updated env.py to load the app; the previous one is kept as env.old. Existing revisions are kept." and returns WITHOUT running anything else), `reflex db migrate`, `reflex db makemigrations`, `reflex db status` (each logs at INFO then continues), `rx.Model.migrate()`/`reflex.model.migrate()` and `alembic_autogenerate()` (logged at WARNING; happens at import time for apps like rx-shout that call `rx.Model.migrate()` at module level). NOT automatic: the startup schema check (`check_schema_up_to_date` at `reflex run`) only logs an ERROR hint "created by an earlier Reflex release... Run reflex db init" and skips the check; a bare `alembic ...` CLI call on a legacy env.py runs the stock file against the placeholder URL `driver://user:pass@localhost/dbname` and fails (or does nothing useful).
- What is kept: `alembic/versions/*` (never touched), `alembic.ini` (never touched, test asserts byte-identical), `script.py.mako` (never replaced in final design; first draft replaced it, later commit "Init with alembic's stock template, replacing only env.py"). What changes: `alembic/env.py` -> `env.py` template; old file moved with `Path.replace` to `alembic/env.old` (a second upgrade overwrites an existing env.old without warning).
- User-edited env.py: kept ONLY if it no longer contains `target_metadata = None`. Consequence: in a 0.10.x app, an env.py that was hand-edited (e.g. `target_metadata = my_metadata`) was previously ignored; now it is executed for the first time by `alembic upgrade head`, with whatever imports/URL logic it has (likely stock `config.get_main_option("sqlalchemy.url")` placeholder or engine_from_config). It also has none of the template's hooks (empty-revision skip, server defaults, sqlmodel import, batch mode). Docs: move env.py aside and run `reflex db init` to write a fresh one (init writes env.py if missing). Edited stock file that still has the `None` line is silently replaced (backup in env.old, user must diff manually).
- alembic.ini differences: `sqlalchemy.url` is ignored; `script_location` is read as before (old alembic.ini writes `script_location = alembic` relative to cwd, new alembic versions write `%(here)s/alembic` -> running `reflex db` from another cwd or with a different `ALEMBIC_CONFIG` path can fail "Path doesn't exist"); the `[loggers]` section is applied only to the bare `alembic` CLI. `prepend_sys_path` matters for bare `alembic` importing the app (cwd must be project root). Old alembic.ini + env.py with `file_template` etc. work as before. `ALEMBIC_INCLUDE_SCHEMAS` still honored.
- Existing `versions/`: untouched; migrate = `upgrade head`. A DB whose `alembic_version` row is at head behaves as before. Old revisions that `import sqlmodel` need sqlmodel installed (still in `db` extra).
- Startup path: `reflex run` -> `get_compiled_app` -> `check_schema_up_to_date` now runs AFTER compile and uses `alembic check` via env.py (imports the app AGAIN inside alembic, with `_loading_app` guard).

### New docs (#7679 and #7742 edits to docs/database/overview.md): what is recommended
- Recommend plain SQLAlchemy 2.0: `class Base(MappedAsDataclass, DeclarativeBase)`, `rx.ModelRegistry.register(Base)`, tables with explicit `__tablename__`, `id: Mapped[int] = mapped_column(init=False, primary_key=True)`, `Mapped[...]` columns. MappedAsDataclass chosen so instances have kw constructors and serialize into state (via #7756 built-in serializer; no custom `@rx.serializer`).
- Two URLs in rxconfig: `db_url` (sync driver; `reflex db` + migrations) and `async_db_url` (async driver; app). SQLite: `sqlite:///reflex.db` + `sqlite+aiosqlite:///reflex.db`; Postgres psycopg3 for both; MySQL pymysql/asyncmy|aiomysql; MSSQL pyodbc/aioodbc.
- App code: one module-level `create_async_engine(rx.config.get_config().async_db_url)` + `async_sessionmaker(engine, expire_on_commit=False)`; handlers are `async` and do `async with Session() as session: ... (await session.scalars(select(User))).all(); await session.commit()`. `rx.session()` (sync) and `rx.asession()` are NOT recommended; blocking sync Session in handlers is called out in a warning box. Result rows assigned to `list[User]` state vars render with `rx.foreach`.
- `rx.Model`/`rx.session()` "deprecated as of 0.9.2, removed in 1.0" with a migration table (Field(foreign_key=)->mapped_column(ForeignKey), Relationship->relationship(back_populates=, repr=False), session.exec->session.scalars). Claim "Columns, data and migration history are unchanged, since both map to the same tables." and pointer to "Datetimes and SQLModel upgrades" in tables.md.
- Relationships docs (via #7756): load every relationship the page reads (selectinload); unloaded relationship is `undefined` in browser: `post.user.username` renders blank but `post.flags.length()` crashes the page render; cycles sent as `{"id": 1}` pk stubs.
- `pip install "reflex[db]"` now includes aiosqlite (#7679 pyproject); extras still alembic, greenlet, pydantic, sqlmodel.
- docs tests: docs/app/tests/test_database_examples.py (459 lines) executes the doc snippets with `pytest.importorskip("aiosqlite")`.

## #7756 SQLAlchemy DeclarativeBase serializer (40139e566)  [packages/reflex-base serializers.py, types.py]
Intent: `list[User]` state vars of plain SQLAlchemy models just work; no custom `@rx.serializer`.
Runtime: `serialize_sqlalchemy_base` registered lazily for `sqlalchemy.orm.DeclarativeBase` (output typed `dict`, so `State.user.name` is an ObjectVar); per-class cached layout (weak dict): unmapped dataclass fields, loaded columns, synonyms, relationships (+uselist), pk names. Reads `instance_state(m).dict` (never triggers lazy loads) -> unloaded/expired columns and relationships are omitted instead of raising DetachedInstanceError/MissingGreenlet. Transient/pending objects send all attrs (unassigned relationship -> None/[]). Cycles replaced by primary-key dict stub (None if pk incomplete). write_only/dynamic relationships skipped. Synonyms typed like their target (`get_attribute_access_type`) and sent via getter. Applies only to DeclarativeBase; rx.Model (SQLModel) keeps `serialize_sqlmodel`.
Tests: tests/units/reflex_base/utils/test_serializers.py (+1055 lines: loaded/unloaded/expired/detached, cycles, shared objects via two paths, synonyms, transient/pending, dataclass fields, composite pk, perf layout cache), test_types.py, test_attribute_access_type.py, test_lazy_serializer_regressions.py, docs test for relationships.
UNTESTED/QA: (1) after `session.commit()` with default `expire_on_commit=True` all columns are expired -> serialized dict is EMPTY `{}` and the UI renders blanks silently (docs say use expire_on_commit=False; try the default session). (2) Dataclass `field(init=False)` non-column fields, `column_property`, `hybrid_property`, `association_proxy`, `deferred()` columns, `composite()` - not in layout, silently dropped. (3) polymorphic/joined-table inheritance subclasses (layout per type(m): OK?) and `Mapped[Enum]`, `JSON`, `Decimal`, `datetime` column values (go through normal serializers). (4) A user who still registers their own `@rx.serializer def serialize_model(model: Base)` (from old docs): user serializer vs built-in precedence. (5) rx.Model and Base mixed in the same state; State var annotated `list[Base]` vs `list[User]`; computed var returning model instances; `rx.foreach` + `post.flags.length()` when relationship not loaded -> crash. (6) Sync `rx.session()` + Base model (sync lazy-load inside open session: serializer still omits unloaded -> data different from rx.Model behaviour).

## #7679 Rewrite the database docs around SQLAlchemy models (b97231239)
Intent: docs steer to SQLAlchemy async engine/sessions + MappedAsDataclass instead of rx.Model/rx.session; `aiosqlite` added to the `db` extra.
Runtime: docs only (overview/queries/relationships/tables/table.md, docs test) + `pyproject.toml` db extra `aiosqlite >=0.20.0`, uv.lock, news `+db-extra-aiosqlite.feature.md`. No framework code.
Tests: docs/app/tests/test_database_examples.py executes snippets against sqlite+aiosqlite.
UNTESTED/QA: follow the new doc verbatim in a fresh project on 0.11.0a1 (init, models, db init, handlers, rx.foreach, makemigrations after adding a column, migrate), plus: Postgres psycopg both URLs; `async_db_url` unset (what error?); `reflex[db]` install on py3.10..3.14 (aiosqlite wheel); `reflex export`/prod mode with async engine created at import and uvicorn workers/multi-process (engine bound to import-time loop?); hot reload dev mode (engine re-created each reload).

## RISK LIST - DB scenarios
A. Old app (0.10.x) with existing migrations upgrading to 0.11.0a1
 1. First `reflex db migrate/status/makemigrations` rewrites alembic/env.py (backup env.old). Verify: DB at head -> `migrate` no-op; `status` shows revisions with current marker; `makemigrations` with no model change writes NO revision; with model change writes a revision that has `import sqlmodel` when sqlmodel types are present.
 2. Hand-edited stock env.py w/o `target_metadata = None` is now executed (see above) - construct: edit target_metadata line to a variable, run `reflex db migrate`.
 3. `reflex run` after upgrade without running any db command: only an ERROR hint at startup, and schema check silently skipped; app still works. With `rx.Model.migrate()` at import: env.py replaced at import time, WARNING logged; check nesting works (migrate() called during env.py import is skipped by `_loading_app`).
 4. Spurious "Detected database schema changes" after upgrade: `compare_type=False`, server defaults not compared; but index/unique/nullable differences between old rx.Model tables and DB state show up. Verify an untouched 0.10.1 app gives zero diff in `alembic check`.
 5. Previously `reflex db makemigrations` exit code 0 with no DB; now exit 1 (scripts/CI).
 6. `ALEMBIC_CONFIG` env var pointing outside cwd; `alembic.ini` `script_location = alembic` relative path; running reflex from subdir.
 7. Multiple processes/workers importing app run `check_schema_up_to_date`; sqlite file locking with `alembic check` while app holds connection.
 8. offline mode `alembic upgrade --sql` with batch on sqlite not renderable (docs removed the suggestion).
 9. Postgres with `ALEMBIC_INCLUDE_SCHEMAS=True`; `db_url` using async driver by mistake (`sqlite+aiosqlite://`) -> get_engine sync engine fails.
B. Rewriting rx.Model (sqlmodel) -> `class Base(MappedAsDataclass, DeclarativeBase)` keeping tables
 1. Forgetting `rx.ModelRegistry.register(Base)` (or importing models only in a page not evaluated): target_metadata lacks the tables -> autogenerate writes a revision with `drop_table` for every existing table; `reflex db migrate` would then drop data. The non-empty revision is NOT skipped. HIGHEST data-loss risk. (Also: leaving rx.Model class + Base both defining same table name -> to_metadata duplicate warning, one silently wins.)
 2. Table name mismatch: rx.Model default `__tablename__` = lowercase class name (e.g. `user`); Base requires explicit `__tablename__`; a typo/rename = drop_table + create_table (data loss).
 3. Spurious diffs: `compare_type=False` hides String vs AutoString/Text/DateTime(timezone) differences, so those will NOT appear (and real type changes are never detected - not new). Expect diffs for: `index=True` names (`ix_<table>_<col>` same convention in both, check), `unique=True` (named vs unnamed unique constraints; sqlmodel creates UniqueConstraint differently), nullability (`Optional[int]` vs `Mapped[int]`; sqlmodel Field(nullable default) vs mapped_column), foreign keys (names; ondelete), implicit sqlmodel `id` pk missing if not re-declared, columns sqlmodel generated that Base doesn't declare (autogenerate drops the column -> data loss on migrate), `sa_column=` custom columns.
 4. Server default hook only for AddColumnOp: python-side `default=` scalar/callable is baked into the migration at generation time. `default=func.now()` / SQL-expression defaults / `insert_default=` / `MappedAsDataclass` `default_factory` (not a Column default) may crash `sqlalchemy.literal(value)` or add NOT NULL column without default to non-empty table (sqlite batch recreation fails). Not covered by tests beyond scalar + callable.
 5. Merged metadata: Base metadata with `naming_convention` loses it in the merged MetaData when 2+ models registered (e.g. rx.Model from reflex-local-auth + your Base) -> unnamed constraints, sqlite batch "Constraint must have a name".
 6. Datetime tz: docs say existing apps with naive datetimes read "Datetimes and SQLModel upgrades"; SQLModel upgrade (sqlmodel>=0.0.24) + utc datetime test exists only for fresh DB.
 7. Runtime: `rx.session()` (sync) with Base models works but returns un-serialized shape differences; `session.exec` doesn't exist on plain Session (sqlmodel-only API) -> AttributeError at runtime for ported code that keeps `.exec`.
C. reflex-enterprise / third-party (reflex-local-auth uses rx.Model, `rx.session()`)
 1. rx.Model, rx.session, rx.asession, rx.ModelRegistry, `reflex.model.migrate/alembic_init` all still exist; deprecated-but-present: `alembic_autogenerate`, `get_migration_history`, `format_revision` (warn once; call signature unchanged, behavior changed: connection ignored, runs through env.py; will fail if env.py cannot run). Removed: private `_alembic_config`/`_alembic_render_item`/`_alembic_upgrade`. grep site-packages of reflex-local-auth/reflex-enterprise for those names.
 2. rx.Model subclasses in third-party packages register at import; with `reflex db makemigrations` now evaluating every page, models imported lazily in plugin hooks are picked up -> a first `makemigrations` after upgrade may include new tables (e.g. local-auth tables) - verify no `drop_table`.
 3. Third-party packages with their own alembic/DB init at import (calling `rx.Model.migrate()` at module import): reentrancy guard skips nested runs; migration then happens in the outer run - verify tables exist for the first request after `reflex db init` on fresh project.
 4. `app.admin_dash` removed (#7739): any package using `rx.AdminDash` now raises AdminDashRemovedError.
 5. rx.Model sqlmodel serialization unchanged; DeclarativeBase serializer only for plain SQLAlchemy.

====================================================================
PART B. OTHER PRs
====================================================================

## #6936 Promote client state to rx.client_state with a scoped store
Intent: `rx.client_state(default, name=?)` is the supported API for client-only state; unnamed = tree-scoped (like useState, owned by outermost page or @rx.memo, per memo instance), named = global (backend can push/retrieve). Writes re-render only that var's subscribers.
Runtime: new `reflex_base/client_state.py`, `.templates/web/utils/client_state.js` (useClientState hook over a store with per-slot useSyncExternalStore, provider injected via VarData.app_wraps), `components/client_state_context.py`, new events `_client_state_set/_client_state_get` (replace eval'd run_script), compiler plugin changes (builtin.py/memoize.py), memo.py. `.set` is callable (`.set`, `.set(value)`, `.set(lambda v: ...)`); `.set_value` deprecated; `.global_value/.global_set` escape hatch; `rx._x.client_state` re-exports w/ deprecation; emitted identifier suffixed `RxClientState`; names validated as JS identifiers (non-ASCII rejected).
Tests: unit tests (test_client_state.py 752 lines, experimental test, context test, memoize plugin tests), vitest tests/js/client_state.test.js (622 lines, new vitest infra), Playwright test_client_state.py (674) + test_memo.py additions.
UNTESTED: (1) unnamed client_state created inside rx.foreach inside @rx.memo with auto_memoize=False + react_compiler=True (item scope vs owner scope; "A loop inside an @rx.memo function is not covered yet" per #7793). (2) same name used in two pages / named var `push` before provider mounted (retrieve returns undefined). (3) client_state + LocalStorage var with same name (name collision of store vs storage key); client_state named "cs" equal to generated prefix. (4) `.set(lambda v: ...)` with a v that is list/dict (placeholder typed), `.set` in rx.cond/rx.match branches, inside on_submit of a form. (5) embedded second rx app / SSR (`getClientStore` fresh store without document); page unmount/remount resets; hot-reload in dev. (6) legacy `ClientStateVar.create(global_ref=False)` path and `rx._x.client_state` deprecation. (7) `retrieve` callback in a background task / event chain order.

## #7642 SetVar for set and frozenset vars
Intent: set/frozenset state vars become SetVar with set ops (contains, union, intersection, difference, symmetric_difference, issubset, issuperset, isdisjoint, length, to_array); frozenset accepted; array ops on sets deprecated (still compile; warn 0.11.0 after #7789).
Runtime: `vars/set.py` (805 lines), JS helpers `utils/helpers/set.js` (pySet* keyed by value), serializers (frozenset), figure_out_type routing, ArrayVar drops `set`; foreach calls to_array(); set literals render sorted.
Tests: tests/units/reflex_base/vars/test_set.py (354), test_base, Playwright test_set_operations.py (216), foreach news.
UNTESTED: (1) SetVar of tuples/dataclass/BaseModel elements, set[int] vs set[str], mixed int/bool (`{1}|{True}` one element). (2) SetVar inside `rx.cond`/`rx.match`/`rx.foreach` + `contains` as cond condition; `Optional[set]` None. (3) event handler argument typed `set[str]` from rx.checkbox_group / select multiple; `State.tags == {...}`, `|`/`&` keep generic var meaning. (4) deprecated paths: `State.tags[0]`, `.length()` vs `len`, `set + list`, `tags.map` in prod build (warning only), `rx.foreach(State.frozen_tags, ...)` ordering (JSON array ordering of Python set - non-deterministic across restarts).  (5) Computed var returning set; `rx.Var.create({1,2})` with unsortable elements.

## #7582 Reject browser storage defaults produced by a default_factory (BREAKING)
Intent: `rx.LocalStorage/SessionStorage/Cookie` vars must have a storage default or storage annotation; default_factory now raises VarTypeError at compile.
Runtime: `reflex/compiler/utils.py` compile_client_storage / _compile_client_storage_field: checks storage-annotated field with factory; calls str/Any-compatible frontend factories once at compile; skips backend vars and factories that raise.
Tests: tests/units/compiler/test_compiler_utils.py (+154), test_hydration_storage.py tweak.
UNTESTED: factory on `Optional[str]`/`Literal`/`Annotated[str, ...]`; `rx.Field(default_factory=...)` + subclassed state (inherited); factory with side effects/time-based values called at compile and again at runtime; mixin states; `set_default` later; factory returning `rx.Cookie("x")` in `reflex export`.

## #7637 Sync shared-name storage vars in the writing tab (fixes #7567)
Intent: two synced LocalStorage vars with the same `name` now update each other in the tab that writes (previously only other tabs).
Runtime: `reflex/state.py` +89 lines: backend fan-out in the same locked event; groups by storage name (sorted by state/var name for determinism); vars written in the same event keep their value.
Tests: unit tests/units/test_state.py (+107), Playwright test_hydration_storage.py (+91).
UNTESTED: same name across different State classes/substates; mixed sync=True/False; Cookie/SessionStorage same name; conflicting writes in one event (deterministic last in sorted order); same-name var of different types (int vs str) -> coercion; client_state var with same name; background tasks writing; storage var + `rx.remove_local_storage`.

## #7652 Synchronize localStorage clear events across tabs
Intent: when localStorage is cleared / synced key removed, other tabs' synced vars reset to compiled defaults (like page load).
Runtime: `state.js` storage handler sends each var's default instead of null; removed backend None-to-default branch.
Tests: vitest/mjs state_js.test.mjs (+147, real sync event + echo), Playwright two-tab test, integration test_client_storage.py.
UNTESTED: `sessionStorage.clear()`; partial removeItem of one of several shared-name keys; Cookie vars; var with default_factory-free complex default (list/dict) and `sync=False`; clear in the same tab via devtools (storage event doesn't fire in same tab); vars sharing a name with different defaults (last wins - noted in commit).

## #7648 Clear error for unserialized @property on dataclass and Pydantic vars (BREAKING)
Intent: reading plain `@property` via a state var now raises VarAttributeError at compile instead of rendering empty.
Runtime: `utils/types.py is_unserialized_property`, `vars/object.py` check in attribute access (gated on property descriptor; skips models overriding `model_dump`; allows dataclass fields implemented by property).
Tests: test_object.py (+201), test_types.py (+20).
UNTESTED: `@cached_property`; property on SQLAlchemy MappedAsDataclass model (serializer #7756 does not send hybrid/plain props - does this check fire?); property on pydantic subclass with computed_field; inherited property on dataclass base; property used only in event handler (backend) vs frontend; Pydantic v1 compat models; `rx.Base`.

## #7651 BackendVarFormatError when a backend var is used in the UI
Intent: `State._secret` in UI contexts (LiteralVar.create, component id, toast, image src, on_upload_progress, page title/description/image, str()/%/!s) raises BackendVarFormatError naming the var instead of TypeError/ValueError/Field text in the page.
Runtime: `vars/base.py` Field._no_frontend_var_error, LiteralVar fallthrough helpers, `component.py`, `event/__init__.py`, `reflex/app.py add_page` metadata check, exceptions.py docstring.
Tests: test_base.py, test_component.py, test_app.py, test_event.py, test_upload.py, test_hooks.py, test_button.py.
UNTESTED: backend var in f-string inside rx.cond/rx.match; in `style=` dict, `class_name` list, `rx.script`, `rx.Var.create` list items; backend var in event handler args `on_click=State.f(State._x)`; backend var referenced in `rx.foreach` iterable; mixin backend vars; `str(State._x)` in event handler server-side code on class attribute (legit use now raises?) e.g. logging `str(Cls._x)` or Field repr in debug tools.

## #7548 Unicode-aware StringVar ops
Intent: StringVar length/index/slice/reversed/foreach operate on code points (emoji not split into surrogates).
Runtime: `vars/sequence.py` ops call `pyStrLength/pyStrAt/pyStrSlice/pyStrChars` in state.js (fast path native for strings without surrogates); foreach over StringVar uses chars op.
Tests: test_unicode_string_operations.py (Playwright), test_foreach.py, test_var.py.
UNTESTED: `.upper()/.lower()` on combining sequences; grapheme clusters (family emoji ZWJ, flags, accents with combining marks) - code points != visible chars; negative step slices, `[::-1]`, None/Optional strings; `str * int`; `.split("")`; python `len()` event-handler side vs frontend equality; large strings perf (Array.from).

## #7564 Make production frontend build reproducible
Intent: exporting twice yields identical files (no script renaming on deploy).
Runtime: stop bundling `.web/reflex.json` (version read from env.json); `utils/build.py`, `state.js`; `format_ref` drops Var marker (see #7691/#7707).
Tests: test_build.py, test_format.py.
UNTESTED: `reflex export` twice in different dirs/hash seeds `PYTHONHASHSEED` and compare dist trees; `reflex --version` shown in frontend (version display uses env.json); app w/ f-string ids around Vars; two foreach blocks with same param name.

## #7691 / #7707 Drop f-string Var marker from ref names (format_ref / format_array_ref)
Intent: ref names stable across runs (follow-up of #7564 which first used a sha256 digest).
Runtime: `utils/format.py`. Tests: test_format.py (pinned names).
UNTESTED: two vars differing only by type used as `id` -> same ref collision (dropped digest, commit accepts); `rx.set_value/set_focus/scroll_to` with f-string ids; refs in rx.foreach of different item types with same lambda param name (potential duplicate ref -> wrong element focused).

## #7276 Load only the optional libraries each dynamic component uses
Intent: with `frontend_lazy_bundled_libraries` (env `REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES`, default False) a dynamic component loads only the optional libs it needs.
Runtime: `templates.py`, `components/dynamic.py` first-line `//__reflex_evaluate` marker with library list, `state.js` loader, retry-able loads.
Tests: unit codegen test, docs node test, integration test_dynamic_components.py parametrized lazy off/on (banana icon not in window.__reflex until rendered).
UNTESTED: dynamic component from a page loaded by SSR/prod export; failing network for a chunk then retry; two dynamic components needing the same lib concurrently; custom scripts reading `window.__reflex` directly; lazy flag + `@rx.memo` components; libs with names like `constructor`.

## #7694 React Compiler optimizes generated components + auto_memoize option
Intent: Reflex emits code React Compiler can compile; new experimental `auto_memoize` (REFLEX_AUTO_MEMOIZE); with `react_compiler=True, auto_memoize=False` whole pages are memoized by the compiler (faster Python compile).
Runtime: useRegisteredRef hook instead of writing refs in render, UUID in inline useMemo, useCallback deps only referenced bindings, outlining disabled, Emotion jsx described to compiler, pinned experimental compiler, `vite-plugin-react-compiler.js`, `MemoizeStatefulPlugin` removed from page compile when auto_memoize=False, components with lifecycle events/hooks keep a wrapper; config warnings.
Tests: test_plugins.py, test_memoize_plugin.py, test_config.py (+86), vite plugin template test, Playwright test_memo.py (+107), component tests.
UNTESTED: react_compiler=True + auto_memoize=False with: client_state (unnamed) in rx.foreach in @rx.memo; rx.cond/rx.match branches with on_mount/on_unmount; upload components; rx.moment/dynamic components; `rx.input` with debounce; large page re-render counts; error boundary; dev (HMR) vs prod build; Windows; both options False (warning only).

## #7793 Pass loop variables to auto-memo wrappers inside rx.foreach
Intent: hooks (on_mount, on_unmount, add_hooks) of components inside rx.foreach no longer crash with loop vars and run once per item.
Runtime: `reflex/compiler/plugins/memoize.py` (_scope_instance_hooks, in_loop wrapper receives loop vars as props), `memo.py`, `memoize_helpers.py`, `iter_tag.py`.
Tests: test_memoize_plugin.py (+289), Playwright test_memoize_edge_cases.py (+135).
UNTESTED: documented gap "A loop inside an @rx.memo function is not covered yet"; nested rx.foreach (inner loop var + outer var in hooks), foreach with index var, `rx.foreach` over dict items, hooks + key stability when list reorders (unmount/mount counts), foreach inside rx.cond inside foreach, with auto_memoize=False (react_compiler) path where wrapper is kept.

## #7057 Bound mapping type inference to sampled entries (perf)
Intent: figure_out_type for big dict values does not scan all entries.
Runtime: `vars/base.py` (5 lines). Tests: test_base.py, benchmarks test_type_inference.py.
UNTESTED: dict with heterogenous values past the sample limit (type inferred from first N only -> frontend type ops wrong); huge dict literal in state default; dict[str, list[...]] nested.

## #7409 Resolve files in serialized upload callbacks
Intent: uploads triggered from toast actions or `rx.call_script` callbacks no longer fail with `ReferenceError: filesById is not defined`; use current selection.
Runtime: `templates.py` (provider wrap), `event/__init__.py` serialization, docs upload.md.
Tests: Playwright test_toast.py (+181), test_upload.py.
UNTESTED: toast opened, selection changed, then clicked; multiple upload ids; upload inside @rx.memo; in rx.foreach with literal upload id; `rx.upload_files(on_upload_progress=...)`; page without upload provider.

## #7721 Apply each streamed upload update once, with a synchronous listener
Intent: repeated upload chunk updates can't restore stale values.
Runtime: `.templates/web/utils/helpers/upload.js` (34 lines). Tests: client_upload.mjs (node), test_client_event_queue.py.
UNTESTED: large multi-file upload with yield-based progress updates; cancel mid-upload; two simultaneous uploads; slow connection; error path then retry.

## #7716 Accept a component as rx.callout icon
Intent: `rx.callout("x", icon=rx.icon("info"))`, rx.cond/rx.match of icons, ComponentVar from @rx.memo arg work.
Runtime: radix `callout.py` pops icon prop, wraps str in Icon, keeps component/ComponentVar as-is. Tests: test_callout.py.
UNTESTED: icon = Var[str] name from state (still goes to Icon.create -> dynamic icon); callout inside foreach; icon=None; `rx.callout.icon` child plus icon prop.

## #7753 Accept "text" as code_block language
Runtime: LiteralCodeLanguage adds "text". Tests: type_checking components_code.py.
UNTESTED: runtime render of `rx.code_block(code, language="text")` with react-syntax-highlighter (no grammar load), with Var language, copy button, line numbers.

## #7750 Type rx.match as Component or Var by first case
Runtime: typing overloads only (match.py). Tests: type_checking, test_match.py.
UNTESTED: pyright/ty on user code returning rx.match from functions annotated `-> rx.Component`; first case a Var vs str; default case type differs.

## #7747 Type input clear_events as events accepted by on_click
Runtime: typing only (radix/internal input.py). Tests: type_checking components_internal.py.
UNTESTED: runtime clear button with event spec, bound handler, list of handlers; `rx.input(clear_events=...)` in reflex-components-internal.

## #7674 Fix blank digit-x-digit icons in dynamic rx.icon
Intent: Var-tagged icons like `grid_2x_2` render (Lucide wants `grid-2x2`); docs gallery uses native `title` tooltips.
Runtime: lucide `icon.py` new var_operation `dynamic_icon_name_operation` (JS replaceAll + regex). Tests: test_icon.py.
UNTESTED: Var tag with `arrow_up_0_1`, `a_arrow_down`, camelCase tags; names like `grid-2x2` already kebab; static (non-Var) path for the same icons; unknown icon name fallback.

## #7739 Remove starlette-admin integration (BREAKING)
Runtime: `rx.AdminDash`/`App(admin_dash=)` raise AdminDashRemovedError; docs page `docs/database/admin-dashboard.md`; starlette-admin leaves dev group.
Tests: test for named route of Starlette api_transformer via app(), exceptions.
UNTESTED: old app with `admin_dash=rx.AdminDash(models=[...])` -> error message clarity at import vs compile; doc's recipe (api_transformer + SessionMiddleware + AuthProvider) with Base models and sqlmodel; `/admin` route no longer mounted.

## #7668 trace_id/span_id in JSON log records inside a span
Runtime: `reflex_base/otel.py trace_fields()`, `utils/log.py _write_json` merges ids (both JsonHandler and console.print JSON). Tests: test_otel.py, test_log.py.
UNTESTED: OTel enabled with real exporter, handler inside background task, no-op tracer, `REFLEX_LOG_FORMAT=json` + otel disabled (no opentelemetry import).

## #7635 Trace reflex-workflow step attempts with OpenTelemetry
Runtime: new `reflex_workflow/otel.py`; CONSUMER span per step attempt, link to scheduling span, traceparent in next_args reserved key (stripped before step sees args); ReflexInstrumentor toggles. Tests: unit/otel tests for workflow trace points (skipped w/o sqlalchemy).
UNTESTED: workflow with otel off (no opentelemetry import); rows created before upgrade (no traceparent key); retries chain; fan-out; wake_in days; payload size growth; DB-backed workflow with sqlite+Postgres.

## #7670 hosting-cli: fail cloud config when PyYAML missing
Runtime: `reflex_cli/utils/hosting.py` raises Exit(1). Tests: test_hosting.py, test_vmtypes_regions.py.
UNTESTED: `reflex cloud config --json` in env without PyYAML (exit non-zero, no JSON); existing cloud.yml (exit 0, generated false).

## #7789 Stamp unreleased deprecations with 0.11.0; postpone form id removal to 0.12
Runtime: deprecation_version strings in client_state.py, event/__init__.py, vars/set.py, forms.py, experimental/client_state.py, model.py, state.py. Tests: none new (strings). 
UNTESTED: grep warnings shown to the user for each deprecated path report "deprecated in 0.11.0, removed in 1.0"; id-based form submission still works in 0.11 with warning.

## #7784 Raise floors on 0.11 component siblings to train dev0
Runtime: pyproject.toml only (at tag: components-code/core/radix >= 0.11.0a1, reflex-base >= 0.10.2.dev0, hosting-cli >= 0.2.1).
UNTESTED: `pip install reflex==0.11.0a1` resolves published component alphas (not 0.10.1 finals) without `--pre` complaints; reflex-base floor 0.10.2.dev0 satisfied by published base version; min-deps install of old siblings (dataeditor 0.10.1 etc.) works with new reflex.

## #7698 Restore unconditional psycopg[binary]
Runtime: dev dependency group + docs/app only (no shipped package change). UNTESTED: none user-facing.

====================================================================
TOP RISKS (10)
====================================================================
1. Base model not registered / table-name mismatch => autogenerate emits drop_table for existing tables (data loss).
2. User-edited 0.10.x alembic env.py (no `target_metadata = None`) is now executed for the first time.
3. Legacy env.py replaced silently on first db command (env.old backup only; startup check merely logs hint).
4. DeclarativeBase serializer returns `{}`/omits attrs for expired (expire_on_commit=True) or unloaded rows; `.length()` on unloaded relationship crashes the page.
5. rx.client_state unnamed-in-foreach-in-@rx.memo with auto_memoize=False + react_compiler=True (documented gap in #7793).
6. Merged ModelRegistry metadata drops naming_convention; sqlite batch mode needs named constraints; also AddColumn server_default hook with SQL-expression defaults.
7. Breaking: storage default_factory now compile error (#7582); plain @property on pydantic/dataclass var is a compile error (#7648); rx.AdminDash raises (#7739).
8. `reflex db` commands now exit 1 without DB; alembic.ini script_location cwd-relative / ALEMBIC_CONFIG path issues.
9. Ref-name changes (#7564/#7691/#7707): digest dropped so same-name refs of different types can collide; verify reproducible exports.
10. SetVar migration: array ops on set vars deprecated but compile; set ordering non-deterministic; frozenset/tuple elements compared by value in JS only.
