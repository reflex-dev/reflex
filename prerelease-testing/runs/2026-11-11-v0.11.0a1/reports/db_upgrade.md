CLUSTER: db_upgrade
SUMMARY: All four reflex-examples DB apps (form-designer, chat_v2, basic_crud, twitter) were built on 0.10.1, driven in Chromium to create real data, then upgraded in place to 0.11.0a1. The upgrade is clean in both orders (`reflex run` first, or a `reflex db` command first): the stock env.py is swapped for the template, env.old is byte-identical to the old file, alembic.ini and versions/ are untouched, no data is lost, `makemigrations` on unchanged models writes no revision, and the alembic CLI works afterwards. Dev, prod and cold runs match the baseline, and new columns migrate correctly. One HIGH regression: an env.py edited by hand so that it no longer contains `target_metadata = None` is now kept and executed. With the stock alembic.ini URL, `reflex run` then dies at startup and every `reflex db` command fails with a raw traceback.
ARTIFACTS: /home/user/reflex/prerelease-testing/runs/2026-11-11-v0.11.0a1/db_upgrade/ (NOTES.md, scripts/, apps/, combo/, revisions/, logs/, freeze/, shots/)
TESTS:
- [pass] venvs: db_upgrade-{fd,chat,crud,tw} = reflex[db]==0.10.1 + requirements, constrained to the prev freeze, no --prerelease; in-place `uv pip install -U reflex[db]==0.11.0a1 --prerelease=allow` moves only reflex/base/core/code/radix (0.11.0a1), lucide 1.1.2a1, hosting-cli 0.2.2a1, redis 7.4.1->8.2.0b1, +aiosqlite 0.22.1; pip check clean
- [pass] form-designer baseline 0.10.1: migrate/status/makemigrations rc 0; bare alembic current/history/check/downgrade rc 1 NoSuchModuleError (placeholder URL, as expected); dev full 18/0/2, entry 14/0/1
- [pass] form-designer order (i) `reflex run` first: import-time rx.model.migrate() logs `Warning: Updated env.py to load the app; the previous one is kept as alembic/env.old.`; no ERROR hint, startup alembic check clean; dev up 12/0/1, entry 14/0/1 = baseline; old rows plus new rows present
- [pass] form-designer CLI after upgrade: status rc 0; makemigrations writes no revision; `alembic check` "No new upgrade operations detected."; `alembic current` 4c92535dbbbd (head); downgrade -1 then upgrade head leaves every table digest unchanged; reflex-local-auth tables produce no autogenerate diff
- [pass] form-designer order (ii) `reflex db status` first: Info message, env.old byte-identical, ini/versions/mako untouched, DB dump identical to baseline; migrate/makemigrations/init rc 0
- [pass] form-designer prod (single port): routes 200/404/307 as expected; drives up 11/1/1 (the FAIL: LocalStorage auth on another origin, test artifact) and entry 15/0/0; cold rebuild gives identical package.json and file list
- [pass] form-designer add columns (str default + datetime default_factory): revision has `import sqlmodel`, batch_alter_table and server_default for both; migrate backfills; app works
- [pass] chat_v2 (LLM stub `AI_PROVIDER=qa_stub`, see NOTES): order (i) shows the ERROR hint "created by an earlier Reflex release ... Run reflex db init", skips the schema check and does not change env.py; the app works. Order (ii) `reflex db migrate` first replaces env.py with data intact. Dev, prod and cold match the baseline; new columns migrate fine
- [pass] basic_crud (api_transformer FastAPI): `reflex db init` on 0.10.1, then upgrade. Order (ii) `makemigrations` first writes no revision (the unique constraint and func.now() server defaults produce no spurious diff). UI plus direct HTTP CRUD passes in dev, prod (single port) and cold. Moving env.py aside and running `reflex db init` writes the template
- [pass] twitter (composite-PK join table): order (ii) `reflex db init` first updates env.py and stops. Add-column revision, then downgrade -1 restores the 0.10.1 dump exactly and upgrade head restores the migrated dump. Dev, prod and cold pass. A DB behind head gives the same "not up to date" hint as 0.10.1
- [pass] lazily imported model (page-only import) with stateful_pages.json present: 0.10.1 makemigrations misses it, 0.11 creates the table; afterwards bare `alembic check` and `alembic revision --autogenerate` are no-ops and the startup check prints no warning (bugfix verified)
- [pass] ALEMBIC_CONFIG=conf/alembic.ini works on both versions; 0.11 updates env.py and `alembic -c conf/alembic.ini current` works
- [pass] deprecated helpers (get_migration_history, format_revision, alembic_autogenerate, rx.Model.*) still work and warn "deprecated in version 0.11.0 ... removed in 1.0.0"; alembic_autogenerate replaces a legacy env.py with a WARNING
- [pass] db_url unset: status/migrate/makemigrations exit 1 with a clear message (0.10.1: ValueError traceback); not initialized exits 1 (0.10.1: rc 0)
- [pass] import-time migrate() inside `reflex db migrate`: debug log "Skipping alembic upgrade head: an alembic run is loading the app", one upgrade only
- [pass] prod --backend-only + Redis + GRANIAN_WORKERS=4 from a legacy env.py, 3 runs: no race, one replacement, 0 tracebacks
- [pass] fresh clone with no DB, `reflex run --env prod`: DB created at head, full flow 18/0/2
- [pass] rollback to 0.10.1 after the upgrade: reflex db/run work; only bare alembic fails (ModuleNotFoundError reflex.utils.migrations), expected
- [pass] dev hot reload adding a column, then makemigrations + migrate while the server runs: no lock errors, app works
- [fail] hand-edited env.py H1 (`target_metadata = SQLModel.metadata`, stock alembic.ini): 0.11 `reflex run` crashes at startup and reflex db commands traceback; 0.10.1 is fine (ISSUE 1)
- [anomaly] H2 (H1 + a working sqlalchemy.url): 0.11 makemigrations writes an empty `pass` revision on every call; 0.10.1 wrote none (ISSUE 2)
- [anomaly] H3 / upgrading twice: env.old is overwritten without warning (ISSUE 3)
- [anomaly] from a subdirectory, 0.11 says "db_url is not configured in rxconfig.py" when no rxconfig.py exists (status/migrate/init); makemigrations still raises the 0.10.1 RuntimeError traceback
- [anomaly] `reflex db init` with db_url unset exits 0 (same on 0.10.1), unlike the other subcommands; `makemigrations` with no change and `migrate` print nothing (both versions)
- [anomaly] 0.11 writes .web/package.json as compact JSON (semantically identical) and adds utils/client_state.js and utils/helpers/set.js; the new blocking monitor warns on reflex-local-auth's bcrypt login (accurate)
- [anomaly] pre-existing app issues on both versions: chat_v2 naive-datetime ValueError with sqlmodel 0.0.48 (patched to proceed); fresh `reflex db init` of form-designer fails because page evaluation queries localuser before the tables exist
- [skipped] chat_v2 real LLM providers (no network): stubbed instead
REVERIFIED:
- TP-05: still-broken — form-designer login does not auto-redirect away from /login (anomaly on both versions). The FormMessage crash was not re-checked because FD_FIX_FIELD_NAME=1 was set
- TP-07: unchanged — basic_crud and twitter still ship no alembic dir (same pinned commit)
ISSUES:
- TITLE: Hand-edited alembic env.py (no `target_metadata = None` line) is now executed; `reflex run` crashes at startup and every `reflex db` command tracebacks
  SEVERITY: high
  REGRESSION: yes
  REPRO: Take a reflex-examples app that ships the stock env.py (chat_v2 or form-designer @ ebe19ff). Edit only the env.py line `target_metadata = None` to `from sqlmodel import SQLModel` / `target_metadata = SQLModel.metadata` and leave alembic.ini alone (placeholder `driver://` URL). On reflex[db]==0.10.1, `reflex db migrate` and `reflex run` work. Upgrade in place to reflex[db]==0.11.0a1 and run `reflex run --frontend-port 3100 --backend-port 8100`: the server dies. `check_schema_up_to_date()` runs `alembic check`, which executes the user's env.py; `engine_from_config` raises `sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:driver`. That is not a CommandError, so nothing catches it. `reflex db status`, `migrate` and `makemigrations` exit 1 with the raw traceback and no hint. With an import-time `rx.model.migrate()` (form-designer), the app import itself fails. The workaround (move env.py aside, run `reflex db init`) works, but nothing points the user to it; `reflex db init` on the kept file only says "Database is already initialized".
  EVIDENCE: db_upgrade/logs/chat-H1-run.server.traceback.log, logs/combo-H1b-run.server.traceback.log, logs/combo-H1-run.server.tail.log, logs/combo-H1-run-010.server.tail.log (0.10.1 UP), logs/combo-H12-010.log vs logs/combo-H12-011.log; env file combo/fd-H1-env.py
- TITLE: A kept user env.py lacks the template hooks, so `reflex db makemigrations` writes an empty revision on unchanged models
  SEVERITY: medium
  REGRESSION: yes
  REPRO: Same edit as above, plus `sqlalchemy.url = sqlite:///reflex.db` in alembic.ini (form-designer copy, combo/fd-H2). On 0.10.1, `reflex db makemigrations` writes nothing. On 0.11.0a1, each call writes `<rev>_.py` with `def upgrade(): pass` (no empty-revision skip, batch mode, server-default rewriter or sqlmodel import). The other commands work.
  EVIDENCE: db_upgrade/logs/combo-H12-011.log (Generating .../33b77d334a84_.py), NOTES.md section H2
- TITLE: A second legacy env.py replacement silently overwrites alembic/env.old
  SEVERITY: low
  REGRESSION: no (new code path)
  REPRO: Start from an env.py with custom edits that still contains `target_metadata = None`. On 0.11, run `reflex db status`: env.py is replaced and env.old holds the edits. Restore the committed stock env.py (`git checkout alembic/env.py`) and run `reflex db status` again: env.old is overwritten with the stock file and the edits are gone. The only output is the Info line.
  EVIDENCE: db_upgrade/NOTES.md section H3; combo/fd-H3/env.py
NOT_COVERED: Postgres or MySQL backends (sqlite only); a read-only app directory where the env.py replacement cannot write (the sandbox runs as root); real LLM providers for chat_v2 (stubbed); data_visualisation (not assigned); Python versions other than 3.12; `alembic upgrade --sql` offline mode; ALEMBIC_INCLUDE_SCHEMAS.
