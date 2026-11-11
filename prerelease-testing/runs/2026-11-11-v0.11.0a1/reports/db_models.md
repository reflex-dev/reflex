CLUSTER: db_models
SUMMARY: An rx.Model/sqlmodel blog app built and migrated on 0.10.1 upgrades in place to 0.11.0a1 cleanly: it runs unchanged in dev and prod, `reflex db status` swaps in the new env.py and keeps the old one as env.old, and an unchanged schema produces no revision. Rewriting the models faithfully to `MappedAsDataclass + DeclarativeBase` with async sessions, as the new docs describe, keeps the same tables, data and migration history with no spurious revision. The #7756 serializer works in Chromium in dev, prod+Redis and across hot reload; on 0.10.1 the same rewritten app fails with DetachedInstanceError. No regression in reflex runtime code was found. The main risks are in the newly recommended path, and all of them already exist on 0.10.1. Forgetting `rx.ModelRegistry.register(Base)` silently generates drop_table for every table (HIGH). Other problems: JSON columns are typed `object`, `default_factory` columns break migrations, the merge is random when two metadatas define the same table, and the admin-dashboard recipe fails on create with dataclass models.
ARTIFACTS: /home/user/reflex/prerelease-testing/runs/2026-11-11-v0.11.0a1/db_models/
TESTS:
- [pass] old app on 0.10.1: rx.Model Author/Post/Tag + SQLModel link table, unique index, Enum, UTC datetime, nullable, JSON; db init + 2nd revision (server_default backfill); data via Chromium incl. IntegrityError, dynamic route /post/[pid]
- [pass] in-place upgrade (`uv pip install --prerelease=allow reflex[db]==0.11.0a1`): app unchanged works dev + prod before any db command; startup logs "migration environment was created by an earlier Reflex release ... Run reflex db init"
- [pass] `reflex db status` upgrades env.py, env.old byte-identical to the 0.10.1 file, history shows (head) (current); makemigrations writes no revision; bare `alembic check` "No new upgrade operations"; migrate no-op
- [anomaly] first `reflex run` after the upgrade prints "Success: Initialized blog. Install dependencies from requirements.txt ... before running `uv run reflex run`" during `reflex run`
- [pass] rewrite to MappedAsDataclass/DeclarativeBase (same __tablename__s, Table() link + secondary=, async engine + async_sessionmaker(expire_on_commit=False), select/selectinload/scalar/get): makemigrations NO revision, alembic check clean, old rows render, new rows via UI, dev + prod
- [anomaly] UTC-aware datetimes written by sqlmodel UTCDateTime are read back naive by Mapped[datetime] (data intact; semantics change not mentioned by "data unchanged")
- [pass] new-style column add with scalar `default=` and `server_default=func.now()`: revision has server defaults, existing rows filled
- [fail] new-style column with `mapped_column(default_factory=...)` on a non-empty table: migrate fails NOT NULL (F2, both versions)
- [fail] forgetting rx.ModelRegistry.register(Base): drop_table for every table, no warning, migrate drops all data (F3, both versions)
- [anomaly] adopting a naming_convention on the rewritten Base emits create_unique_constraint for every existing unnamed UNIQUE (alembic behaviour)
- [fail] rx.Model + Base mixed: Base naming_convention lost for UniqueConstraint in merged metadata (F4, both versions)
- [fail] same table in old rx.Model module + Base both imported: winner random per process; alembic check 2/6 clean, 4/6 add_column (F5, both versions)
- [pass] reflex-local-auth (SQLModel tables) + Base-only rewrite: no drop of localuser/localauthsession (rx.Model is always registered); register/login + Base blog e2e in Chromium
- [pass] serializer e2e: list[Post] with nested user/tags/flags.user, rx.foreach over post.flags/tags, .length(), Post|None detail (client nav + direct), computed var returning models, two tabs, background task with `async with self`, rx.asession(), sync rx.session() with Base models
- [pass] synonym typing: `State.user.nick.upper()` renders (0.10.1: VarAttributeError on Mapped[str])
- [pass] mutating model instances held in state (column attr, nested user, relationship list append) updates UI and dependent computed var
- [pass] a user's own @rx.serializer for a Base subclass takes precedence over the built-in one
- [pass] prod + Redis (own redis-server :8159): models pickled, reload restores nested models; dev hot reload with models in state
- [pass] unloaded relationship: `.username` blank, `.flags.length()` shows the documented render error (dev + prod)
- [pass] #7648 plain @property on MappedAsDataclass model via var -> VarAttributeError with a clear message
- [anomaly] hybrid_property typed str, compiles, never serialized -> blank silently (unlike @property)
- [anomaly] column_property declared Mapped[int] is typed `object`
- [anomaly] default sessionmaker (expire_on_commit=True), object stored after commit -> serialized `{}`, UI silently blank, no warning (docs do say expire_on_commit=False)
- [fail] JSON column on a Base model typed `object`: `State.m.profile["city"]` -> TypeError at compile (F1, both versions)
- [fail] tables.md custom serializer example (`dataclasses.asdict`) fails on any model with relationships: DetachedInstanceError / RecursionError (F6)
- [pass] rx.AdminDash(...) / rx.App(admin_dash=...) -> AdminDashRemovedError with link to /docs/database/admin-dashboard/ (raised at construction)
- [pass] admin-dashboard recipe via api_transformer with Base models: login, list views incl. relationships/JSON; Reflex app still served
- [fail] admin "New <Model>" with MappedAsDataclass model -> 500 TypeError __init__ missing 'name' (F8)
- [fail] GET /admin (no slash) 404 via api_transformer; 0.10.1 rx.AdminDash redirected 307 (F9)
- [pass] deprecated get_migration_history / format_revision / alembic_autogenerate / rx.Model.alembic_autogenerate from user code: warnings name 0.11.0 -> 1.0.0 and point at the user line; still functional (legacy env.py upgraded, revision written when changes)
REVERIFIED:
- DOC-06: changed — overview.md now documents `async_db_url` and steers away from rx.asession; rx.asession() without it raises `ValueError: No async database url configured`
- PKG-15: still-broken — rx.Model deprecation warning still points at pydantic/_internal/_model_construction.py:133 on 0.11.0a1
ISSUES:
- TITLE: Unregistered DeclarativeBase -> makemigrations silently generates drop_table for every existing table (and the startup hint points at makemigrations)
  SEVERITY: high
  REGRESSION: no
  REPRO: NOTES.md F3. Copy the 0.10.1 project (apps/blog_as_built_on_0101 with its tables), replace blog/models.py+blog.py+db.py with apps/blog versions minus the line `rx.ModelRegistry.register(Base)`; `reflex db makemigrations --message x` (rc 0, no warning) -> revision drop_index/drop_table author, post, tag, posttaglink; `reflex db migrate` (rc 0) leaves only alembic_version. `reflex run` before that logs only "Detected database schema changes. Run reflex db makemigrations". Script: repros/variant.sh db_models-up noregister v_noregister.py (0.10.1: noregister0101). The 0.11 docs move every app to DeclarativeBase, where one missing line causes total data loss; a warning or refusal when target metadata lacks tables that exist in the DB would prevent it.
  EVIDENCE: db_models/logs/noregister_revision.py, logs/noregister_run.log
- TITLE: JSON column on a DeclarativeBase model is typed `object`; item access in a page is a compile TypeError
  SEVERITY: medium
  REGRESSION: no
  REPRO: probes/probe_types.py: `d: Mapped[dict] = mapped_column(JSON, ...)` (also dict | None, dict[str,str] | None) in a `m: M | None` state var -> `S.m.d["city"]` raises `TypeError: Var of type <class 'object'> does not support item access.` get_attribute_access_type uses `sa.JSON().python_type` (object) over the Mapped[] annotation. rx.Model `profile: dict = Field(sa_column=Column(JSON))` worked, so the documented rewrite breaks such pages; workaround `.to(dict)`. Same on 0.10.1.
  EVIDENCE: NOTES.md F1; first rewrite attempt traceback "Var of type object | None does not support item access. Happened while evaluating page 'index'"
- TITLE: MappedAsDataclass `default_factory` column added to a non-empty table -> NOT NULL migration failure (env.py server-default hook ignores default_factory)
  SEVERITY: medium
  REGRESSION: no
  REPRO: repros/repro_default_factory.sh new (and prev): Base model Item with one row, add `score: Mapped[int] = mapped_column(default_factory=lambda: 7)`, makemigrations -> `add_column(sa.Column('score', sa.Integer(), nullable=False))` with no server_default; migrate rc 1 `NOT NULL constraint failed` (batch leaves `_alembic_tmp_post`, so the next migrate fails "table _alembic_tmp_post already exists"). tables.md recommends default_factory for optional columns.
  EVIDENCE: db_models/logs/default_factory_migrate.log
- TITLE: Same table defined in two registered metadatas (old rx.Model module still imported during rewrite) -> which definition is compared is random per process
  SEVERITY: medium
  REGRESSION: no
  REPRO: repros/variant.sh db_models-up dup v_dup.py; in variants/dup run `alembic check` 6x: 2x "No new upgrade operations", 4x "New upgrade operations detected: add_column legacy_flag"; makemigrations 10x: 0.11 none,none,REV,none,REV,REV,REV,REV,none,none; 0.10.1 REV,REV,REV,REV,none,REV,REV,REV,REV,none. Only SAWarning "Table 'post' already exists within the given MetaData - not copying." (ModelRegistry.models is a set). A stale model can randomly yield drop_column/drop_index.
  EVIDENCE: db_models/logs/dup_alembic_check_6runs.log, logs/dup_sawarnings.log
- TITLE: Admin dashboard recipe: creating rows fails with MappedAsDataclass models (500), and the docs' own example uses a SQLModel model
  SEVERITY: medium
  REGRESSION: no
  REPRO: apps/adminapp (docs/database/admin-dashboard.md recipe with blog Base models, starlette-admin 1.0.3): `ADMIN_SECRET_KEY=k3y reflex run --frontend-port 3140 --backend-port 8140`; scripts/drive_admin.py http://localhost:8140 http://localhost:3140 x -> /admin/tag/create submit -> HTTP 500, server `TypeError: __init__() missing 1 required positional argument: 'name'` (starlette-admin calls Model() with no args). Listing works. Docs also leave MyAuthProvider undefined; current starlette-admin 1.0 API is login(username,password,remember_me,request)/authenticate/logout, and the older signature crashes the login page.
  EVIDENCE: db_models/logs/admin_create_500.log, shots/admin_dev_tag_create.png
- TITLE: Merged registry metadata drops the Base naming_convention for UniqueConstraint (rx.Model or any SQLModel table present)
  SEVERITY: low
  REGRESSION: no
  REPRO: repros/variant.sh db_models-up mixed v_mixed.py snap_blog_011up -> new Comment table `sa.UniqueConstraint('text')` unnamed while pk/fk keep convention names; Base alone (nc_single) -> `name=op.f('uq_comment_text')`. Same on 0.10.1.
  EVIDENCE: db_models/logs/mixed_revision.py vs logs/nc_single_revision.py
- TITLE: tables.md custom serializer example (`dataclasses.asdict(post)`) breaks for models with relationships
  SEVERITY: low
  REGRESSION: no
  REPRO: probes/probe_legacy_ser.py envs/new: relationship not loaded -> DetachedInstanceError; Post.user loaded -> DetachedInstanceError on user.posts; cycle loaded -> RecursionError. Docs give no relationship-safe pattern and no way to extend the built-in serializer.
  EVIDENCE: NOTES.md F6
- TITLE: `/admin` without trailing slash returns 404 through api_transformer (rx.AdminDash redirected), contrary to "existing links keep working"
  SEVERITY: low
  REGRESSION: yes (vs the removed rx.AdminDash on 0.10.1; api_transformer composition itself behaves the same on both)
  REPRO: probes/probe_admin_slash.py (cwd probes/slash): plain Starlette Mount -> 307 /admin/; via rx.App(api_transformer=...) -> 404 on 0.10.1 and 0.11. Live: 0.10.1 apps/admin0101 rx.AdminDash `/admin` 307; 0.11 adminapp `/admin` 404.
  EVIDENCE: NOTES.md F9
- TITLE: Silent blanks from the serializer: hybrid_property never sent (unlike @property, which now raises), expired objects (expire_on_commit=True) sent as {}
  SEVERITY: low
  REGRESSION: no (0.10.1 raised MissingGreenlet/DetachedInstanceError for expired objects instead)
  REPRO: apps/ser + scripts/drive_ser.py: `S.user.upper_name` (hybrid, typed str) renders "[]"; `expired` button (async_sessionmaker(engine) default, object stored after commit) renders "expired user: [] []"; no log line. probes/probe_ser.py prints `{}`.
  EVIDENCE: shots/ser_dev1_after_actions.png
NOT_COVERED: reflex-examples twitter as a second real app (left to db_upgrade, which owns the reflex-examples upgrades); Postgres/MySQL; user-edited env.py (db_upgrade); polymorphic inheritance, Decimal and composite columns in the serializer; admin edit form (starlette-admin 1.0 edit URL not found in time); reflex.dev link in AdminDashRemovedError not checked because the sandbox proxy blocks reflex.dev; an alembic downgrade across the rewrite.
