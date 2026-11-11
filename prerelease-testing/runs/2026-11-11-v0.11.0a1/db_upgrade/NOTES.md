# db_upgrade — reflex-examples DB apps, 0.10.1 -> 0.11.0a1 in place (PR #7742 alembic env.py)

## Status / resume here
DONE (2026-11-11). All four apps baselined on 0.10.1, upgraded in place, both orders, dev+prod+cold, column added; combinations done; every server/redis stopped (ports 3100-3119/8100-8119 free). Report: `../reports/db_upgrade.md`.
Headline: the in-place upgrade of all four reflex-examples DB apps is clean (no data loss, no spurious revision, env.old byte-identical, alembic.ini/versions untouched, alembic CLI works afterwards). One HIGH regression: an env.py that was hand-edited so it no longer contains `target_metadata = None` is now executed, and with the stock alembic.ini URL `reflex run` dies at startup (section "combinations", H1/H1b).

## Setup (how to rerun)
```
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad; W=$SB/apps/db_upgrade
mkdir -p $W; for a in form-designer chat_v2 basic_crud twitter; do cp -r $SB/downloads/reflex-examples/$a $W/; done   # reflex-examples @ ebe19ff00dfe
(cd $W && patch -p1 < <repo>/prerelease-testing/fixtures/upgrade/examples/patches/form-designer_field_view.diff)      # opt-in FD_FIX_FIELD_NAME=1 (pre-existing FormMessage crash)
cp <DEST>/scripts/* $W/scripts/
uv --no-config pip freeze --python $SB/envs/prev/bin/python > $W/freeze/prev-constraints.txt
for k in fd:form-designer chat:chat_v2 crud:basic_crud tw:twitter; do $W/scripts/build_base_venv.sh ${k%%:*} $W/${k#*:}; done
```
Upgrade step (same venv): `cd $SB && uv --no-config pip install --python $SB/envs/db_upgrade-<k>/bin/python --prerelease=allow --only-binary :all: -U 'reflex[db]==0.11.0a1'`
Ports: dev 3100/8100 (one server at a time), prod 3101 single port.

## 1. form-designer (reflex-local-auth 0.5.0, committed alembic: 481d2a7a6d6f -> 4c92535dbbbd, stock env.py, `rx.model.migrate()` at import)
Driver: `scripts/drive_form_designer.py` (fixture driver; persistent Chromium profile `$W/profiles/fd`), server `FD_FIX_FIELD_NAME=1`.
Commands: `scripts/start.sh fd $W/form-designer 3100 8100 <log>`; `$DRV scripts/drive_form_designer.py http://localhost:3100/ $W/shots/fd <tag> full|up|entry $W/profiles/fd <ver>`; `scripts/stop.sh <app> 3100 8100`.

### Baseline 0.10.1 (venv db_upgrade-fd before upgrade)
- `reflex db status` rc 0 (already shows both revisions ✓ even before `migrate`, because importing the app runs `rx.model.migrate()`); `reflex db migrate` rc 0; `makemigrations` rc 0, no file, NO output at all.
- bare `alembic current|history --indicate-current|check|downgrade -1`: rc 1, `sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:driver` (stock env.py + placeholder URL) — as expected, the alembic CLI is useless on 0.10.1.
- dev drive: full 18 pass / 0 fail / 2 anomaly (login auto-redirect, pre-existing), entry 14/0/1 (React DOM-nesting console errors in accordion, pre-existing).
- DB after baseline: field 4, fieldvalue 4, form 1, localauthsession 1, localuser 1, option 4, response 1, alembic_version 4c92535dbbbd. Snapshot `$W/snap/fd-base` (dir incl. .web + db).

### Upgrade (same venv, `uv pip install -U 'reflex[db]==0.11.0a1' --prerelease=allow`)
freeze diff: +aiosqlite 0.22.1, redis 7.4.1->8.2.0b1, reflex/base/core/code/radix -> 0.11.0a1, lucide 1.1.2a1, hosting-cli 0.2.2a1. pip check clean.

### Order (i) `reflex run` first ($W/form-designer, in place)
- Startup log: `Warning: Updated env.py to load the app; the previous one is kept as alembic/env.old.` (from the import-time `rx.model.migrate()`), no ERROR hint, no schema warning (startup `alembic check` clean). PASS.
- env.old sha == 0.10.1 env.py (byte-identical), env.py == template, alembic.ini / versions / script.py.mako untouched.
- dev drive: up 12/0/1, entry 14/0/1 — identical to baseline (same anomalies). Old data + new rows present.
- New-in-0.11 log noise: `Warning: Event handler LoginState.on_submit is blocking the event loop (threshold 0.200s)` with a stack into reflex_local_auth bcrypt.checkpw (#7672 monitor; accurate, benign; anomaly).
- `.web/package.json`: 0.11 rewrites it as single-line compact JSON (0.10.1 pretty-printed); semantically identical. Files added: `utils/client_state.js`, `utils/helpers/set.js`.
- CLI after upgrade: `reflex db status` rc 0 (`alembic history --indicate-current` format); `makemigrations` rc 0 writes NO revision (and prints nothing); `alembic check` rc 0 "No new upgrade operations detected."; `alembic current` = 4c92535dbbbd (head); `alembic downgrade -1` rc 0 (batch drop of `hidden`), all rows kept; `reflex db status` then shows current at 481d2a7a6d6f (import-time migrate() correctly skipped inside env.py); `alembic upgrade head` rc 0; dbdump digests identical before/after the down/up round trip.
- From subdirectory `form_designer/`: `reflex db status|migrate` rc 1 "db_url is not configured in rxconfig.py, so there is no database to migrate." (misleading: there is no rxconfig.py in cwd); `makemigrations` rc 1 traceback `RuntimeError: Cannot get the app module because app_name is not set`; `init` rc 0 "db_url is not configured, cannot initialize."; `alembic current` rc 255 "No 'script_location' key"; `alembic -c ../alembic.ini current` rc 255 "Path doesn't exist: alembic". 0.10.1 control (venv db_upgrade-fd010): status/makemigrations/migrate from subdir all rc 1 with the RuntimeError traceback. -> not a regression; message wording anomaly.
- prod (`--env prod`, single port 3101, REFLEX_API_URL): `/`,`/edit/form/1`,`/form/1`,`/responses/1`,`/ping`,`/sitemap.xml` 200, `/nope` 404, `/login` 307; drive up 11/1/1 (the FAIL = "auth survives" — LocalStorage is per origin and prod runs on another port; not a finding), entry 15/0/0.
- cold (`rm -rf .web`): package.json + .web file list identical to in-place; drive up 12/0/1.

### Order (ii) `reflex db status` first ($W/fd-dbfirst = copy of the 0.10.1 snapshot, upgraded venv)
- `reflex db status`: `Info: Updated env.py to load the app; the previous one is kept as alembic/env.old.` then history; rc 0. Then `migrate` rc 0, `status` rc 0, `makemigrations` rc 0 no file, `reflex db init` rc 0 "Database is already initialized...". env.old byte-identical, alembic.ini/versions/mako untouched, DB dump identical to baseline.

### form-designer: combinations (copies under `$W/combo/`, made from `$W/snap/fd-base` with `cpapp`; CLI runner `scripts/cli_seq.sh <venv-key> <dir> "reflex:db status" "alembic:check" ...`)
- **H1 hand-edited env.py (no `target_metadata = None` line)**: replace that line with `from sqlmodel import SQLModel; import form_designer.models; import reflex_local_auth.user; target_metadata = SQLModel.metadata`, alembic.ini untouched (placeholder `driver://` URL).
  - 0.10.1 (venv db_upgrade-fd010): `reflex db status|migrate|makemigrations` rc 0 (env.py never executed), `reflex run` dev UP, `/` and `/form/1` 200. bare alembic rc 1 (NoSuchModuleError), as with the stock file.
  - 0.11.0a1: env.py is NOT legacy, so it is kept and now executed. `reflex db status|migrate|makemigrations` rc 1 with a raw traceback `sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:driver` (no hint to move env.py aside / run `reflex db init`). **`reflex run` dies at startup** (log `logs/combo-H1-run.server.log`): the import-time `rx.model.migrate()` runs the user's env.py. Variant H1b (same env.py, `rx.model.migrate()` removed) ALSO dies at startup: `check_schema_up_to_date` -> `alembic check` -> env.py -> NoSuchModuleError, which is not a CommandError so it is not caught (`logs/combo-H1b-run.server.log`). => REGRESSION (high).
- **H2** = H1 + alembic.ini `sqlalchemy.url = sqlite:///reflex.db` (a user who made the alembic CLI work on 0.10): 0.10.1: all rc 0, `makemigrations` writes nothing, `alembic check` clean. 0.11.0a1: all rc 0, but `reflex db makemigrations` on unchanged models writes an EMPTY revision `33b77d334a84_.py` (`def upgrade(): pass`) — the user's env.py lacks the template's empty-revision skip; also `render_as_batch`, server-default rewriter and `import sqlmodel` hook are absent. Behaviour change for kept env.py (medium/low).
- **H3** edited env.py that still contains `target_metadata = None` (added `MY_CUSTOM_SETTING = 'keep me'`): replaced by `reflex db status` with only `Info: Updated env.py ...`; env.old == edited file. Then "upgrade twice" (restore the committed stock env.py, as `git checkout alembic/env.py` would, and run `reflex db status` again): replaced again and **env.old silently overwritten** with the stock file -> the custom edit's only backup is gone (low; git has it).
- **ALEMBIC_CONFIG=conf/alembic.ini** (ini moved to `conf/`, `script_location = alembic` relative to cwd): 0.10.1 and 0.11.0a1 both rc 0 for status/migrate/makemigrations; 0.11 updates `alembic/env.py` and `alembic -c conf/alembic.ini current` works (4c92535dbbbd). PASS.
- **Deprecated helpers** (`scripts/probe_deprecated.py`, cwd = app root): 0.11 `get_migration_history`, `format_revision`, `alembic_autogenerate(connection=None, write_migration_scripts=False)`, `rx.Model.get_migration_history`, `rx.Model.alembic_autogenerate` all work and emit `reflex.model.X has been deprecated in version 0.11.0. Run `alembic ...` or `reflex db ...`. It will be completely removed in 1.0.0.`; `alembic_autogenerate` replaces the legacy env.py (WARNING `Updated env.py ...`) and returns False (no diff). PASS.
- **import-time migrate() + `reflex db migrate`** on an empty DB (after `alembic downgrade base`): `REFLEX_LOGLEVEL=debug reflex db migrate` -> `Debug: Skipping alembic upgrade head: an alembic run is loading the app.`; one upgrade; DB at 4c92535dbbbd. `reflex db migrate` prints nothing at all on success (also 0.10.1) — anomaly. `reflex db status` no longer upgrades the DB as a side effect (0.10.1 did, through the app's import-time migrate()).
- **Add columns after upgrade** (Form.description: str = "qa default"; Form.created_at = Field(default_factory=lambda: datetime(2026,1,2,3,4,5))): `makemigrations` wrote `96616a4d36d0_qa_add_form_cols.py` with `import sqlmodel`, `batch_alter_table('form')`, `server_default=sa.text("'qa default'")` and `server_default=sa.text("'2026-01-02 03:04:05.000000'")` (UTCDateTime), nullable=False; `migrate` rc 0, existing row got both defaults; `alembic check` clean; second makemigrations writes nothing; dev drive up 12/0/1, entry 14/0/1. PASS.

## 2. chat_v2 (committed alembic 486580f3ee3b, stock env.py, no import-time migrate, background streaming, rx.session)
- **LLM stub**: `chat_v2/qa_stub.py` (FakeClient, OpenAI-shaped chunks, 50 ms per token, ends with a None delta) selected by `AI_PROVIDER=qa_stub` (patch in `get_ai_client`/`get_ai_model`); every run uses `AI_PROVIDER=qa_stub`.
- **App patch (pre-existing app bug, not reflex)**: `_check_saved_chat_interactions` compares against naive `datetime.datetime.now()`; sqlmodel 0.0.48's UTCDateTime raises `ValueError: Datetime values must have timezone information` on 0.10.1 already (submit shows "An error occurred" toast). Patched to `datetime.now(datetime.timezone.utc)`.
- Driver `scripts/drive_chat_v2.py <url> <out> <tag> <prompt> [expected previous prompts...]`. Its "partial answer visible" check is timing-flaky (FAIL on 0.10.1 base2 too); the ws frames show deltas every ~55 ms on both versions, so streaming works; the full answer is detected ~8 s after submit by the driver polling (same 8.0 s on 0.10.1).
- Baseline 0.10.1: `reflex db status` rc 0 (`[✗] 486580f3ee3b`), `migrate` rc 0, `status` ✓, `makemigrations` rc 0 no file, `alembic current|check` rc 1 NoSuchModuleError. Dev drive base 6/0/1, base2 6/1/1 (flaky partial check). Console: React unknown-prop + "change in the order of Hooks" errors (app, both versions).
- **Order (i) `reflex run` first** (in place): startup log shows the hint (logged at ERROR, rendered without prefix): `The migration environment was created by an earlier Reflex release and cannot load the app. Run reflex db init to update env.py; existing revisions are kept.` Schema check skipped, env.py NOT replaced by `reflex run` (no import-time migrate), app works: dev drives up1/up2 7/1/1 (same flaky partial check), old rows listed, new rows persisted.
- CLI after: first `reflex db status` replaces env.py (env.old byte-identical, ini untouched), `makemigrations` no file, `alembic check` clean, `alembic current` 486580f3ee3b (head), `alembic downgrade -1` drops `chatinteraction` (the only revision creates it: rows gone, expected), `reflex db status` shows not current, `reflex db migrate` recreates, `alembic current` head.
- **Order (ii) `reflex db migrate` first** ($W/chat-dbfirst): `Info: Updated env.py ...`, rc 0; DB dump identical to baseline. Dev 7/1/1, no hint at startup; prod (3101 single port) 8/1/0, no console errors; cold (`rm -rf .web`): package.json + file list identical to the in-place upgrade (0.11 again writes compact package.json, +client_state.js, +helpers/set.js).
- Add columns `rating: int = 0`, `model_name: str | None = None`: revision `902c4c44fb35_qa_rating.py` with `import sqlmodel`, batch_alter_table, `server_default=sa.text('0')` NOT NULL, `AutoString()` nullable; migrate rc 0, existing 4 rows -> rating 0 / model_name NULL; `alembic check` clean; app works (cold run 7/1/1).

## 3. basic_crud (rx.App(api_transformer=FastAPI), sqlmodel `Product` with `unique=True` + `sa_column` server_default=func.now(), rx.session, bg reload loop)
- Driver `scripts/drive_basic_crud.py <fe> <be> <out> <tag> [expected codes...]`: list via on_load, UI query form POST (radix select + textarea + Send -> state handler -> httpx -> FastAPI router on the backend), bg loop refresh, direct HTTP GET/POST/PUT/DELETE `/products`, duplicate code -> 500 (IntegrityError, expected), reload count.
- Baseline 0.10.1: `reflex db status` before init rc 0 ("Database is not initialized..."), `reflex db init` rc 0 (prints alembic's file list + "Please edit ... alembic.ini"; stock env.py from alembic 1.20.1 with `script_location = %(here)s/alembic`, revision f7b66a7a5fbc creates `product` with UniqueConstraint('code') and server_default CURRENT_TIMESTAMP), `migrate` rc 0, `makemigrations` no file. Dev drives 13/0/0 and 15/0/0. DB: 4 products.
- Order (i) `reflex run` first: startup ERROR hint (same text as chat_v2), schema check skipped, env.py not replaced; dev drive 17/0/0 (all 4 old products listed).
- Order (ii) `reflex db makemigrations` first ($W/crud-dbfirst): `Info: Updated env.py ... kept as /abs/path/alembic/env.old` (absolute here, relative `alembic/env.old` for the old-style ini — cosmetic), NO revision written, `alembic check` clean (unique constraint + server defaults produce no spurious diff), `alembic current` f7b66a7a5fbc (head), history ok; env.old byte-identical; ini untouched. Moving env.py aside + `reflex db init` -> `Info: Created .../alembic/env.py from the template. Existing revisions are kept.` rc 0, file == template.
- prod (3101 single port, REFLEX_API_URL): 15/0/0 incl. the FastAPI routes on the single port. cold: package.json / .web file list identical; 15/0/0.
- Add columns `price: float = 9.5`, `notes: str | None = None`: revision with `import sqlmodel`, batch, `server_default=sa.text('(9.5)')` NOT NULL, AutoString nullable; migrate rc 0, old rows price 9.5 / NULL; check clean.
- **Lazy model** (`basic_crud/lazy_model.py` AuditLog imported only inside `audit_page()`; `.web/backend/stateful_pages.json` = `[]` from the earlier run): 0.10.1 `reflex db makemigrations` writes NOTHING (model missed — the pre-existing bug); 0.11.0a1 writes `8376e163c6e7_lazy.py` with `create_table('auditlog')`; after migrate: bare `alembic check` clean, bare `alembic revision --autogenerate` writes no file, `reflex run` startup no "Detected database schema changes", `/audit` 200; after the run rewrote stateful_pages.json, makemigrations still no file. PASS (fix verified).
- **db_url unset** (rxconfig without db_url): 0.10.1 status/migrate/makemigrations rc 1 with raw `ValueError: No database url configured` traceback; 0.11 rc 1 with `db_url is not configured in rxconfig.py, so there is no database to migrate.` PASS. `reflex db init` rc 0 on both ("db_url is not configured, cannot initialize.") — inconsistent with the other subcommands (anomaly, not a regression).
- **Not initialized** (db_url set, no alembic.ini): 0.10.1 rc 0 for status/migrate/makemigrations; 0.11 rc 1 "Database is not initialized. Run reflex db init first." (documented behaviour change; scripts that tolerated rc 0 now fail).

## 4. twitter (sqlmodel Follows composite-PK join table + User + Tweet, rx.session in two state modules)
- Driver: fixture `scripts/drive_twitter.py` + `tw_common.py` (`QA_EXPECT_SESSION=0`: dev `reflex run` wipes `.states` on every version, so users log in again).
- Baseline 0.10.1: `reflex db init` rc 0 (revision 73ea91a2672c: follows/tweet/user), status ✓; dev drive base 21/0/0. DB: follows 1, tweet 3, user 2.
- Order (i) `reflex run` first: startup ERROR hint, schema check skipped; dev drive up 14/0/0 (pre-upgrade passwords/tweets/follows all work, new user + follow).
- Order (ii) `reflex db init` first ($W/tw-dbfirst): `Info: Updated env.py to load the app; the previous one is kept as .../alembic/env.old. Existing revisions are kept.` rc 0 and nothing else runs; second `init` -> "Database is already initialized..." rc 0; makemigrations no file; `alembic check` clean; current 73ea91a2672c (head); env.old byte-identical; ini untouched.
- Add `Tweet.likes: int = 0` -> `e69c084b544e_qa_likes.py` (batch, server_default '0', NOT NULL); migrate; `alembic downgrade -1` -> tweet columns back to 4, dbdump of every table identical to the 0.10.1 baseline; `alembic upgrade head` -> identical to post-migrate dump. PASS.
- DB behind head at `reflex run`: `Target database is not up to date. Run reflex db migrate to update database.` — identical on 0.10.1. PASS.
- tw-dbfirst dev 14/0/0, prod (3101 single port) 12/0/2 (anomalies = `bg.svg` 404s, known-benign app asset), cold 14/0/0 with package.json / file list identical to in-place.


## Other checks
- **Race, prod `--backend-only` + Redis + GRANIAN_WORKERS=4 from a legacy env.py** (`scripts/race_backend_only.sh fd 3`, Redis on 8119): 3/3 runs: 4 workers, /ping 200, env.py == template, env.old == stock, exactly one `Updated env.py` message, 0 tracebacks. PASS.
- **Fresh clone of form-designer with no reflex.db** (`reflex run --env prod`, the "hosting" path the app comments on): import-time migrate() replaces env.py (WARNING) and creates the DB at 4c92535dbbbd; full driver 18/0/2 (pre-existing login anomalies). `reflex db migrate` on a fresh clone: rc 0 on both versions.
- **Fresh `reflex db init` of form-designer with alembic/ removed**: rc 1 on 0.10.1 AND 0.11.0a1 — evaluating the pages queries `localuser` before any table exists (`sqlite3.OperationalError: no such table: localuser`). Pre-existing, app-specific (the repo ships its alembic dir).
- **Dev hot reload adding a model column, then makemigrations + migrate while the server runs** (twitter): reload ok, revision written, migrate rc 0 with the app holding the sqlite file, no "database is locked", drive 14/0/0. A fresh start with an unmigrated column logs `Detected database schema changes...` on both versions; the hot reload itself does not re-run the check (both versions).
- **Rollback to 0.10.1 after 0.11 replaced env.py** (`$W/combo/fd-rollback`, venv db_upgrade-fd010): `reflex db status|makemigrations|migrate` rc 0, `reflex run` works (/form/1 200); only bare `alembic` fails (`ModuleNotFoundError: No module named 'reflex.utils.migrations'`), expected.
- **H1 remedy from the changelog** (move env.py aside, `reflex db init`): `Info: Created alembic/env.py from the template. Existing revisions are kept.`, then status/makemigrations rc 0, no revision. Works — but nothing tells the H1 user to do it (they only get a NoSuchModuleError traceback; `reflex db init` on the kept file says "Database is already initialized").
- Bare `alembic` on a legacy env.py right after the package upgrade (before any `reflex db` command) still fails exactly like 0.10.1 (stock file, placeholder URL) — by design.

## Anomalies (benign but surprising)
- `reflex db makemigrations` with no change and `reflex db migrate` that applies revisions print nothing at all (exit 0); same on 0.10.1.
- `reflex db init` with `db_url` unset exits 0 (error logged) while status/migrate/makemigrations now exit 1; same rc on 0.10.1.
- From a subdirectory (no rxconfig.py in cwd) 0.11 says `db_url is not configured in rxconfig.py` (status/migrate/init) or raises `RuntimeError: Cannot get the app module because app_name is not set` (makemigrations); 0.10.1 raised the RuntimeError traceback for all three.
- The env.old path in the update message is relative (`alembic/env.old`) for old ini files (`script_location = alembic`) and absolute for alembic-1.20 ini files (`%(here)s/alembic`).
- Legacy hint at `reflex run` is printed at ERROR level with no "Error:" prefix (consistent with other reflex errors, e.g. "Target database is not up to date", which looks the same on 0.10.1).
- 0.11 writes `.web/package.json` as compact single-line JSON (0.10.1 pretty-printed); contents identical.
- New #7672 monitor warns `Event handler LoginState.on_submit is blocking the event loop` (reflex-local-auth bcrypt) on every login — accurate, third-party code.
- form-designer `rx.Cookie` client_token is a session cookie (expires -1): a new token per browser session; same on both versions.
- chat_v2 needs an app patch on sqlmodel 0.0.48 (naive datetime) on both versions; React unknown-prop / hook-order console errors (app).

## Issues (repro steps)
### I-1 (HIGH, regression) Hand-edited env.py without `target_metadata = None` is now executed: `reflex run` crashes at startup, every `reflex db` command tracebacks
0.10.x ran `alembic init` but never executed the generated env.py, so editing it (the usual alembic recipe `target_metadata = SQLModel.metadata`) was harmless. 0.11 keeps any env.py that lacks the literal `target_metadata = None` and executes it. With the stock alembic.ini URL (`driver://user:pass@localhost/dbname`), env.py's `engine_from_config` raises `sqlalchemy.exc.NoSuchModuleError`, which is not an alembic `CommandError`, so neither `check_schema_up_to_date()` nor `_alembic_errors()` catches it.
Repro (verified on chat_v2 and form-designer):
```
SB=...; W=$SB/apps/db_upgrade; cp -r $SB/downloads/reflex-examples/chat_v2 /tmp/x && cd /tmp/x     # any app with the committed stock env.py
sed -i 's/^target_metadata = None$/from sqlmodel import SQLModel\ntarget_metadata = SQLModel.metadata/' alembic/env.py
# 0.10.1 venv (reflex[db]==0.10.1 + requirements): reflex db migrate -> rc 0; reflex run -> app works   (verified: $W/combo/fd-H1, venv db_upgrade-fd010)
# upgrade: uv pip install --prerelease=allow -U 'reflex[db]==0.11.0a1'
reflex run --frontend-port 3100 --backend-port 8100   # dies: check_schema_up_to_date -> alembic check -> env.py -> NoSuchModuleError
reflex db status; reflex db migrate; reflex db makemigrations   # rc 1, raw traceback, no hint
```
Evidence: `logs/chat-H1-run.server.traceback.log`, `logs/combo-H1b-run.server.traceback.log`, `logs/combo-H1-run.server.tail.log` (form-designer, import-time migrate() variant), `logs/combo-H1-run-010.server.tail.log` (0.10.1 control UP), `logs/combo-H12-010.log` vs `logs/combo-H12-011.log`. Workaround (works): move env.py aside, `reflex db init`.
Suggested direction (not a fix): catch any exception from the startup schema check and log it with the "move env.py aside and run reflex db init" hint; and/or detect env.py files that do not import `reflex` as "not a reflex env.py".

### I-2 (MEDIUM/LOW, behaviour change) Kept user env.py lacks the template hooks: `reflex db makemigrations` writes an empty revision on unchanged models
H2 = I-1's env.py + alembic.ini `sqlalchemy.url = sqlite:///reflex.db` (a user who made the alembic CLI work on 0.10). 0.10.1 makemigrations: no file. 0.11.0a1: writes `<rev>_.py` with `def upgrade(): pass` every time; no render_as_batch / server_default rewriter / `import sqlmodel` hook either. Evidence `logs/combo-H12-011.log`, `combo/fd-H2/`.

### I-3 (LOW) Second legacy replacement silently overwrites env.old
H3: an env.py with custom edits that still contains `target_metadata = None` is replaced (Info message only) and its only copy is env.old; restoring the committed stock env.py (e.g. `git checkout alembic/env.py`) and running any `reflex db` command replaces again and overwrites env.old with the stock file — the custom edits are gone from the working tree. Evidence: this file, section H3.

## VERIFICATION
Independent verifier `verify_dbu` (2026-11-11), working only from this NOTES.md, `../reports/db_upgrade.md` and `combo/`. Own venvs, built without `--prerelease`: `$SB/envs/vdbu-a` = `reflex[db]==0.10.1` + `reflex-local-auth>=0.5.0`, upgraded in place with `uv --no-config pip install --prerelease=allow --only-binary :all: 'reflex[db]==0.11.0a1'`. That moved reflex/base/core/code/radix to 0.11.0a1 and added aiosqlite; no `-U`, so lucide, hosting-cli and redis stayed put. pip check is clean, and the installed `migrations.py`, `prerequisites.py`, `reflex.py`, `model.py` and template `env.py` are byte-identical to the `v0.11.0a1` tag. `$SB/envs/vdbu-prev` stays at 0.10.1. The app is my own copy of form-designer from `$SB/downloads/reflex-examples` @ ebe19ff. On 0.10.1 I ran it once (the import-time `rx.model.migrate()` creates reflex.db at head), seeded rows with `scripts/dbdump.py seed`, and checked `/form/1` in Chromium. Every variant is a copy of that seeded 0.10.1 app. Scripts: `../verify_dbu/scripts/` (`run_all.sh` = every command below; `common.sh`, `dbdump.py`, `check_page.py`, `railway_style_env.py`). Logs: `../verify_dbu/logs/`. Ports: 3600/8600, all free at the end.

Where this NOTES.md was not enough:
- `/form/1` crashes with the FormMessage error (TP-05) unless both the fixture patch (`prerelease-testing/fixtures/upgrade/examples/patches/form-designer_field_view.diff`, applied with `-p2` inside the app dir) and `FD_FIX_FIELD_NAME=1` in the server env are in place. Setup names the patch, but nothing says it is needed for any page check.
- The I-1 one-liner (`sed` to `target_metadata = SQLModel.metadata` with no model imports) differs from `combo/fd-H1-env.py`, which imports the models. Both crash 0.11 the same way. With the one-liner, bare `alembic check` on a working URL proposes dropping every table, on both versions. Under `reflex db` the app is imported first, so it does not.
- The I-1 repro copies to `/tmp/x` and says "git checkout" for I-3. The example copies are not git repos, so I emulated the checkout by copying the stock env.py back.
- The upgrade line uses `-U`, which also moves redis, lucide and hosting-cli. That is irrelevant here.
- Neither the report nor NOTES gives file:line for the root cause. It is below.

| # | Claim | Verdict | Severity | Regression |
|---|---|---|---|---|
| PASS | stock env.py, `reflex run` first | CONFIRMED pass | — | — |
| I-1 | edited env.py kept and executed: crash | NARROWED | high -> medium | yes |
| I-2 | kept env.py: empty revision on every makemigrations | CONFIRMED, wider than reported | medium | yes (in the docs, not in CHANGELOG) |
| I-3 | second replacement overwrites env.old | CONFIRMED | low | no (new code path) |

**PASS spot check (form-designer, stock env.py, order (i) `reflex run` first): CONFIRMED.** On 0.11, `reflex run` came up in 7 s and logged `Warning: Updated env.py to load the app; the previous one is kept as alembic/env.old.` with no traceback. env.old sha is e6da64f8b84c2b20, byte-identical (`cmp`) to the 0.10.1 env.py. env.py equals the template. alembic.ini, script.py.mako and both versions/ files have unchanged sha. The dbdump of every table equals the seeded 0.10.1 dump. `/form/1` in Chromium renders the seeded field "QA prompt survives upgrade", with no console errors and no 4xx/5xx. `reflex db makemigrations` (twice) writes no revision. `alembic check` reports "No new upgrade operations detected." and `alembic current` is 4c92535dbbbd (head). The DB was still identical after the CLI runs. Evidence: `verify_dbu/logs/pass-011-summary.log`, `shots/pass-011-form1.png`.

**I-1: NARROWED. Severity medium (claimed high). Regression yes.**
- Reproduced exactly. 0.10.1 (prev-h1, prev-h1b): `reflex db status|migrate|makemigrations` rc 0 and `reflex run` UP, `/form/1` PASS. Bare `alembic check` rc 1 NoSuchModuleError (`logs/prev-H12-cli.log`).
- 0.11.0a1, fd-h1b (no import-time migrate): `reflex run` exits after 6 s. The traceback runs `compile_or_validate_app -> get_compiled_app:344 -> check_schema_up_to_date:879 -> migrations.run -> alembic check -> env.py:61 engine_from_config -> NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:driver`.
- fd-h1 (import-time migrate) exits after 3 s with the same error, raised through `rx.model.migrate()`.
- `reflex db status|migrate|makemigrations`: rc 1 with a raw traceback and no hint. `reflex db init`: rc 0, "Database is already initialized...". Evidence: `logs/fd-h1b-run-011.traceback.log`, `logs/fd-h1-run-011.traceback.log`, `logs/H1-cli-011.log`.
- The remedy works: move env.py aside, `reflex db init` ("Created alembic/env.py from the template"), then status and makemigrations rc 0 with no revision, `reflex run` UP and `/form/1` PASS (`logs/H1-remedy.log`).
- Why narrowed, part 1: the exact trigger is a half-finished edit, a new `target_metadata` with the `driver://` placeholder URL left in place. That is a state in which the user's own `alembic` CLI never worked on 0.10.1, and on 0.10.1 nothing in reflex ever read the file.
- Plausibility, docs: neither the reflex-examples clone (chat_v2 and form-designer ship the stock file) nor the v0.10.1 docs (`docs/database/*.md` never mention env.py) tell users to edit env.py. The v0.11.0a1 docs (`docs/database/overview.md:180-190`) document that a hand-edited env.py without the literal is kept. reflex-local-auth 0.5.0 gives no alembic guidance.
- Plausibility, in the wild: a GitHub code search found public Reflex apps that hand-edited `alembic/env.py`: reflex-dev/reflex-railway (reflex-dev's own template, pins `reflex[db]==0.10.0`), neggles/aptreader, Yh0x1n/kakumi-app, haremir/my-portfolio and mdub187/Reflex-Repo. None of the five contains `target_metadata = None`, so 0.11 keeps and runs all of them. All five set a working URL (rxconfig `db_url`, an env var/`rxconfig` import, or a real `sqlalchemy.url`), so none would hit this crash.
- Why narrowed, part 2: they all hit I-2 instead. Real users with edited env.py files do exist, but the crash needs the rare half-edit, or some other exception from the user's file (import error, missing env var, unreachable ini URL).
- Root cause, detection: `reflex/utils/migrations.py:188` (`is_legacy_env`) decides "legacy" only by the literal `"target_metadata = None"`. Any edited 0.10-era env.py counts as reflex-ready and is executed, even though 0.10.x never executed env.py (0.10.1 `model.py:442-449` drove `EnvironmentContext` itself with `ModelRegistry.get_metadata()` and `get_engine()`).
- Root cause, `reflex run`: `reflex/utils/prerequisites.py:878-888` (`check_schema_up_to_date`) catches only `AutogenerateDiffsDetected`/`CommandError`. The exception reaches `compile_or_validate_app` (`prerequisites.py:434-442`), which prints it and returns False, and `reflex/reflex.py:391` raises `SystemExit(1)`.
- Root cause, `reflex db`: `reflex/reflex.py:1113-1131` (`_alembic_errors`) also catches only `CommandError`.
- Root cause, import-time `migrate()`: `reflex/model.py:432-434` runs `upgrade head` through the same file.
- Suggested fix, minimal: in `check_schema_up_to_date` and `_alembic_errors`, catch any exception raised while alembic runs env.py and log it with a hint ("alembic/env.py failed: <err>. If it predates Reflex 0.11, move it aside and run `reflex db init`"). `reflex run` should not die on a failed schema check.
- Suggested fix, broader: treat an env.py that does not use the template hooks (`reflex.utils.migrations` `load_app`/`invoked_by_reflex`) as foreign. Warn once naming the missing behaviour and the remedy, without replacing the file. The minimal fix does not rescue an import-time `migrate()` (form-designer H1). Only the hint or broader detection helps there.

**I-2: CONFIRMED, wider than reported. Severity medium. Regression yes; the docs cover it, the CHANGELOG does not.**
- fd-H2 (H1 env.py plus `sqlalchemy.url = sqlite:///reflex.db`) on 0.11: each `reflex db makemigrations` writes a new `<rev>_.py` whose upgrade and downgrade are only `pass` (14b708f1634a, then 417e86bb3e77). status and migrate rc 0. On 0.10.1 (prev-h2), makemigrations writes nothing. Evidence: `logs/H2-011.log`.
- Reproduced with a **reflex-railway-style env.py** (`scripts/railway_style_env.py`: rxconfig `db_url`, `SQLModel.metadata`, `render_as_batch`). On 0.10.1, makemigrations twice gives 0 new files. On 0.11.0a1 it gives 2 empty revisions. `reflex run` works on both. Evidence: `logs/railway-style.log`.
- Amplifier, new evidence: `rx.model.migrate(autogenerate=True)` at import plus the H2 env.py. One dev `reflex run` start writes **3 empty chained revisions** on 0.11 (0d2f522b7733 -> c9b1562f0e72 -> d7ae4389252c, one per app import) and 0 on 0.10.1. Control: the same app with the template env.py writes 0. Evidence: `logs/H2-autogen-import.log`, `variants/H2-empty-revision-example.py`.
- Real-world relevance: all five public edited env.py files found for I-1 fall into this case.
- Root cause: `reflex/reflex.py` `makemigrations` (around line 1228) and `reflex/model.py:435-437` (`migrate(autogenerate=True)`) run a bare `alembic revision --autogenerate`. The empty-revision skip now lives only in the template's `process_revision_directives`, so a kept env.py loses it. The deprecated `alembic_autogenerate` still does `check`, then `revision`.
- Suggested fix: run `alembic check` first in `makemigrations` and in `migrate(autogenerate=True)`, and write a revision only on `AutogenerateDiffsDetected`, as 0.10.1 and `alembic_autogenerate` did. That keeps 0.10.1 behaviour for any env.py at the cost of one extra env.py run. Also add a CHANGELOG line for kept env.py files.

**I-3: CONFIRMED. Severity low. Regression no (new code path).**
- fd-h3 (stock env.py plus `MY_TEAM_HOOK = "keep me"`, still containing `target_metadata = None`). The first `reflex db status` prints `Info: Updated env.py ...`, and env.old (sha 9c737ca30ce9ad0c) contains the edit.
- After the stock env.py is restored (the `git checkout alembic/env.py` equivalent), a second `reflex db status` prints the same Info line. env.old becomes e6da64f8b84c2b20 (stock) and `MY_TEAM_HOOK` is gone from the tree. Evidence: `logs/H3-011.log`.
- Root cause: `reflex/utils/migrations.py:200-201`, where `env_py.replace(backup)` overwrites unconditionally. Low, because the loss needs edits that did not remove the literal plus a second legacy file, and VCS usually still has them.
- Suggested fix: when env.old exists and differs, pick a free name (env.old.1, ...) or log a warning that names the overwritten file.

NOT re-run: chat_v2 (form-designer covers both the import-time-migrate and the no-migrate path); prod multi-worker with `migrate(autogenerate=True)` (could race to multiple heads; untested); dev hot reload with `migrate(autogenerate=True)` (probably one more empty revision per reload; untested).
