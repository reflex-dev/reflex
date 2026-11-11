# db_upgrade — reflex-examples DB apps, 0.10.1 -> 0.11.0a1 in place (PR #7742 alembic env.py)

## Status / resume here
- [x] venvs built: `$SB/envs/db_upgrade-{fd,chat,crud,tw}` = `reflex[db]==0.10.1` + app requirements, constrained to `$SB/envs/prev` freeze (`freeze/prev-constraints.txt`), no `--prerelease`.
- [ ] form-designer baseline / upgrade / orders / combos
- [ ] chat_v2
- [ ] basic_crud
- [ ] twitter
- [ ] report

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
