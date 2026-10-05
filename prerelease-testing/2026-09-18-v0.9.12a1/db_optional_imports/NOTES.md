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

---

## VERIFICATION

Independent adversarial verification, run 2026-09-19 from the written material only
(this NOTES.md + the app sources/scripts in this directory). Nothing was installed from or
run inside `/home/user/reflex`. Work dir
`$SB/apps/verify_db_optional_imports/` (fresh copy of `scripts/`, `bareapp/`, `dbapp/`);
reserved ports frontend 3920, backend 8920. Evidence under `verification/`.

Versions (`uv pip freeze --python <venv> | grep -iE 'reflex|sqlmodel|sqlalchemy|alembic|aiosqlite'`,
full output in `verification/v_freeze.txt`):

```
shared   reflex==0.9.12a1      reflex-base==0.9.12a1      + 0.9.12a1 component alphas (no db extra)
prev     reflex==0.9.11.post1  reflex-base==0.9.11.post1  + matching stable components (no db extra)
dbi_db   reflex==0.9.12a1      reflex-base==0.9.12a1      + alphas, sqlalchemy==2.0.54 sqlmodel==0.0.42
         alembic==1.20.0 aiosqlite==0.22.1
```

### A1 — changelog understates the `rx.Model` behavior change — **NOT CONFIRMED** (observation accurate, framing does not hold)

Commands:

```bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/apps/verify_db_optional_imports
cd $W && $SB/envs/shared/bin/python $W/scripts/bare_model.py   # -> verification/v1_bare_model_new.log
cd $W && $SB/envs/prev/bin/python   $W/scripts/bare_model.py   # -> verification/v1_bare_model_prev.log
```

The *behavior* reproduces exactly as written, 100% deterministic:

| case | 0.9.11.post1 | 0.9.12a1 |
| --- | --- | --- |
| `class Item2(rx.Model): id: int` | `NO_ERROR -> <class '...Item2'>` | `RAISED: ImportError` (`pip install reflex[db]`) |

Root cause confirmed in the release source: `reflex/model.py:53-63` defines
`_ClassThatErrorsOnInit.__init_subclass__`, which Python calls for **every** subclass
regardless of class keywords. PR #7083's body confirms the explorer's account verbatim —
the author wrote "a plain `class Item(rx.Model)` without keywords used to define fine on a
bare install and only failed at instantiation; it now fails at definition ... if you would
rather keep plain subclasses lazy I can gate the check on the presence of class keywords",
and the maintainers merged it unchanged.

Why this is nevertheless **not** a defect a fix agent should act on:

1. The claim is that the changelog implies "only the `table=True` form changes behavior".
   The actual v0.9.12a1 entry reads: *"Subclassing `rx.Model` (e.g. `class Item(rx.Model,
   table=True)`) without the `db` extra installed now raises the guided "pip install
   reflex[db]" `ImportError` instead of a bare `TypeError` from `__init_subclass__`."*
   The scope clause is **"Subclassing `rx.Model`"** — general — and `table=True` is
   introduced with "e.g.", i.e. explicitly as an example, not as the scope. The changelog
   therefore already covers the plain-subclass case.
2. The only genuinely imprecise words are the trailing "instead of a bare `TypeError`",
   which is true for the keyword form and not for the plain form (which previously raised
   nothing). That is a one-clause wording nit, not a documentation gap about the change.
3. The newly-broken population is vanishingly small: only a **bare** install (no `db`
   extra) importing a module that defines an `rx.Model` subclass it never instantiates.
   Any such module that actually *uses* the model already failed on 0.9.11.post1, and now
   fails earlier with a strictly better message. Installs *with* the `db` extra are
   unaffected (`rx.Model` is the real model class there).

Optional polish only: drop or qualify the "instead of a bare `TypeError`" clause. No code
change warranted. Severity: not a defect.

### A2 — `reflex db init` without the `db` extra prints a raw traceback — **CONFIRMED** (low, pre-existing, not a release blocker)

Commands:

```bash
cd $W/bareapp && REFLEX_TELEMETRY_ENABLED=false $SB/envs/shared/bin/reflex db init
cd $W/bareapp && REFLEX_TELEMETRY_ENABLED=false $SB/envs/prev/bin/reflex db init
```

Evidence: `verification/v2_dbinit_new.log`, `verification/v2_dbinit_prev.log`.
Both are 35 lines, exit 1, and after normalizing venv paths and line numbers the two
tracebacks are **byte-for-byte identical** (`diff` clean) — confirming the explorer's
"not a regression". Frames: `click/core.py` ×5 -> `reflex/reflex.py:986 db_init` ->
`reflex/model.py:47 _print_db_not_available` -> `ImportError: Database is not available.
Please install the required packages: 'pip install reflex[db]'.` (0.9.11.post1:
`reflex.py:960` / `model.py:49`.)

Confirmed as a genuine, if minor, defect because it is **inconsistent with the same
command's own error style**: `db_init` (`reflex/reflex.py:960-987`) already handles its
other two foreseeable failures — `db_url` unset, and alembic already initialized — with a
clean `logger.error(...)` + `return`, but lets the missing-extra `ImportError` escape to
click.

Additional evidence the explorer missed, which strengthens the case: on a bare install
`reflex db makemigrations` is **worse** — it dies in
`reflex/reflex.py:1044` on `from alembic.util.exc import CommandError` with
`ModuleNotFoundError: No module named 'alembic'` and **no `reflex[db]` guidance at all**.
Identical on 0.9.11.post1 (`reflex.py:1018`). Evidence: `verification/v2_dbmakemig_new.log`,
`verification/v2_dbmakemig_prev.log`. (`reflex db migrate` is fine — it exits 0 with the
clean "Database is not initialized. Run reflex db init first.": `verification/v2_dbmigrate_new.log`.)

Regression: **no** — pre-existing on 0.9.11.post1. Should not block 0.9.12; worth a
follow-up that wraps the `reflex db *` commands so both the `ImportError` and the
`alembic` `ModuleNotFoundError` render as one guided CLI line.

### A3 — failing `rx.asession()` in a background task is "invisible to the client" — **REFUTED**

Setup reproduced exactly as written (`async_db_url` removed from `dbapp/rxconfig.py`,
leaving only `db_url="sqlite:///reflex.db"`):

```bash
cd $W/dbapp && REFLEX_TELEMETRY_ENABLED=false $SB/envs/dbi_db/bin/reflex db migrate
cd $W/dbapp && REFLEX_TELEMETRY_ENABLED=false $SB/envs/dbi_db/bin/reflex run \
    --frontend-port 3920 --backend-port 8920 --loglevel debug   # verification/v3_dbapp_noasync.log
cd $W && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $SB/envs/driver/bin/python $W/scripts/drive_db.py http://localhost:3920/ \
    verification/shots noasync                                   # verification/v3_drive_noasync.log
cd $W && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $SB/envs/driver/bin/python $W/scripts/verify_async_err.py http://localhost:3920/ \
    verification/shots noasync_new                               # verification/v3_async_err_new.log
```

Everything **except the headline** reproduces: `#btn-async` adds no log line and leaves the
authors box empty, `#btn-bg` stops at `bg: starting`, the server log holds exactly three
`ValueError: No async database url configured` tracebacks
(`reflex/model.py:165 get_async_engine`, reached from `model.py:698 asession`), and
`drive_db.py` reports empty PAGE ERRORS / BAD RESPONSES / console errors — identical to
`logs/drive_db_dev.log`.

**But the failure is not invisible to the client.** The same server log contains three
`[Reflex Backend Exception]` markers, i.e. `default_backend_exception_handler`
(`reflex/app.py:136-168`) ran and returned a sonner toast. `drive_db.py` never looks for
one — it only inspects `console`, `pageerror`, HTTP status and the state delta, none of
which a toast touches, and the toast carries `id="backend_error"` with the sonner default
~4 s duration, so it is also gone by the time the script's later steps run. That is the gap
in the written repro.

`scripts/verify_async_err.py` (copied to `verification/verify_async_err.py`) adds a
`page.on("dialog")` listener, a `[data-sonner-toast]` / `[role=alert]` DOM probe and a raw
websocket dump. Result — after **both** `#btn-async` and `#btn-bg`:

```
toast_els: ["", "An error occurred.ValueError: No async database url configured\nSee logs for details.",
                "An error occurred.ValueError: No async database url configured\nSee logs for details."]
body_has_error_text: true
```

and the matching websocket frame:

```
42/_event,["event",{"events":[{"name":"_call_function","payload":{"function":
"(() => (isTrue(refs['__toast']) ? (refs['__toast']?.[\"error\"](\"An error occurred.\",
({ \"description\" : \"ValueError: No async database url configured\\nSee logs for details.\", ... }))
 : (window.alert(...))))"}}]}]
```

Screenshots: `verification/shots/noasync_new_async_click.png` (foreground handler) and
`verification/shots/noasync_new_bg_click.png` (background task) — both show a red toast at
top-center reading *"An error occurred. / ValueError: No async database url configured /
See logs for details."* while `bg: starting` is still on the page.

So the background-task exception **is** surfaced to the browser, in dev mode, with the exact
exception text, by the framework's documented default backend exception handler. The
remaining true parts of A3 — that `rx.asession()` requires `async_db_url` to be configured
explicitly and derives nothing from `db_url` (`reflex/model.py:150-165`), and that the
background task aborts leaving `bg: starting` — are pre-existing, intended design, and are
accompanied by an actionable client-side error. Not a defect.

### Cleanup

`reflex run` pid 27288 killed, orphaned backend pids 27290/27338 killed with `kill -9`;
`python3 $SB/bin/ports.py 3920 3921 8920 8921` reports nothing listening. No redis, no
browser processes left. Everything installed came from PyPI; nothing was run with
`/home/user/reflex` as cwd (`bare_model.py` asserts `"/envs/" in reflex.__file__`).
