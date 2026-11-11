# reflex-examples survey (for 0.10.1 -> 0.11.0a1 in-place upgrade test)

Read-only survey. Nothing was run inside /home/user/reflex.

## Source

- Repo: https://github.com/reflex-dev/reflex-examples (shallow clone)
- Clone: `/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/downloads/reflex-examples`
- HEAD: `ebe19ff00dfee36f9d67a9a584840c6745950b05`
  (same commit the prerelease fixtures pin in `prerelease-testing/fixtures/upgrade/bin/stage.sh`)
- Previous passes (fixtures README): form-designer, github-stats, twitter (+ twitter-redis), clock, counter,
  reflexle, lorem-stream, local-component, quiz, snakegame, nba, upload, plus json-tree / traversal /
  todo legacy drivers. Not previously exercised by the fixtures: **basic_crud, chat_v2, overkey,
  data_visualisation, azure_auth, linkinbio, translator, dalle, flux-fast, ag_grid_finance, nba-proxy,
  todo**. Those are the gaps to weigh.

## Version pinning

- No app pins reflex. Every `requirements.txt` uses a floor: `reflex>=0.9.2` (or `reflex[db]>=0.9.2`).
- No app has a `pyproject.toml`. Each app has `rxconfig.py` and `requirements.txt`.
- So the "pinned version" for an example is whatever the venv resolves. The 0.10.1 base has to be installed
  explicitly (`reflex==0.10.1`), and the upgrade step is `reflex[db]==0.11.0a1` (alpha needs `--prerelease=allow` under uv).
- Third-party pins that matter for the venv: `reflex-local-auth>=0.5.0` (form-designer), `reflex-global-hotkey>=1.2.2`
  (reflexle), `reflex-enterprise>=0.0.2` (ag_grid_finance).

## Database and migrations

- `rx.Model`: **zero hits** in the repo. All DB apps use `sqlmodel.SQLModel` with `table=True`.
- `rx.session()` is used (sync). `rx.asession` / `sqlalchemy` async: **no hits**.
- `db_url` in rxconfig.py: basic_crud, chat_v2, data_visualisation (env `DATABASE_URL`, default sqlite), form-designer, twitter.
- `alembic/` directory committed: **chat_v2** (1 revision) and **form-designer** (2 revisions). Both also ship `alembic.ini`.
  No other app ships alembic files. basic_crud's README documents `reflex db init` / `reflex db migrate`, but nothing is committed.
- `reflex.model` functions: the only call is `rx.model.migrate()` at form-designer/form_designer/form_designer.py:95
  (run at import time, "hosting service does not migrate automatically"). No `alembic_autogenerate`,
  `get_migration_history`, `format_revision`, or `migrate` calls elsewhere.

### Alembic revision chains

- form-designer/alembic/versions:
  - `481d2a7a6d6f_.py`: `down_revision = None`. Creates localauthsession, localuser (with unique index on username),
    form, field, option, fieldvalue, response.
  - `4c92535dbbbd_add_hidden_to_response.py`: `down_revision = "481d2a7a6d6f"`. `batch_alter_table("response")` adds column `hidden`.
  - Head: `4c92535dbbbd`.
- chat_v2/alembic/versions:
  - `486580f3ee3b_.py`: `down_revision = None`. Creates `chatinteraction`. Head: `486580f3ee3b`.

### alembic/env.py is the LEGACY stock template in both apps (important)

The committed env.py is alembic's generic template: `target_metadata = None`, and it connects through
`sqlalchemy.url` in alembic.ini (which is the placeholder `driver://user:pass@localhost/dbname`).
chat_v2's and form-designer's env.py are byte-identical. The reflex template in `reflex/.templates/alembic/env.py`
is different: it loads the app and reads `db_url` from rxconfig.py.

Reflex already has a path for this. `reflex/utils/migrations.py:is_legacy_env()` detects the stock env.py by looking for
`target_metadata = None`. `update_legacy_env()` renames it to `env.old` and installs the template. Callers:
`reflex/model.py:299/400/432`, `reflex/reflex.py:1148`, `reflex/utils/prerequisites.py:861/875`.

So the upgrade test should check, for form-designer and chat_v2:
1. Whether 0.11.0a1 rewrites env.py and creates `env.old` (on `reflex run`, `reflex db ...`, or the `rx.model.migrate()` call).
2. Whether `alembic current` / `makemigrations` still reports head `4c92535dbbbd` / `486580f3ee3b` afterwards, and no new revision appears.
3. Whether a `reflex db makemigrations` against the unchanged models produces a no-op (empty revision).
4. Whether the stock env.py, if left in place, still yields `target_metadata = None` and no autogenerate.

First 30 lines of `form-designer/alembic/env.py` (identical to chat_v2's):

```python
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
```

alembic.ini (form-designer): `script_location = alembic`, `sqlalchemy.url = driver://user:pass@localhost/dbname`,
i.e. the stock placeholder. The reflex template ignores that URL.

Other DB apps without alembic (basic_crud, chat_v2 has it, twitter, data_visualisation): a fresh `reflex db init` runs
on the 0.11 side, so these exercise the fresh-directory path. Create the DB under 0.10.1 first (no alembic dir) and see
how 0.11 handles an existing sqlite file with no version table.

## Per-app inventory

Legend: DB = uses sqlmodel/rx.session and/or db_url. Alembic = committed alembic/ dir. Bg = `background=True` events.

| app | requirements (beyond reflex) | DB | alembic | Bg | notable features |
|---|---|---|---|---|---|
| ag_grid_finance | reflex-enterprise>=0.0.2, yfinance==0.2.54 | no | no | no | enterprise AG Grid; external data fetch |
| azure_auth | msal==1.31.0 | no | no | no | OIDC login via on_load query/URL params (2 state classes) |
| basic_crud | reflex[db], fastapi | yes (sqlmodel, rx.session, db_url sqlite) | no (README: reflex db init/migrate) | yes (1 file) | **`rx.App(api_transformer=fastapi)`**: FastAPI router served next to the app; `api.py` uses rx.session |
| chat_v2 | reflex[db], openai, together, openinference, otlp, pytz, uv | yes (sqlmodel model + rx.session, db_url sqlite) | **yes (1 rev)** | yes (`submit_prompt`) | LLM streaming; external API keys needed; `set[str]` only in a dataclass in templates/top_bar.py, not a State var |
| clock | pytz==2022.7.1 | no | no | yes (2) | **rx.Cookie** timezone; tick loop |
| counter | - | no | no | no | plain baseline |
| dalle | openai>=1 | no | no | yes (1) | external API |
| data_visualisation | reflex[db], psycopg2-binary, pandas | yes (sqlmodel, rx.session, db_url from DATABASE_URL, default sqlite) | no | yes (1) | Postgres path possible; charts |
| flux-fast | - | no | no | no | TailwindV3Plugin + Radix accent color |
| form-designer | reflex[db], reflex-local-auth>=0.5.0 | yes (5 sqlmodel tables + LocalUser FK, rx.session, db_url sqlite) | **yes (2 revs), legacy env.py** | no | **reflex-local-auth** (login/register/logout routes, LocalAuthState subclass AppState); **rx.Cookie client_token** (pages/form_entry.py); **rx.model.migrate()** at import; sitemap plugin; 7 state classes; tests/ (pytest, login + create-form) |
| github-stats | - | no | no | yes (2) | **rx.LocalStorage** x4 (github_stats.py x2, widget.py x2: user_stats_json, last_fetch, selected_users_json); widget reads router params in on_load |
| json-tree | - | no | no | no | plain; in fixtures as legacy driver |
| linkinbio | launchdarkly-server-sdk==9.8.0 | no | no | no | external feature-flag service |
| local-component | - | no | no | no | local .jsx asset / custom component |
| lorem-stream | lorem_text>=2.1 | no | no | yes (1) | streaming text via background event |
| nba | pandas==3.0.1, plotly==6.6.0, statsmodels==0.14.6, scipy==1.17.1 | no | no | yes (1) | plotly charts; heavy pins |
| nba-proxy | same as nba | no | no | yes (1) | imports `../nba` via sys.path (needs sibling dir) |
| overkey | - | no | no | yes (1) | **stacked decorators**: `@rx.event` above `@rx.event(background=True)` on `tick` (overkey.py:164-165); **ClientStateVar** (`reflex.experimental.client_state`, overkey.py:80); timer typing game |
| quiz | - | no | no | yes (1) | Radix theme background |
| reflexle | reflex-global-hotkey>=1.2.2 | no | no | yes (1) | global hotkey watcher in a background event |
| snakegame | - | no | no | yes (1) | game loop in background event |
| todo | - | no | no | no | plain |
| translator | googletrans-py==4.0.0 | no | no | yes (1) | external translate service (sandbox blocked?) |
| traversal | - | no | no | no | plain; in fixtures as legacy driver |
| twitter | reflex[db] | yes (db_model.py many-to-many sqlmodel; rx.session in state/auth.py, home.py; db_url sqlite) | no | yes (1) | auth + feed; fixtures already cover the prod+Redis variant (twitter-redis) |
| upload | - | no | no | no | **rx.upload / rx.upload_files** (7 refs in upload/upload.py) |

Greps with zero hits: `rx.Model`, `AdminDash`, `frozenset`, `rx.asession`, `rx._x.client_state`, `sqlalchemy` async,
`alembic_autogenerate`, `get_migration_history`, `format_revision`.

Storage vars: `rx.LocalStorage` only in github-stats; `rx.Cookie` in clock and form-designer; `rx.SessionStorage` nowhere.

Set-typed state vars: none. The only `set[...]` annotation is a `Style` dataclass field in chat_v2 (templates/top_bar.py:15),
which is not a State var. So the set-var serialization path is not covered by any example.

Stacked decorators: only overkey (`@rx.event` over `@rx.event(background=True)`).

`api_transformer`: only basic_crud.

Third-party reflex packages across the examples: reflex-local-auth (form-designer), reflex-global-hotkey (reflexle),
reflex-enterprise (ag_grid_finance). chat_v2 and others use non-reflex SDKs only.

## Recommended in-place upgrade set (0.10.1 -> 0.11.0a1), 7 apps

Ordering is by priority. Items 1-3 are the DB / migration coverage that the fixture set does not have for 0.11.

### 1. form-designer (must-do)

Why: the only app with committed alembic revisions, a legacy stock env.py, `rx.model.migrate()` at import,
reflex-local-auth, a Cookie var, and a pytest suite. The fixtures already drive it on 0.9.12 -> 0.10.0 (`up/bin/seq_fd.sh`);
reuse those drivers, but on 0.10.1 -> 0.11.0a1.

Browser flows:
1. Anonymous `/` -> `/login`. Register a new user, then log out (navbar).
2. Login with the same user. Confirm the `client_token` cookie survives a full reload.
3. Create a form (form-create dialog), add 2-3 fields (text, select with options), save.
4. Open the form's editor `/edit/form/<id>`. Edit a field name, reload, confirm it persisted.
5. Open the public entry page `/form/<id>` in a fresh browser context (no login), submit a response.
6. Open `/responses/<id>` as the owner. Confirm the response row and its field values.
7. Open a protected route in a fresh context without a session: expect a redirect to `/login`.
8. Restart server, reload `/edit/form/<id>`: still logged in.
9. Run `reflex db makemigrations` (no-op expected) and check `alembic current` = `4c92535dbbbd`.
10. Prod mode (`reflex run --env prod`): repeat 2 and 5.

Known pre-existing anomalies (from fixtures): FormMessage crash on `/form/<id>` unless `FD_FIX_FIELD_NAME=1` patch;
React DOM-nesting / `:first-child` console errors in `entry`; favicon 404s.

### 2. chat_v2 (must-do, needs keys or a stub)

Why: committed alembic (1 rev, legacy env.py), `rx.session` in chat_state.py, background `submit_prompt` streaming,
and no fixture coverage at all. Requires `OPENAI_API_KEY` / `TOGETHER_API_KEY` for the real LLM path. The sandbox cannot
reach those providers, so either stub the client (monkeypatch the openai/together call in a local copy) or drive only the
non-LLM flows.

Browser flows:
1. Load home; create a new chat session. Confirm it appears in the sidebar.
2. Send a prompt (stubbed or real). Confirm streaming chunks render and the interaction saves.
3. Reload the page. The chat history from sqlite must still show (`chatinteraction` rows).
4. Delete a chat; confirm it disappears after reload.
5. Switch model/selector in top bar (the `set[str]` dataclass, not a state var). Confirm nothing regresses.
6. Check `alembic current` = `486580f3ee3b` after the upgrade; `makemigrations` no-op.

### 3. basic_crud (must-do)

Why: the only `api_transformer` app (FastAPI router mounted next to the Reflex app) plus sqlmodel + rx.session + background
events, and the README-only migration path (no committed alembic). It is the cleanest test of "fresh `reflex db init`
against an existing sqlite file created on 0.10.1".

Setup: run on 0.10.1 first, run `reflex db init` + `reflex db migrate` as the README says, add data, then upgrade in place.

Browser / HTTP flows:
1. Product list page loads, rows from the db.
2. Create, edit, delete a product through the UI. Confirm each change in the list after reload.
3. Background event path (the one `background=True` handler): trigger it and confirm the db write.
4. HTTP: GET/POST/DELETE against the FastAPI routes at the same origin (`/api/...`, check `api.py` for exact paths).
   Confirm the same data appears in the UI. These are the `api_transformer` checks.
5. Prod mode (`--env prod`) with the same CRUD flow.

### 4. twitter (should-do; dev covered, prod+redis covered)

Why: heavy `rx.session` usage across two state modules with many-to-many sqlmodel relations, and a sqlite `db_url`.
The fixture covers the twitter-redis and dev disk-state variants. Use the plain `twitter` app here as a DB-focused check
on 0.11 if the redis variant is out of scope.

Browser flows:
1. Sign up, log out, log in (plain auth in state/auth.py, not reflex-local-auth).
2. Post a tweet from home. Confirm it appears in the feed.
3. Follow a user; confirm the feed filters.
4. Open a user profile, confirm the tweet list.
5. Restart server, reload: session and feed persist (db, not state).

### 5. github-stats (should-do; storage vars)

Why: the only app with `rx.LocalStorage` (4 vars across the main page and the widget), background events, and a widget
that reads router params in on_load. These are the storage-persistence paths the 0.11 notes care about. Fixtures cover it
on 0.9.12 -> 0.10.0 with a GraphQL stub (`QA_GITHUB_GRAPHQL_URL`).

Browser flows:
1. Add 2-3 GitHub users. Confirm stats render.
2. Reload: LocalStorage `user_stats_json` and `selected_users_json` restore without re-fetching (check `last_fetch`).
3. Open the widget route (`/widget/...` per widget.py) and confirm it renders stats from LocalStorage.
4. Background fetch: trigger a refresh and confirm the state update reaches the UI.

Network: GitHub GraphQL is blocked in the sandbox; use the fixture stub.

### 6. overkey (should-do; stacked decorators + ClientStateVar + background)

Why: the only app with stacked `@rx.event` over `@rx.event(background=True)` (overkey.py:164-165), a ClientStateVar
(`reflex.experimental.client_state`), and a background timer. Stacked decorators are a likely breakage point for a
decorator-level change in 0.11, and ClientStateVar is an experimental API that could change.

Browser flows:
1. Load the typing game; pick a time limit.
2. Start: the timer ticks once per second (background `tick`). Confirm the countdown changes.
3. Type words; confirm the client-side `user_input` ClientStateVar updates without a server round-trip (watch the network panel).
4. Let the timer expire; confirm the results screen and score.
5. Reload mid-game; check the ClientStateVar default resets as expected on 0.11 vs 0.10.1 (record both).

### 7. counter (plain baseline)

Why: the cheapest plain UI app. It confirms that the base venv swap works end to end (install 0.10.1, upgrade in place
to 0.11.0a1, dev + prod + cold rebuild). The fixtures already run counter in `up/bin/seq_app.sh counter`.
If a second plain app is wanted instead, use `upload` (rx.upload / rx.upload_files, react-dropzone) since that
covers an upload path the other six do not.

Browser flows:
1. Increment / decrement / reset. Reload: state reset as expected (no persistence).
2. Dev -> prod: same flow.
3. Upgrade in place: the page still renders after the restart; no console errors beyond the known favicon 404.

## Gaps and notes for the test plan

- No example uses `rx.Model`, `AdminDash`, `frozenset`, `rx.asession`, or `set`-typed State vars. A set-var check needs a
  custom app (not from reflex-examples).
- `rx.SessionStorage` is not used anywhere.
- The `alembic/env.py` legacy path (see above) is the single most important DB check for 0.11: it is exercised only by
  form-designer and chat_v2, and nothing in the fixtures checks `update_legacy_env()` on an in-place upgrade.
- basic_crud and twitter need an explicit `reflex db init` on the 0.10.1 base before the upgrade, because nothing
  is committed. Otherwise the upgrade test cannot tell "fresh db" from "pre-existing db".
- Apps needing external keys or network (chat_v2, dalle, translator, linkinbio, ag_grid_finance via yfinance,
  github-stats, azure_auth) are either stubbed or skipped in the sandbox.
- nba-proxy imports `../nba` at config time: it needs the sibling directory present.
