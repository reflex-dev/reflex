# Cluster `db_optional_imports` — optional-dependency and lazy-import behavior (#7049), `rx.Model` without the db extra (#7083), on-demand serializers

Changelog lines (verbatim):
- Preserve relationship serialization and database usage accounting for apps that use SQLModel directly, without loading unused database integrations. (#7049)
- (reflex-base) Preserve SQLModel relationships, ObjectVar field access, and optional serializer overrides on cold startup, including classes without module names and multiple optional-library bases. Avoid import-order failures, fork hangs, and registry corruption during serializer lookup. (#7049)
- (reflex-base) Load pandas, Plotly, and Pillow serializers on demand and avoid importing SQLAlchemy for generic type helpers, reducing startup time and memory when these integrations are unused. (#7049)
- Subclassing `rx.Model` (e.g. `class Item(rx.Model, table=True)`) without the `db` extra installed now raises the guided "pip install reflex[db]" `ImportError` instead of a bare `TypeError` from `__init_subclass__`. (#7083)
- Reduce development startup and reload time and memory by deferring unused database, admin, and compiler imports... (#7049)

Read #7049 (large) and #7083. Three venvs of your own: `bare` (train only, no extras), `db`
(`reflex[db]==0.9.12a1` + component alphas), `data` (train + pandas + pillow + plotly), and the
0.9.11.post1 equivalents where a baseline is needed.

## Exercise

1. bare: guarded script — `import reflex; sorted(m for m in sys.modules if m.split('.')[0] in {"sqlalchemy","sqlmodel","alembic","pandas","PIL","plotly","httpx","starlette_admin"})`
   (expect none); `class Item(rx.Model, table=True)` → the guided ImportError text (record it
   verbatim; baseline gives a TypeError); `rx.session()`, `rx.asession()`, `reflex db init` in a
   project → error quality; `rx.Model` referenced in a type annotation only (no subclass) → fine?
2. data: a page with `rx.data_table(data=pd.DataFrame(...))`, `rx.image(src=PIL.Image.new(...))`,
   `rx.plotly(data=go.Figure(...))`, a State var holding a DataFrame / a Figure / an Image that
   changes on click; check `sys.modules` before the first serialization and after (serializers
   load on demand); prod too. Also a fresh-process ("cold") start where the FIRST serialization
   happens inside a background task or an API route rather than at compile time.
3. db (sqlite): models `Author`/`Book` with `Relationship(back_populates=...)`, one-to-many and
   many-to-many via a link table; `reflex db init` → `makemigrations` → `migrate`; state handlers
   using `with rx.session()` and `async with rx.asession()` with `selectinload`; a state var
   `books: list[Book]` where each book's `author` relationship is loaded → the frontend receives
   the nested author (compare frame payloads with 0.9.11.post1); `State.book.author.name`
   (ObjectVar field access through a relationship) in `rx.foreach`; a model class created
   dynamically with `type(...)` and `__module__` deleted/None (the "classes without module names"
   line); a custom `@rx.serializer` override for a model type; `rx.Model.__fields__`/`dict()` of a
   row with relationship set. Then a cold prod start (`--env prod`) with the DB pre-populated and
   the first request hydrating the relationship-bearing var.
4. "database usage accounting": read #7049 to see what this means (a telemetry/usage counter?)
   and verify it still fires when SQLModel is used directly; record what you find.
5. Startup numbers on both versions: `time` to `/ping` for the bare app and the db app, backend
   worker RSS, `python -X importtime -c "import reflex"` top-20 cumulative; report a table.
6. Fork safety: prod with 4 granian workers using the db app, 20 concurrent browser contexts
   (Playwright) each triggering a DB read → no hang, no "registry corruption" tracebacks.
7. `reflex-local-auth` (PyPI 0.5.0, requires `reflex[db]>=0.8.1`) in the db venv: register/login
   flow in a browser (it is also covered by an upgrade cluster — here just check it installs and
   its models migrate against 0.9.12a1).
