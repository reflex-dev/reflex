# db_models — 0.11.0a1 notes

## Status / resume here
- [x] Step 1: old-style app `blog` built on reflex 0.10.1 (venv `$SB/envs/db_models-up` before upgrade; `$SB/envs/db_models-old` stays 0.10.1),
  `reflex db init` + 2nd revision `add bio views`, data created in Chromium. Snapshot of the 0.10.1 project (incl. reflex.db): `$SB/apps/db_models/snap_blog_0101/`.
- [x] Step 2: in-place upgrade to 0.11.0a1 (PASS)
- [x] Step 3: model rewrite + migration variants (done; findings F1-F5 below)
- [x] Step 4: serializer e2e (dev, prod+redis, hot reload, legacy serializer) done
- [x] Step 5: AdminDash (done)
- [x] Step 6: deprecated helpers (done)
- [x] artifacts copied, report at `../reports/db_models.md`. All my servers/redis stopped. CLUSTER DONE.

## Rerun from this directory
Scripts assume `$SB/apps/db_models/` as root: `mkdir -p $SB/apps/db_models && cp -a apps/* scripts/*.sh $SB/apps/db_models/ && cp -a scripts $SB/apps/db_models/scripts && cp -a repros probes $SB/apps/db_models/`.
Snapshots used by `repros/variant.sh`: `snap_blog_0101` = `apps/blog_as_built_on_0101` (0.10.1 project, legacy env.py, 2 revisions); `snap_blog_011up` = same after
`reflex db status` on 0.11 (env.py upgraded); `snap_blog_rw` = `apps/blog` minus revision `fc3bc0a55fc1` and the `summary/score/update_ts` columns. `*.db` files are not copied:
recreate with `reflex db migrate` (empty tables still show the drop_table / random-merge results); data rows came from `drive_blog.py create`.
Extra: `apps/blog_0101_models.py` / `blog_0101_app.py` are the old-style sources; rewritten app `rw0101` = `snap_blog_rw` + `snap_env_0101.py` run on 0.10.1 (DetachedInstanceError, logs/rewrite_on_0101_detached.log).

## Setup
- `SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`
- venvs: `cd $SB && uv --no-config venv $SB/envs/db_models-old --python 3.12 && uv --no-config pip install --python $SB/envs/db_models-old/bin/python --only-binary :all: 'reflex[db]==0.10.1' starlette-admin` (same for `db_models-up`).
- Helpers (in `scripts/` here; originals in `$SB/apps/db_models/`): `run.sh <venv> <appdir> <log> dev|prod` (dev 3140/8140, prod single port 3141), `stop.sh <appdir>`, `wait.sh <url>`.
- Drivers: `scripts/pwlib.py`, `scripts/drive_blog.py <base> create|verify <tag>` run with `$SB/envs/driver/bin/python` from `scripts/`.

## Step 1 — old app on 0.10.1
Models (`blog/models.py` in `apps/blog_0101_models.py`): Author (unique index name, nullable email, Enum role, UTC datetime, JSON profile), Post (index title, FK author, datetime),
Tag (unique name), PostTagLink (plain `sqlmodel.SQLModel` link table, composite pk). One-to-many Author.posts, many-to-many Post.tags.
`reflex db init` -> revision 5c38124c7e86; `makemigrations --message "add bio views"` -> 5962b6935088 (`bio` nullable AutoString, `views` Integer server_default 0). 
Chromium (`drive_blog.py create`): 2 authors, duplicate-name IntegrityError surfaced, 3 posts with tags, detail page `/post/[pid]`, bump views: all PASS on 0.10.1, no page errors.

## Step 2 — in-place upgrade 0.10.1 -> 0.11.0a1 (`uv pip install --prerelease=allow 'reflex[db]==0.11.0a1'` into db_models-up)
- Installs aiosqlite 0.22.1 (new `db` extra) ; lucide stays 1.1.1, redis stays 7.4.1 (no -U).
- `reflex run` (dev) BEFORE any db command: app works unchanged in Chromium (`drive_blog.py verify up_dev1`: all PASS); log shows
  "The migration environment was created by an earlier Reflex release and cannot load the app. Run reflex db init to update env.py; existing revisions are kept." (expected per #7742).
  anomaly: first `reflex run` after the upgrade prints "Success: Initialized blog. Install dependencies from `requirements.txt` with `uv pip install -r requirements.txt` ... before running `uv run reflex run`." — while it IS `reflex run`.
- `reflex db status`: "Info: Updated env.py to load the app; the previous one is kept as .../alembic/env.old." then history with `(head) (current)`; env.old byte-identical to the 0.10.1 env.py. PASS.
- `reflex db makemigrations` with no model change: no revision, exit 0, **prints nothing at all** (anomaly: no "no changes detected" feedback; 0.10.1 is also silent? not checked).
- `alembic check` (bare CLI from app dir): "No new upgrade operations detected." `reflex db migrate`: no-op, rc 0.
- prod (`--env prod`, single port 3141): drive_blog verify all PASS, no errors.

## Step 3 — rewrite to `class Base(MappedAsDataclass, DeclarativeBase)` (same tables)
Rewritten files: `apps/blog/blog/models.py`, `db.py`, `blog.py` (async engine + `async_sessionmaker(expire_on_commit=False)`, `select()`/`selectinload`, `session.scalar`, `session.get`).
Link table as `Table("posttaglink", Base.metadata, ...)` with `relationship(secondary=...)`. Faithful nullability: `profile: Mapped[dict | None] = mapped_column(JSON, default_factory=dict)`.
- `reflex db makemigrations`: **NO revision** (PASS). `alembic check`: no ops. `reflex db status` unchanged. Old rows render; new rows created via UI (`drive_blog.py create2 rw_dev1`) PASS in dev and prod.
- Data: datetimes written by sqlmodel `UTCDateTime` are read back naive by `Mapped[datetime]` (UI shows `2026-11-11 00:48:57.274411` instead of `...+00:00`). Data intact; semantics change (anomaly; not mentioned by the "data unchanged" claim in overview.md).
- New-style column add (`summary: Mapped[str] = mapped_column(default="n/a")`, `score ... default=7`, docs' `update_ts` with `server_default=func.now()`): revision has server defaults, migrate fills existing rows. PASS.

### F1 (MEDIUM, not a regression) JSON column on a DeclarativeBase model is typed `object` -> `State.m.profile["city"]` is a compile TypeError
`probes/probe_types.py`: `Mapped[dict]` / `Mapped[dict | None]` / `Mapped[dict[str,str] | None]` with `mapped_column(JSON)` all give Var type `object` (`sa.JSON().python_type` is `object`, and
`get_attribute_access_type` prefers the column python_type over the `Mapped[...]` annotation). `S.m.d1["city"]` -> `TypeError: Var of type <class 'object'> does not support item access.`
Same on 0.10.1 (`envs/prev`). rx.Model `profile: dict = Field(sa_column=Column(JSON))` worked, so the documented rewrite breaks such pages. Workaround `.to(dict)["city"]`.
Run: `cd $SB/apps/db_models/probes && $SB/envs/new/bin/python -I probe_types.py envs/new`.

### F2 (MEDIUM, not a regression) `mapped_column(default_factory=...)` column added to a non-empty table: NOT NULL migration fails
tables.md recommends `default=None` or `default_factory` for optional columns. A `default_factory` is a dataclass default only (no Column.default), so env.py's
`add_column_with_server_default` sees nothing: revision `add_column(sa.Column('score', sa.Integer(), nullable=False))`; `reflex db migrate` -> rc 1,
`sqlite3.IntegrityError: NOT NULL constraint failed: _alembic_tmp_post.score` (batch) / `ALTER TABLE item ADD COLUMN score INTEGER NOT NULL` (simple case) and a leftover `_alembic_tmp_post` table
makes the next migrate fail with "table _alembic_tmp_post already exists". Same on 0.10.1. Repro: `repros/repro_default_factory.sh new` (and `prev`).

### F3 (HIGH, not a regression) Forgetting `rx.ModelRegistry.register(Base)` -> silent drop_table of every table
`repros/variant.sh db_models-up noregister v_noregister.py`: makemigrations rc 0, no warning, revision = drop_index + drop_table for author/post/tag/posttaglink.
`reflex db migrate` rc 0 -> only `alembic_version` left (all data gone). 0.10.1 identical (`variant.sh db_models-old noregister0101 v_noregister_0101.py snap_blog_0101`).
`reflex run` in that state (before makemigrations) logs only "Detected database schema changes. Run reflex db makemigrations to generate migration scripts." — i.e. it points the user at the command that writes the drop revision (`logs/noregister_run.log`).
Newly exposed because the 0.11 docs move every app to DeclarativeBase where one missing line = data loss; nothing warns that the target metadata is empty while the DB has tables.

### F4 (LOW, not a regression) Merged metadata drops Base's naming_convention for UniqueConstraint
`variant.sh db_models-up mixed v_mixed.py snap_blog_011up` (rx.Model tables + new Base table with `MetaData(naming_convention=...)`): `sa.UniqueConstraint('text')` unnamed
(pk/fk keep `pk_comment`/`fk_comment_post_id_post`). Base alone (`nc_single`): `sa.UniqueConstraint('text', name=op.f('uq_comment_text'))`. rx.Model is always registered
(`ModelRegistry.register(Model)` at import) so any SQLModel table (reflex-local-auth!) triggers the merge. Same on 0.10.1 (`mixed0101`).
anomaly: adopting a naming_convention on the rewritten Base emits `create_unique_constraint('uq_tag_name')` for each existing unnamed UNIQUE (alembic behaviour).

### F5 (MEDIUM, not a regression) Same table in two metadatas (old rx.Model module still imported) -> which definition wins is random per process
`variant.sh db_models-up dup v_dup.py`: only `SAWarning: Table 'post' already exists within the given MetaData - not copying.`; `alembic check` 6 runs: 2x "No new upgrade operations", 4x
"New upgrade operations detected: add_column legacy_flag ...". makemigrations 10x: 0.10.1 `REV REV REV REV none REV REV REV REV none`, 0.11.0a1 `none none REV none REV REV REV REV none none`.
(`ModelRegistry.models` is a set of classes -> merge order follows id-hash.) A stale module during the rewrite can randomly generate drop_column/drop_index.

### PASS: reflex-local-auth (plain SQLModel tables) + Base-only rewrite
`v_localauth_old.py` (old app + local-auth -> revision creates localuser/localauthsession) then `v_localauth_rw.py` (Base rewrite, local-auth kept): no revision; local-auth tables are
still managed because reflex registers `rx.Model` (=SQLModel.metadata) itself.

## Step 4 — DeclarativeBase serializer (#7756) end to end
App `apps/ser` (models User/Post/Tag/Flag on `Base`, m2m `post_tag`, synonym `nick`, `column_property` name_len, `hybrid_property` upper_name).
Run: `cd $SB/apps/db_models/ser && reflex db init` (envs/new); `run.sh new $SB/apps/db_models/ser <log> dev`; `cd scripts && $SB/envs/driver/bin/python drive_ser.py http://localhost:3140 <tag> [legacy]`.
Prod+Redis: `redis-server --port 8159 --save '' --appendonly no`; `REFLEX_REDIS_URL=redis://localhost:8159 run.sh new ... prod`; `drive_ser.py http://localhost:3141 ser_prod_redis`.
Python probes: `probes/probe_ser.py` and `probes/probe_legacy_ser.py` (`$SB/envs/new/bin/python -I probe_ser.py envs/new`; compare `envs/db_models-old`).

Results (dev, prod+Redis identical):
- PASS `list[Post]` with selectinload user/tags/flags.user; `rx.foreach(post.flags)`, `post.flags.length()`, nested `flag.user.username`, m2m tags.
- PASS synonym: `S.user.nick.upper()` renders `ALICE` (0.10.1: `VarAttributeError ... type sqlalchemy.orm.base.Mapped[str] has no attribute 'upper'` -> fixed as advertised).
- PASS computed var returning `Post | None` and `list[str]` built from models; two tabs; background task (`async with self`) assigning models; `rx.asession()`; `Post | None` detail page (client nav + direct).
- PASS mutation of model instances held in state (`self.posts[0].title = ...`, `self.user.username = ...`, `self.posts[0].tags.append(Tag(...))`) updates the UI and the dependent computed var.
- PASS user `@rx.serializer` for a Base subclass (Tag) takes precedence over the built-in one (`LEGACY_SER=1`).
- PASS Redis prod: models pickled into redis, page reload restores `bg_posts`/`as_posts` with nested users. PASS dev hot reload (`drive_hotreload.py`): models in state survive, events work after reload.
- PASS (documented) unloaded relationship: `p.user.username` renders blank; `p.flags.length()` -> page shows "An error occurred while rendering this page ... TypeError: Cannot read properties of undefined (reading 'length')" (dev and prod).
- PASS (#7648) plain `@property` -> `VarAttributeError: The property 'display' on dataclass 'User' is not included in serialized state. Only declared dataclass fields are serialized; register an `rx.serializer` ...` (0.10.1: compiled, rendered blank).
- anomaly (LOW) `hybrid_property` typed `str`, compiles, but is never serialized -> renders blank silently (no error like @property). Same on 0.10.1 at compile time.
- anomaly `column_property(func.length(...))` declared `Mapped[int]` is typed `object` (column python_type wins over annotation); value IS sent when loaded.
- anomaly default `async_sessionmaker(engine)` (expire_on_commit=True) and object stored after commit -> serialized as `{}`, UI silently blank, no log warning (docs warn to use expire_on_commit=False). 0.10.1 raised MissingGreenlet/DetachedInstanceError instead.
- anomaly sync `rx.session()` + lazy load inside the session: only relationships touched before close are sent (row 1 `| alice`, rows 2-3 `|`). Consistent with "never runs a query".
- F6 (LOW, docs) tables.md custom serializer example `dataclasses.asdict(post)` fails for any model with a relationship: DetachedInstanceError (relationship not loaded) or RecursionError (back_populates cycle loaded). `probe_legacy_ser.py`.
- DOC-06 recheck: `rx.asession()` without `async_db_url` -> `ValueError No async database url configured`; overview.md now documents `async_db_url` in Connecting and steers away from rx.asession -> changed/addressed.

### PASS: reflex-local-auth + Base blog e2e (`drive_localauth.py`, variant `localauth_rw`, dev)
Register `zed`, login, then the Base/async blog page renders; rows in localuser + localauthsession. No errors.

## Step 5 — AdminDash (#7739)
- `probes/admindash/p.py` (cwd `probes/admindash`): `rx.AdminDash(models=[Thing])`, `rx.AdminDash()`, `rx.App(admin_dash=...)` all raise
  `reflex_base.utils.exceptions.AdminDashRemovedError: The built-in admin dashboard (rx.AdminDash, rx.App(admin_dash=...)) was removed. Mount starlette-admin yourself with api_transformer: https://reflex.dev/docs/database/admin-dashboard/`
  at construction (import time). `rx.App(admin_dash=None)` OK. 0.10.1: works. (reflex.dev unreachable from this sandbox: link not verified live.)
- Docs recipe (`apps/adminapp`, blog Base models, starlette-admin 1.0.3, `ADMIN_SECRET_KEY=k3y run.sh db_models-up .../adminapp <log> dev`, `drive_admin.py http://localhost:8140 http://localhost:3140 admin_dev`):
  login, Author/Post list with relationships and JSON: PASS; reflex app still serves: PASS.
  - F7 (LOW, docs) docs leave `MyAuthProvider` undefined; my first attempt with the older starlette-admin signature (`login(..., request, response)`, `is_authenticated`) crashed with
    `TypeError: MyAuthProvider.login() missing 1 required positional argument: 'response'` -> current starlette-admin 1.0 API is `login(username, password, remember_me, request)`, `authenticate(request) -> AdminUser|None`, `logout(request)`.
  - F8 (MEDIUM, docs) "New Tag" in the admin -> HTTP 500 `TypeError: __init__() missing 1 required positional argument: 'name'`: starlette-admin instantiates `Model()` without args, which
    `MappedAsDataclass` models (the docs' recommended base) reject. The admin docs example silently uses a `SQLModel` model instead. Listing/reading works.
  - F9 (LOW, regression vs rx.AdminDash) `GET /admin` (no slash) -> 404 through `api_transformer`; 0.10.1 `rx.AdminDash` -> 307 to `/admin/`. Docs: "existing links keep working".
    `probes/probe_admin_slash.py`: plain Starlette 307, via `rx.App(api_transformer=...)` 404 on BOTH 0.10.1 and 0.11 (composition drops redirect_slashes).
  - benign: starlette-admin pages load `https://rsms.me/inter/inter.css` (blocked by sandbox proxy).

## Step 6 — deprecated helpers from user code (`repros/deprecated_helpers.py`, cwd = copy of the 0.10.1 project `deprec/`, legacy env.py)
`cd $SB/apps/db_models/deprec && $SB/envs/db_models-up/bin/python -I ../repros/deprecated_helpers.py envs/db_models-up`
- `get_migration_history()` -> `('5962b6935088', [base, head])` + "reflex.model.get_migration_history has been deprecated in version 0.11.0. Run `alembic history --indicate-current` or `reflex db status`. It will be completely removed in 1.0.0. (<user file>:17)" PASS
- `format_revision` works (expects chronological iteration), warning points at user line. PASS
- `alembic_autogenerate(conn, "noop")` -> upgrades legacy env.py ("Updated env.py ... env.old" at WARNING), returns False, no revision. PASS
- `rx.Model.alembic_autogenerate(conn, "extra table")` with a new rx.Model -> revision written, returns True. PASS
- PKG-15 (rx.Model deprecation location points into pydantic `_model_construction.py:133`): still present in 0.11.0a1 (seen in every `reflex db` / `reflex run` output).
- `reflex db makemigrations` with no change prints nothing (same on 0.10.1; not new).

## Baseline: the rewritten (Base/async) app on 0.10.1
`snap_blog_rw` with the 0.10.1 env.py on `db_models-old`: index renders no posts, server `sqlalchemy.orm.exc.DetachedInstanceError: Parent instance <Author ...>` — the documented 0.11 pattern
has no working 0.10.1 equivalent (#7756 is what makes it work). `logs/rewrite_on_0101_detached.log`.
