# Cluster `db_optional_imports` — reflex 0.9.12a1 pre-release QA

Scope: optional-dependency / lazy-import behavior (#7049), `rx.Model` without the `db`
extra (#7083), on-demand pandas/Plotly/Pillow serializers, SQLModel relationships,
"database usage accounting", fork safety.

Everything here was run against **packages published to PyPI only**. Nothing was installed
from the `/home/user/reflex` checkout, and no script was run with the checkout as cwd
(every repro script asserts `"/envs/" in reflex.__file__`).

**Bottom line: no defects found in this cluster.** Both headline changes do what the
changelog says, the relationship-serialization payloads are byte-for-byte equivalent to the
previous stable, and the startup/memory claim is confirmed with large, reproducible margins.
Three low-severity observations are recorded as anomalies at the end.

---

## 1. Environments

`SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad`

Two venvs were pre-existing and read-only (`$SB/envs/shared` = 0.9.12a1 train with **no**
db/data extras, `$SB/envs/prev` = 0.9.11.post1 likewise). They served as the "bare" installs.
Four more were created for this cluster. Recreate them with:

```bash
cd $SB   # NEVER from /home/user/reflex — its pyproject exclude-newer filters out the alphas

# db (0.9.12a1 + db extra)
uv venv $SB/envs/dbi_db --python 3.11
uv pip install --python $SB/envs/dbi_db/bin/python --prerelease=allow \
  'reflex[db]==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
  'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
  'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
  'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
  'reflex-components-sonner==0.9.4a1' aiosqlite

# data (0.9.12a1 + pandas/pillow/plotly, NO db extra)
uv venv $SB/envs/dbi_data --python 3.11
uv pip install --python $SB/envs/dbi_data/bin/python --prerelease=allow \
  'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
  'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
  'reflex-components-sonner==0.9.4a1' 'reflex-components-markdown==0.9.4a1' \
  pandas pillow plotly

# 0.9.11.post1 baselines
uv venv $SB/envs/dbi_dbprev --python 3.11
uv pip install --python $SB/envs/dbi_dbprev/bin/python 'reflex[db]==0.9.11.post1' \
  'reflex-components-core==0.9.9' 'reflex-components-radix==0.9.9' 'reflex-components-code==0.9.5' \
  'reflex-components-dataeditor==0.9.2' 'reflex-components-gridjs==0.9.1' \
  'reflex-components-markdown==0.9.3' 'reflex-components-plotly==0.9.6' \
  'reflex-components-recharts==0.9.3' 'reflex-components-sonner==0.9.3' aiosqlite

uv venv $SB/envs/dbi_dataprev --python 3.11
uv pip install --python $SB/envs/dbi_dataprev/bin/python 'reflex[db]==0.9.11.post1' \
  'reflex-components-core==0.9.9' 'reflex-components-radix==0.9.9' 'reflex-components-plotly==0.9.6' \
  pandas pillow plotly aiosqlite
```

Resolved versions actually used (`uv pip freeze | grep -iE 'reflex|sqlmodel|pandas|...'`):

```
shared        reflex==0.9.12a1 reflex-base==0.9.12a1 reflex-components-code==0.9.6a1
              reflex-components-core==0.9.10a1 reflex-components-dataeditor==0.9.3a1
              reflex-components-gridjs==0.9.2a1 reflex-components-lucide==1.0.4
              reflex-components-markdown==0.9.4a1 reflex-components-moment==0.9.4
              reflex-components-plotly==0.9.7a1 reflex-components-radix==0.9.10a1
              reflex-components-react-player==0.9.2 reflex-components-recharts==0.9.4a1
              reflex-components-sonner==0.9.4a1 reflex-hosting-cli==0.1.72
              (no sqlmodel / pandas / pillow / plotly)

prev          reflex==0.9.11.post1 reflex-base==0.9.11.post1 + the matching stable
              component set (code 0.9.5, core 0.9.9, dataeditor 0.9.2, gridjs 0.9.1,
              markdown 0.9.3, plotly 0.9.6, radix 0.9.9, recharts 0.9.3, sonner 0.9.3)

dbi_db        reflex==0.9.12a1 reflex-base==0.9.12a1 + 0.9.12a1 component alphas
              sqlalchemy==2.0.54 sqlmodel==0.0.42 alembic==1.20.0 aiosqlite==0.22.1

dbi_data      reflex==0.9.12a1 reflex-base==0.9.12a1 + 0.9.12a1 component alphas
              pandas==3.0.6 pillow==12.3.0 plotly==7.1.0 numpy==2.4.6

dbi_dbprev    reflex==0.9.11.post1 + stable components
              sqlalchemy==2.0.54 sqlmodel==0.0.42 alembic==1.20.0 aiosqlite==0.22.1

dbi_dataprev  reflex==0.9.11.post1 + stable components
              pandas==3.0.6 pillow==12.3.0 plotly==7.1.0 numpy==2.4.6
              sqlalchemy==2.0.54 sqlmodel==0.0.42 alembic==1.20.0 aiosqlite==0.22.1
```

Ports used: frontend 3420/3421/3422, backend 8420/8422 (prod used 3421 for both, as
required). Redis was not needed. All processes were killed at the end and the ports
verified clear with `python3 $SB/bin/ports.py`.

## 2. Apps in this directory

| dir | venv | what it exercises |
| --- | --- | --- |
| `dbapp/` | `dbi_db` | `Author` 1–N `Book`, `Book` N–N `Tag` via `BookTagLink`; sync `rx.session()` and async `rx.asession()` with `selectinload`; relationship-bearing state vars; `State.book.author.name` ObjectVar access inside `rx.foreach`; background task; event chain; dynamically-created SQLModel class with `__module__` removed; custom `@rx.serializer`; `__fields__`/`dict()`/`serialize()` of a row |
| `dataapp/` | `dbi_data` | `rx.data_table` over a `pd.DataFrame` state var, `rx.plotly` over a `go.Figure` state var, `rx.image` over a `PIL.Image.Image` state var, all mutated on click; `@rx.memo`; `rx.ComponentState`; `rx.cond`; event chain across all three serializers; first serialization inside a background task |
| `bareapp/` | `shared` (no db extra) | `reflex db init` error quality without the `db` extra |

`.web/`, `node_modules/`, `*.db` and `__pycache__` were excluded from this copy — the apps
rebuild them on first `reflex run`.

## 3. Exact rerun commands

```bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
D=$SB/apps/db_optional_imports         # copy this directory's dbapp/dataapp/bareapp here
export REFLEX_TELEMETRY_ENABLED=false

# --- no-server repro scripts (each asserts it is NOT importing the checkout) ---
cd $D && $SB/envs/shared/bin/python   $D/scripts/bare_imports.py        # lazy-import check, new
cd $D && $SB/envs/prev/bin/python     $D/scripts/bare_imports.py        # baseline
cd $D && $SB/envs/shared/bin/python   $D/scripts/bare_model.py          # #7083, new
cd $D && $SB/envs/prev/bin/python     $D/scripts/bare_model.py          # #7083, baseline (TypeError)
cd $D && $SB/envs/dbi_data/bin/python $D/scripts/data_serializers.py    # optional serializer resolution
cd $D && $SB/envs/dbi_db/bin/python   $D/scripts/accounting.py direct   # db usage accounting (also: bare|rxmodel)
cd $D && $SB/envs/dbi_db/bin/python   $D/scripts/serializer_override.py # custom override survival
cd $D && $SB/envs/dbi_dbprev/bin/python $D/scripts/serializer_override.py  # baseline: override is clobbered
cd $D && $SB/envs/dbi_data/bin/python $D/scripts/startup_measure.py     # startup RSS/time (also dbi_dataprev)
cd $D && $SB/envs/dbi_db/bin/python   $D/scripts/serialize_baseline.py $D/dbapp/reflex.db   # payload A/B
cd $D && $SB/envs/dbi_dbprev/bin/python $D/scripts/serialize_baseline.py $D/dbapp/reflex.db

# --- db app: migrations, dev server, browser ---
cd $D/dbapp
$SB/envs/dbi_db/bin/reflex db init
$SB/envs/dbi_db/bin/reflex db makemigrations --message initial
$SB/envs/dbi_db/bin/reflex db migrate
$SB/envs/dbi_db/bin/reflex run --frontend-port 3420 --backend-port 8420 --loglevel debug
cd $D && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python $D/scripts/drive_db.py http://localhost:3420/ $D/shots dev

# --- db app: prod, 4 forked granian workers, 20 concurrent browser contexts ---
cd $D/dbapp
GRANIAN_WORKERS=4 $SB/envs/dbi_db/bin/reflex run --env prod --frontend-port 3421 --backend-port 3421
cd $D && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python $D/scripts/fork_load.py http://localhost:3421/ 20 $D/shots

# --- data app: dev server, browser ---
cd $D/dataapp
$SB/envs/dbi_data/bin/reflex run --frontend-port 3422 --backend-port 8422
cd $D && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python $D/scripts/drive_data.py http://localhost:3422/ $D/shots dev

# --- bare install: db CLI error quality ---
cd $D/bareapp && $SB/envs/shared/bin/reflex db init     # guided ImportError (same on prev)
```

## 4. What was verified

### 4.1 `rx.Model` without the `db` extra (#7083) — FIXED, confirmed against baseline

`logs/bare_model_new.log` vs `logs/bare_model_prev.log`. On 0.9.12a1 every path raises the
same guided error, verbatim:

```
ImportError: Database is not available. Please install the required packages: `pip install reflex[db]`.
```

| case | 0.9.11.post1 | 0.9.12a1 |
| --- | --- | --- |
| `class Item(rx.Model, table=True)` | `TypeError: Item.__init_subclass__() takes no keyword arguments` | guided `ImportError` |
| `class Item(rx.Model)` (no kwargs) | **defines successfully** | guided `ImportError` |
| `rx.Model()` | guided `ImportError` | same |
| `rx.session()` / `rx.asession()` | guided `ImportError` | same |
| `rx.Model` used only in an annotation (string or runtime) | no error | no error |
| `rx.Model.__fields__` | `AttributeError` | same |
| state var annotated `rx.Model` | `VarTypeError` | same |

The plain-subclass row is a deliberate behavior change (the PR author flagged it); see
anomaly A1 — the changelog only mentions the `table=True` form.

### 4.2 Optional integrations are no longer imported when unused (#7049) — CONFIRMED, large margin

`scripts/startup_measure.py`, run 3× per version in the venvs that have pandas, Pillow,
Plotly, SQLModel, SQLAlchemy and alembic **installed**, building a small app that uses none
of them (one state, one page, a `foreach` and a `cond`). Median of 3:

| metric (optional deps installed, unused) | 0.9.11.post1 | 0.9.12a1 | delta |
| --- | ---: | ---: | ---: |
| optional modules loaded after `import reflex` | none | none | — |
| optional modules loaded after building the app | `PIL, alembic, numpy, pandas, plotly, sqlalchemy, sqlmodel` | **none** | all 7 avoided |
| `len(sys.modules)` after building the app | 1509 | **645** | −57% |
| max RSS after building the app | 133.0 MB | **46.5 MB** | −65% |
| time to build the app | 0.78 s | **0.24 s** | 3.2× faster |

(First iteration on the baseline was a cold-cache outlier at 3.0 s / 148 MB; the 0.78 s /
133 MB figures are the warm medians, which is the fair comparison. `import reflex` alone was
already lazy on both versions — the difference is entirely in app construction.)

The perf claim in the changelog holds and then some, at least on this Linux/Python 3.11 box.

### 4.3 On-demand pandas / Plotly / Pillow serializers — PASS

`scripts/data_serializers.py` (`logs/data_serializers_new.log`) confirms the identity-based
lookup resolves correctly against the *current* library layouts: `pandas.DataFrame`
(pandas 3.0.6), `plotly.graph_objs._figure.Figure` and `plotly.graph_objs.layout._template.Template`
(plotly 7.1.0), `PIL.Image.Image` (Pillow 12.3.0) each map to their serializer, and each
serializes. This matters because the lookup matches classes by identity in hard-coded module
paths — a library reorganizing would silently break it, and none of the current ones have.

End-to-end in the browser (`logs/drive_data_dev.log`, `shots/dev_data_*.png`): `rx.data_table`
renders real DataFrame cells (`['0','0','row-0','1','1','row-1',…]`), `rx.plotly` renders
13 SVGs / 8 bars and updates its title on re-render, `rx.image` emits a `data:image/png;base64,…`
src with a correct 64×64 natural size. All three update on click, through an event chain, and
through a background task whose `async with self` block is the **first** place any of them is
serialized. `@rx.memo`, `rx.ComponentState` and `rx.cond` all behave. State survives a reload.
Zero console errors/warnings, zero 4xx/5xx.

### 4.4 SQLModel relationships — PASS, payload identical to baseline

Browser run `logs/drive_db_dev2.log`, screenshots `shots/dev_0*.png`. Confirmed:

- one-to-many: `books: list[Book]` loaded with `selectinload(Book.author)` arrives at the
  client with the author nested, e.g.
  `{"id":3,"year":1961,"author_id":2,"title":"Solaris","author":{"country":"PL","id":2,"name":"Stanislaw Lem"},"tags":[{"label":"scifi","id":1}]}`
- many-to-many through the link table renders its tag badges (`['scifi','scifi','classic']`)
- `async with rx.asession()` + `selectinload(Author.books)` nests books under authors
- `State.single_book.author.name` and `b.author.country` (ObjectVar access **through** a
  relationship) render inside and outside `rx.foreach`
- a background task doing the DB read and assigning the relationship-bearing var works
- an event chain `seed → load_books_sync → load_authors_async` works
- loading **without** `selectinload` leaves the relationship unloaded: the fields render empty
  and the `DetachedInstanceError` is suppressed rather than crashing (same as baseline)
- a second browser tab gets the same data
- `type(row).__fields__` / `row.dict()` = `['author_id','id','title','year']`;
  `serialize(row)` = those plus `author` and `tags` — i.e. relationships are added on top of
  the column fields, as documented
- a class built with `type("DynBook", (sqlmodel.SQLModel,), …)` whose `__module__` was deleted
  serializes fine (`{"title": "dyn"}`) — the "classes without module names" case
- zero console errors, zero 4xx/5xx, no tracebacks in the server log

**Baseline A/B of the payload** (`scripts/serialize_baseline.py`, `logs/serialize_baseline.log`):
serializing the same three rows from the same SQLite file under 0.9.12a1 and 0.9.11.post1
yields semantically identical output (same keys, same nested author/tags, same values; the
only textual difference is the field order inside the nested objects' `repr`). Relationship
attribute typing is identical too: `get_attribute_access_type(Book,'author')` →
`Optional[Author]`, `(Book,'tags')` → `list[Tag]`, `(Author,'books')` → `list[Book]` on both.

### 4.5 Custom serializer override survives a later `reflex.model` import — FIXED, confirmed regression in baseline

`scripts/serializer_override.py`. Register `@rx.serializer` for `sqlmodel.SQLModel`, then
`import reflex.model` (which a downstream import can trigger at any time):

| | 0.9.11.post1 | 0.9.12a1 |
| --- | --- | --- |
| before `import reflex.model` | `{"CUSTOM_BASE": true, "name": "a"}` | same |
| **after** `import reflex.model` | `{"name": "b"}` — override silently clobbered, with an "Overwriting serializer … to reflex.model:serialize_sqlmodel" warning | `{"CUSTOM_BASE": true, "name": "b"}` — override kept |
| `rx.Model` subclass | `{"name":"c","id":null}` (framework serializer) | `{"CUSTOM_BASE": true, "name": "c"}` |
| exact-type override on a subclass | `{"EXACT": true, …}` | same (exact type still beats the base) |

This is a real user-visible bug that 0.9.12a1 fixes: on the old version a user's serializer
was silently replaced depending on import order.

### 4.6 "Database usage accounting" — PASS

The changelog phrase maps to `reflex.utils.telemetry_accounting._get_db_model_count()`.
`scripts/accounting.py` verifies on 0.9.12a1:

| app shape | `reflex.model` loaded? | count |
| --- | --- | --- |
| no models at all (db extra installed) | no | 0 |
| two tables declared with **sqlmodel directly**, never touching `rx.Model` | **no** | **1** |
| one table declared with `rx.Model` | yes | 1 |
| no models, db extra **not** installed | no | 0 |

So direct-SQLModel apps are still counted as database users without the unused
`reflex.model` integration being imported — exactly the claim.

### 4.7 Fork safety under prod with 4 workers — PASS

`GRANIAN_WORKERS=4 reflex run --env prod --frontend-port 3421 --backend-port 3421` against a
pre-populated SQLite file (cold start: the first request is what hydrates the
relationship-bearing var). Four worker PIDs confirmed listening on 3421.
`scripts/fork_load.py` then opened **20 concurrent Chromium contexts**, each navigating and
firing a sync DB read plus a background-task DB read.

Result (`logs/fork_load_prod.log`): **20/20 contexts** returned the full, correctly nested
relationship data in 6.0 s total; no hangs, no `MissingGreenlet`, no "registry corruption"
tracebacks, no page errors, no 4xx/5xx, and the prod server log stayed clean (27 lines, no
exceptions). Screenshot `shots/prod_fork_ctx0.png`.

### 4.8 Migrations on a bare-then-db install — PASS

`reflex db init` → `makemigrations` → `migrate` in `dbapp/` produced
`alembic_version, author, tag, book, booktaglink` and the generated revision
(`dbapp/alembic/versions/4c902955c15a_initial.py`) applies cleanly.

## 5. Anomalies (benign but worth knowing)

**A1 — changelog understates the `rx.Model` behavior change.** The changelog line only
mentions `class Item(rx.Model, table=True)`. In fact a plain `class Item(rx.Model)` with no
class keywords, which on 0.9.11.post1 *defined successfully* on a bare install and only
failed at instantiation, now raises the guided `ImportError` at class-definition time. The
PR (#7083) explicitly flags this and argues it is the more useful failure point; I agree, but
a module that merely *defines* such a class at import time (without ever instantiating it)
will now fail to import on a bare install where it previously did not. Evidence:
`logs/bare_model_new.log` vs `logs/bare_model_prev.log`. Not a regression in the pejorative
sense — an intended change — but downstream users on a bare install could be surprised, and
the changelog wording does not cover it.

**A2 — `reflex db init` without the `db` extra dumps a raw traceback.** The guided
`ImportError` message is correct, but it arrives as an unhandled ~20-line Python traceback
through `click` rather than as a clean CLI error. Identical on 0.9.11.post1, so this is a
pre-existing UX wart, not a regression, and it is adjacent to #7083's "guided error" theme.
Repro: `cd bareapp && $SB/envs/shared/bin/reflex db init`.

**A3 — `rx.asession()` requires `async_db_url` to be set explicitly.** With only
`db_url="sqlite:///reflex.db"` configured, every `async with rx.asession()` handler fails
with `ValueError: No async database url configured`, and in a background task this surfaces
only as the task silently never completing (my first run left `bg: starting` on screen with
no client-side error). Identical code and behavior on 0.9.11.post1 (`reflex/model.py` line
~153 on new, ~144 on prev), so **not a regression** — but it is a sharp edge for anyone
following the relationship examples, since nothing hints that a second URL is required.
Fixed here by adding `async_db_url="sqlite+aiosqlite:///reflex.db"` to `rxconfig.py` and
installing `aiosqlite`. The failing first run is preserved in `logs/dbapp_dev.log`
(search "No async database url configured"); the passing run is `logs/dbapp_dev2.log`.

Also noted, and expected: `rx.Model` emits the "deprecated in version 0.9.2 … removed in
1.0.0" warning on every db command, and the `SitemapPlugin` "enabled by default but not
explicitly added" warning appears on every run. Both are pre-existing and present on
0.9.11.post1 too.

## 6. Not covered

- `reflex-local-auth` install + migration against 0.9.12a1 (cluster item 7) — ran out of
  timebox; it is also covered by the upgrade cluster.
- Redis state manager was not combined with the DB app (memory/disk only).
- Only Python 3.11 on Linux; the PR's own numbers are macOS/Python 3.14.
- The startup comparison measures in-process app construction, not full
  `reflex run` time-to-`/ping`, so it is not directly comparable to the PR's table.

## 7. Cleanup

All servers killed by PID; `python3 $SB/bin/ports.py 3420 3421 3422 8420 8421 8422` reports
nothing listening. No redis was started. `.web/` and `node_modules/` were excluded from this
artifact copy but still exist under the scratchpad app dirs.
