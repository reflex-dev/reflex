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

## VERIFICATION
Independent adversarial verifier (`verify_dbm`), 2026-11-11. Fresh venvs, PyPI only, cwd always under `$SB/apps/verify_dbm/`:
- `cd $SB && uv --no-config venv $SB/envs/vdbm-new --python 3.12 && uv --no-config pip install --python $SB/envs/vdbm-new/bin/python --prerelease=allow --only-binary :all: 'reflex[db]==0.11.0a1' starlette-admin`
  (reflex/reflex-base 0.11.0a1, sqlalchemy 2.1.8, sqlmodel 0.0.48, alembic 1.20.1, starlette-admin 1.0.3, aiosqlite 0.22.1)
- `cd $SB && uv --no-config venv $SB/envs/vdbm-prev --python 3.12 && uv --no-config pip install --python $SB/envs/vdbm-prev/bin/python --only-binary :all: 'reflex[db]==0.10.1' starlette-admin` (no --prerelease)
Scripts (all self-contained, no snapshots needed): `/home/user/reflex/prerelease-testing/runs/2026-11-11-v0.11.0a1/verify_dbm/`; captured outputs in its `out/`.
Servers: backend-only on 8640-8644, each process group killed afterwards.

| # | Claim | Verdict | Severity | Regression | Root cause (v0.11.0a1) |
|---|---|---|---|---|---|
| 1 | Unregistered DeclarativeBase -> makemigrations writes drop_table for every table, migrate drops all data, startup hint says "run makemigrations" | CONFIRMED | high (fix before 0.11.0 final; not an alpha blocker) | no (0.10.1 identical) | `reflex/model.py:258-272` `get_metadata()` returns a fresh empty `MetaData()` when no registered model has tables (the `len(models)==1` branch is skipped, the merge loop adds nothing); `reflex/.templates/alembic/env.py:59` passes it as `target_metadata`, which defeats alembic's own "env.py does not provide a MetaData object" refusal (alembic/autogenerate/api.py:375). Hint: `reflex/utils/prerequisites.py:880-884`. |
| 2 | JSON column on DeclarativeBase model typed `object`; `State.m.d["city"]` compile TypeError | CONFIRMED (broader: also `Mapped[list[str]]` JSON, and plain non-dataclass DeclarativeBase) | medium | no (0.10.1 identical) | `packages/reflex-base/src/reflex_base/utils/types.py:1079-1098`: the column's `type.python_type` (`object` for `sa.JSON`) is returned without consulting the `Mapped[...]` annotation. |
| 3 | `default_factory` column on non-empty table -> no server_default -> NOT NULL migrate failure; leftover `_alembic_tmp_*` breaks next migrate | CONFIRMED, NARROWED on two points | medium | no (0.10.1 identical) | `reflex/.templates/alembic/env.py:82-86` only reads `op.column.default`; a MappedAsDataclass `default_factory` is dataclass-only (SQLAlchemy design: `Column.default is None`). `_alembic_tmp_*` leftover is alembic batch mode on SQLite (non-transactional DDL), only when the revision rebuilds the table. Docs (tables.md:40-42) mention default_factory as an option for optional fields, they do not recommend it for columns specifically. New fact: rx.Model `Field(default_factory=...)` DOES set `Column.default` and migrates fine, so the documented rewrite turns a working migration into a failing one. |
| 4 | Same table in two registered metadatas -> compared definition random per process | CONFIRMED, NARROWED (not silent) | low | no (0.10.1 identical) | `reflex/model.py:204` `models` is a `set` (iteration order = id hash, varies per process) + `model.py:267-269` `table.to_metadata(metadata)` keeps the first copy. Every run prints `SAWarning: Table 'post' already exists within the given MetaData - not copying.` pointing at model.py:269, so the user is told; the non-determinism is reflex's. |
| 5a | Admin "New <Model>" 500 with MappedAsDataclass | CONFIRMED, RECLASSIFIED (upstream starlette-admin + docs gap) | low | no (0.10.1 `rx.AdminDash` 500s identically) | starlette-admin 1.0.3 `contrib/sqla/view.py:581/588` calls `self.model()` with no args; reflex code is not involved. Docs example (admin-dashboard.md) uses a SQLModel model and never mentions the dataclass limitation; `MyAuthProvider` is undefined. |
| 5b | `/admin` (no slash) 404 via api_transformer; 0.10.1 rx.AdminDash redirected 307 | CONFIRMED, NARROWED (docs inaccuracy, not a code regression) | low | only vs the removed feature; `api_transformer` composition is identical on 0.10.1 (also 404) | `reflex/app.py:1000` `api_transformer.mount("", asgi_app)`: the catch-all Mount matches `/admin` before Starlette's `redirect_slashes` can run, so reflex's app answers 404. 0.10.1 rx.AdminDash mounted on reflex's own router (`app.py:1522` at v0.10.1). Docs sentence "existing links keep working" is false for `/admin`. |

### 1. Unregistered DeclarativeBase -> drop_table (CONFIRMED, high, not a regression)
`bash verify_dbm/v1_noregister.sh vdbm-new` / `vdbm-prev` (two-table Base app, `reflex db init`, one row per table, delete the `rx.ModelRegistry.register(Base)` line):
- both versions: `makemigrations rc=0`, no warning, revision `op.drop_table('user')` / `op.drop_table('post')`; `migrate rc=0`; `tables after ['alembic_version']`. (`out/v1.out`)
- hint: with no pending revision, `reflex db migrate` (runs the same `check_schema_up_to_date()` as `reflex run`'s compile) prints
  "Detected database schema changes. Run reflex db makemigrations to generate migration scripts." The 0.10.1 code prints the same hint (`git show v0.10.1:reflex/utils/prerequisites.py` 868-871).
  Note: `reflex run --backend-only` does NOT run the check (only the compile path does).
- `v1b_noregister_mixed.sh vdbm-new` (extra `rx.Model` table, as with reflex-local-auth): only the Base tables are dropped, `legacy` survives -> an "empty metadata" guard alone would not cover that case.
- fresh project with the line missing: `reflex db init` rc 0, no revision written, DB has only `alembic_version`, no warning (the runtime later fails with "no such table", so less dangerous).
- Docs: overview.md (line 14 summary bullet, code sample line 124, sentence 135-137) and tables.md (23, 37-38) DO show and explain `register(Base)`; nothing says what happens without it. overview also says "It is recommended that they be inspected before applying them." So this is API misuse the docs warn against only implicitly, but the consequence (silent total data loss, with the startup hint steering the user to the command that writes it) is disproportionate and cheaply detectable:
  (a) `ModelRegistry.get_metadata()` returning an empty MetaData, or env.py seeing `not target_metadata.tables` while the DB has tables -> refuse autogenerate (alembic itself refuses when `target_metadata is None`; reflex's empty MetaData bypasses that);
  (b) after `load_app`, walk `DeclarativeBase.__subclasses__()` for bases with tables whose metadata is not registered and warn/raise (covers the mixed case);
  (c) a docs callout.
- Severity: HIGH. Release-blocker call: not a blocker for the alpha (identical on 0.10.1, documented), but should be fixed before 0.11.0 final because 0.11 makes DeclarativeBase the only documented path and rx.Model needed no registration, so every migrating user gains a new one-line step whose omission silently deletes data.

### 2. JSON column typed `object` (CONFIRMED, medium, not a regression)
`cd $SB/apps/verify_dbm/neutral && $SB/envs/vdbm-new/bin/python -I verify_dbm/v2_json_types.py $SB/envs/vdbm-new` (prev: add `--no-plain`; 0.10.1 cannot hold a non-dataclass DeclarativeBase in state at all). `out/v2.out`:
`Mapped[dict]`, `Mapped[dict | None]`, `Mapped[list[str]]` with `mapped_column(JSON)` -> `object` / `object | None`; `S.mm.d['city']`, `S.mm.l[0]` -> `TypeError: Var of type <class 'object'> does not support item access.` on both versions; also on a plain (non-dataclass) DeclarativeBase on 0.11. rx.Model `dict` + `Column(JSON)` -> `dict`, item access OK. Workaround `.to(dict)` works.
Root cause `reflex_base/utils/types.py:1079-1098` (column `python_type` wins over the `Mapped[]` annotation; for `object` it should fall back to the annotation, as the sqlmodel branch at 1118-1131 does).

### 3. default_factory column (CONFIRMED, NARROWED, medium, not a regression)
`bash verify_dbm/v3_default_factory.sh <vdbm-new|vdbm-prev> <df|dfbatch|dflt|ins|rxdf>` (`out/v3.out`, `out/v3b.out`), one existing row, add NOT NULL `score`:
| variant | Column.default | revision | migrate |
|---|---|---|---|
| df `mapped_column(default_factory=lambda: 7)` | None | `add_column(... nullable=False)` | rc 1 `Cannot add a NOT NULL column with default value NULL` (no tmp table) |
| dfbatch (df + `name` made nullable -> table rebuild) | None | same | rc 1 `NOT NULL constraint failed: _alembic_tmp_item.score`; `_alembic_tmp_item` left; next migrate `table _alembic_tmp_item already exists` |
| dflt `mapped_column(default=7)` | Scalar(7) | `server_default=sa.text('7')` | rc 0, row gets 7 |
| ins `mapped_column(insert_default=7, default_factory=lambda: 7)` | Scalar(7) | `server_default=sa.text('7')` | rc 0 |
| rxdf rx.Model `Field(default_factory=lambda: 7)` | Callable | `server_default=sa.text('7')` | rc 0 |
Identical on 0.10.1. Narrowing: (a) tables.md 40-42 only mentions `default_factory` as one way to give a dataclass field a default (ordering rule); it does not single it out for columns. (b) the `_alembic_tmp_*` leftover is alembic batch-mode behaviour on SQLite and appears only when the revision rebuilds the table. Not refuted: the rx.Model->Base rewrite the docs prescribe turns a working `Field(default_factory=...)` migration into a failing one. Root cause `reflex/.templates/alembic/env.py:82-86` reads only `op.column.default`; fix options: map the column back to its dataclass field's `default_factory` in the hook, or document `insert_default=` / scalar `default=` for columns.

### 4. Same table in two metadatas (CONFIRMED, NARROWED to low, not a regression)
`bash verify_dbm/v4_dup_table.sh vdbm-new 8` / `vdbm-prev 8` (`out/v4b.out`): DB from rx.Model `post(id,title)`, then a registered Base `post` with an extra column, both modules imported.
0.11 `alembic check` x8: `add_column add_column clean add_column clean clean add_column add_column` (earlier x10: 3 clean / 7 add_column); `makemigrations` x8 `REV none REV none none none none none`; 0.10.1 makemigrations x8 `none none REV REV none REV REV none`.
Not silent: every run (both versions) prints `reflex/model.py:269: SAWarning: Table 'post' already exists within the given MetaData - not copying.` Reflex-side cause is the non-determinism: `model.py:204` `models: ClassVar[set[...]]` + `267-269` first copy wins. Fix: insertion-ordered registry and raise on a conflicting duplicate table.

### 5. Admin dashboard (5a RECLASSIFIED upstream/docs; 5b NARROWED docs; both low)
App `verify_dbm/admin_app` (MappedAsDataclass `Tag` + SQLModel `Label`, `api_transformer` recipe, no auth for the test); `bash verify_dbm/v5_admin.sh <venv> <appdir> <port>`:
| run | GET /admin | POST /admin/tag/create (dataclass) | POST /admin/label/create (SQLModel) |
|---|---|---|---|
| 0.11 api_transformer | 404 | 500 `TypeError: __init__() missing 1 required positional argument: 'name'` | 303 |
| 0.10.1 api_transformer | 404 | 500 same | 303 |
| 0.10.1 `rx.AdminDash(models=[Tag, Label])` | 307 -> /admin/ | 500 same | 303 |
5a: starlette-admin `contrib/sqla/view.py:581,588` `self.model()`, so any required-arg dataclass model fails on every reflex version; reflex code is not involved. Docs gap only: the guide's example uses a SQLModel model and says nothing about MappedAsDataclass (and `MyAuthProvider` is never defined).
5b: `reflex/app.py:1000` `api_transformer.mount("", asgi_app)` catch-all matches `/admin` before Starlette's `redirect_slashes`. Same composition on 0.10.1 (`app.py:854`); the old dashboard was mounted on reflex's own router (v0.10.1 `app.py:1522`). The regression is only against the removed feature, and the docs' "existing links keep working" is wrong for the bare `/admin` URL. Fix: correct the docs (link to `/admin/`, or add a `Route("/admin", RedirectResponse("/admin/"))` to the recipe).

### Repro quality (NOTES.md as written)
- F1 `probe_types.py` and F2 `repro_default_factory.sh` are self-contained and sufficient (the verifier read them and ran its own broader equivalents, v2/v3, with the same results). repro_default_factory's simple case gives the ALTER TABLE error, not the `_alembic_tmp` one; the leftover table needs a table rebuild, which NOTES attributes to the blog app without saying so.
- F3/F5 (`variant.sh` + `v_noregister.py` / `v_dup.py`) depend on `$SB/apps/db_models/snap_blog_rw` / `snap_blog_011up`, which are not in the artifacts under those names; NOTES says how to rebuild them (copy apps/blog, delete one revision, strip three columns, re-migrate), which is manual and error-prone. The verifier's v1/v4 scripts build from nothing.
- F3's startup-hint claim only shows on the compiling `reflex run` path (or `reflex db migrate`), not `--backend-only`; NOTES did not say so.
- F8/F9 need a full `reflex run` + Playwright + an auth provider in the reporter's version; curl against a backend-only run is enough (`v5_admin.sh`).
