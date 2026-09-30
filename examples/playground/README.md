# Reflex playground

A multi-page Reflex app covering the framework's surface: state with every kind of
field, every kind of event handler, a sqlite table with forms, uploads, client storage,
charts, grids, markdown and media, custom components, and rooms whose visitors share
one `rx.SharedState` live. It targets reflex 0.8.23 and later, and it is the app the
Reflex macro benchmarks drive through the real `reflex` CLI.

```bash
uv run reflex run
```

From the repository root, `uv run --directory examples/playground --project ../.. reflex run`
runs it against this checkout instead of the latest release (the workspace's `dev`
group has the packages below).

- **Dependencies.** `reflex[db]` for the `rx.Model` table (reflex 0.9 moved
  `sqlmodel` and `alembic` into the `db` extra; 0.8.23 has them either way) and
  `plotly`, which `rx.plotly` imports when it renders. The macro benchmarks install
  the same packages into every subject venv (`SUBJECT_REQUIREMENTS` of reflex-bench).
- **Database.** `rxconfig.py` sets `db_url` to `sqlite:///playground.db`. At backend
  start a lifespan task creates the table and, when it is empty, inserts 2000
  products in one transaction. `playground/seed.py` builds them from a fixed
  `random.Random` seed, so every machine gets the same rows. The app runs without
  migrations, so reflex warns that the database is not initialized; reflex 0.9.2
  and later also warn that `rx.Model` is deprecated. `playground.db` stays out of
  git; delete it to reseed.
- **Tailwind.** `rxconfig.py` adds `rx.plugins.TailwindV4Plugin()` unless
  `PLAYGROUND_TAILWIND=0`, the default of `reflex init` (the `/about` page and the
  data sidebar use Tailwind classes). The benchmarks never set it, and the
  variable is not part of their series key: setting it in the shell you run
  reflex-bench from changes the build, and the results, of the same series.

## Pages

Every page shares `layout.py`: the navigation bar, the content and the benchmark
hooks. The appearance toggles live on `/settings`, not in the navigation bar: on
reflex 0.8.23, a page rendering `rx.color_mode.button` stops applying its hot
updates. The data pages add a
sidebar inside it (`data_layout`, a nested layout).

| Route | Shows |
| --- | --- |
| `/` | The benchmark landing page: the item list (`rx.foreach`) and the leaf hot reload marker. |
| `/counter` | A counter and its parity (`rx.cond`). |
| `/board` | The shared board of the event benchmarks: join `lobby`, or a board typed into `#board-token`. |
| `/item/[item_id]` | A dynamic route showing its argument. |
| `/events` | One button per kind of handler: sync, arguments, async, generator, background, chain, toast, `rx.call_script`, `rx.download`, `rx.redirect`, `get_state` of a sibling. |
| `/tasks` | Dataclass rows edited in place through the mutable proxy, nested tags, a chain of three computed vars. |
| `/data` | The product table: filter, category, sort and pagination over sqlite; its `on_load` runs the first query. |
| `/data/product/[product_id]` | A product's edit form: validation, update and delete. |
| `/data/new` | The same form, creating a product. |
| `/data/analytics` | An expensive computed var (a sort over every row) and a recharts bar chart. |
| `/forms` | A sign-up form validated on blur and on submit. |
| `/upload` | `rx.upload` with progress; files land in `uploaded_files/`. |
| `/storage` | `rx.Cookie`, `rx.LocalStorage` and `rx.SessionStorage`. |
| `/charts` | Recharts line, area and bar charts over a computed series, and a plotly figure built as a dict. |
| `/grids` | The same rows in `rx.data_table` (gridjs) and `rx.data_editor`. |
| `/content` | `rx.markdown`, `rx.code_block`, lucide icons, `rx.moment`, `rx.audio` and `rx.video`. |
| `/widgets` | `rx.match`, nested `rx.foreach`, `rx.memo`, `rx.ComponentState`, `rx.dynamic` and a custom component with its own JavaScript and a page hook. |
| `/room/[room_id]` | A room: presence, a shared counter and broadcasts (below). |
| `/settings` | Radix tabs, switches, sliders and radio groups over a dict of preferences. |
| `/about` | Static content styled with Tailwind classes. |
| `404` | The custom not-found page. |

The backend also answers `GET /api/playground/stats` with the product count and
the total stock: an ASGI middleware added with `rx.App(api_transformer=...)`
(`playground/api.py`).

## Rooms: a live collaborative page

Open `/room/<name>` in two browsers: both join the room's board, an `rx.SharedState`
linked to the token `<name>` (`BoardState.enter_room` calls `_link_to`), so they
share its counter and see each other's name under "Here". `+` changes the shared
counter once, `+10 at once` sends ten increments together (every visitor contends
for one state), and `Broadcast` sends one event that every visitor receives (a
fan-out). `Leave` takes the name off the room and unlinks the session. A name
stays listed until its visitor leaves: closing the tab does not remove it.

It works with each state manager: `REFLEX_STATE_MANAGER_MODE=memory` or `disk`,
or redis with `REFLEX_REDIS_URL=redis://localhost:6379` (for example with
`docker run --rm -p 6379:6379 redis:7`). With redis, reflex 0.8.23 sends a room's
updates only to the visitors connected to the same backend worker, so run it
with `GRANIAN_WORKERS=1` there; reflex 0.9 reaches every worker.

## Element ids

Interactive elements carry kebab-case ids prefixed by their page. Elements
rendered by `rx.foreach` carry none: an id built from a var gets a ref whose
name changes on every compile, which makes the build differ between two
compiles of the same app.

| Page | Ids |
| --- | --- |
| every page | the benchmark hooks below |
| `/counter` | `count`, `increment`, `decrement` |
| `/board` | `board-join`, `board-token`, `board-join-token`, `board-count`, `board-increment`, `board-seq` |
| `/item/[item_id]` | `item-id` |
| `/events` | `events-total`, `events-log-size`, `events-sync`, `events-args`, `events-async`, `events-generator`, `events-background`, `events-chain`, `events-repeat`, `events-toast`, `events-script`, `events-download`, `events-sibling`, `events-redirect`, `events-clear`, `events-progress`, `events-running`, `events-script-result`, `events-sibling-summary`, `events-log` |
| `/tasks` | `tasks-draft`, `tasks-add`, `tasks-filter`, `tasks-list` (a row per task, its checkbox first), `tasks-progress`, `tasks-clear-done`, `tasks-reset`, `tasks-note-urgent`, `tasks-note-later`, `tasks-note-review` |
| `/data` | `data-sidebar`, `data-filter`, `data-category`, `data-reset`, `data-table`, `data-sort-<column>` (`id`, `name`, `category`, `price-cents`, `stock`, `rating`), `data-previous`, `data-page`, `data-next` |
| `/data/product/[product_id]`, `/data/new` | `data-sidebar`, `product-heading`, `product-form`, `product-name`, `product-category`, `product-price-cents`, `product-stock`, `product-rating`, `product-save`, `product-delete`, `product-delete-confirm` |
| `/data/analytics` | `data-sidebar`, `analytics-count`, `analytics-rating`, `analytics-leaderboard` |
| `/forms` | `forms-signup`, `forms-username`, `forms-email`, `forms-age`, `forms-plan`, `forms-terms`, `forms-submit`, `forms-reset`, `forms-error-<field>`, `forms-count`, `forms-signups`, `forms-forget` |
| `/upload` | `upload-files` (the drop zone, also its upload id), `upload-selected`, `upload-start`, `upload-clear`, `upload-progress`, `upload-stored` |
| `/storage` | `storage-values`, `storage-cookie`, `storage-local`, `storage-session`, `storage-forget` |
| `/charts` | `charts-kind`, `charts-shift`, `charts-points`, `charts-resolution`, `charts-recharts`, `charts-plotly` |
| `/grids` | `grids-edits`, `grids-table`, `grids-editor`, `grids-reset` |
| `/content` | `content-markdown`, `content-code`, `content-icons`, `content-dates`, `content-audio`, `content-video` |
| `/widgets` | `widgets-stats`, `widgets-layout`, `widgets-add-row`, `widgets-reset`, `widgets-matrix`, `widgets-stepper-a-decrement`, `widgets-stepper-a-value`, `widgets-stepper-a-increment` (and `-b-`), `widgets-dynamic-shape`, `widgets-next-shape`, `widgets-clock` |
| `/room/[room_id]` | `room-name`, `room-me`, `room-leave`, `room-presence-count`, `room-presence`, `room-count`, `room-increment`, `room-burst`, `room-broadcast`, `room-last` |
| `/settings` | `settings-tab-profile`, `settings-tab-notifications`, `settings-tab-appearance`, `settings-name`, `settings-volume`, `settings-switch-emails`, `settings-switch-sounds`, `settings-switch-beta`, `settings-on`, `settings-accent`, `settings-compact`, `settings-color-mode`, `settings-color-mode-button`, `settings-preview` |
| `/about` | `about-features` |
| `404` | `not-found`, `not-found-home` |

## Size

Counted on reflex 0.9.12 by evaluating every page function and walking the
components' `children` (an `rx.foreach` counts its template once), so drift
shows in review:

| | Count |
| --- | --- |
| Pages | 21 |
| Component instances | 2986 (from 95 on `/item/[item_id]` to 236 on `/data`) |
| States | 16 direct children of `rx.State` (`BoardState` under the shared state base), plus one per `rx.ComponentState` instance (2) |
| Event handlers | 82 (70 outside the benchmark states) |
| Computed vars | 20 (14 outside the benchmark states) |
| Seeded products | 2000 |

The `rx.dynamic` badge on `/widgets` is expensive by design: its var is
uncached and always dirty, so reflex rebuilds the component on every event of
every state, `BenchState.set_seq` included. On a 4-core VM the closed-loop
throughput of `set_seq` (disk state manager, 10 sessions) was about 2,200
events per second without that one call and about 900 with it. The event and
memory benchmarks measure the app with it.

## Benchmark contract

The benchmarks rely on the names below; keep each with the same meaning. The
harness imports `BenchState` and `BoardState` from `playground.state` in the
subject's interpreter (`suites/events.py`), and both stay direct children of
`rx.State` (`BoardState` through the shared state base): their full names are on
the wire. Add nothing to `BenchState`, whose `set_seq` is the "one var, no computed
var" event. `wire.navigate` loads `/counter` and `/item/42` after hydrating `/`, and
`/` is the page the browser benchmarks load, so it stays the light landing page:
the new surface lives on other pages, and only the index page imports
`components/marker.py` (a leaf edit for `hmr.render.leaf` and
`lifecycle.compile.incremental`).

Every page renders these ids through `layout.py`, except `#bench-marker-leaf`,
which only the index page renders, and the `board-*` and `count`/`increment` ids of
their pages.

| Id | Shows |
| --- | --- |
| `bench-hydrated` | Present (and empty) once the page is hydrated: websocket connected and the first state update applied. With Playwright, wait for it with `state="attached"`. |
| `bench-seq` | `BenchState.last_seq`, which the event handler `BenchState.set_seq(seq: int)` sets. The button `#bench-set-seq` fires `set_seq(7)`. Over the websocket, the handler is `reflex___state____state.playground___state____bench_state.set_seq`. |
| `bench-parts` | The computed var chain `BenchState.parts_total` → `parts_scaled` → `parts_label`, which reads the vars `set_seq_complex` sets. |
| `bench-handler-value` | `BenchState.handler_value`, which the event handler `BenchState.bench_value()` sets to `HANDLER_MARKER`. The button `#bench-handler` fires it. |
| `bench-marker-root` | `ROOT_MARKER` of `playground/layout.py`, which every page imports. |
| `bench-marker-leaf` | `LEAF_MARKER` of `playground/components/marker.py`, which only the index page imports. |
| `board-join` | A button firing `BoardState.join("lobby")`, which links the session to the board `lobby`. |
| `board-count` | `BoardState.count`, shared by every session linked to the same board; `#board-increment` fires `BoardState.increment`. |
| `board-seq` | `BoardState.last_seq` and `BoardState.last_client`, which `set_seq_shared` sets. |
| `count`, `increment` | On `/counter`: `PlaygroundState.count` and the button incrementing it, which `hmr.reconnect` clicks until the count changes. |

The hot reload benchmarks rewrite exactly the string literal on a line carrying a
`# bench:hmr-target <name>` pragma, then wait for the new value to show:

| Pragma line | File | Shows in |
| --- | --- | --- |
| `LEAF_MARKER = "m-initial-leaf"  # bench:hmr-target leaf` | `playground/components/marker.py` | `#bench-marker-leaf` |
| `ROOT_MARKER = "m-initial-root"  # bench:hmr-target root` | `playground/layout.py` | `#bench-marker-root` |
| `HANDLER_MARKER = "m-initial-handler"  # bench:hmr-target handler` | `playground/state.py` | `#bench-handler-value`, once `bench_value` runs |

Keep each target on its own line, in exactly this form, and add no other
`# bench:hmr-target` line. `assets/mark.svg` (shown as `#bench-mark`, with no
`width` or `height` of its own) and `assets/playground.css` (whose `.bench-hooks`
rule keeps `font-size: 0.75rem`, the literal `hmr.css` rewrites) are there for the
asset hot reload benchmarks; `assets/favicon.ico` is the one `reflex init`
creates, and `assets/chime.wav` the sound of the media players.

The event benchmarks send these `BenchState` handlers over the websocket, each with the
payload `{"seq": <int>}`. Every one sets `last_seq` to `seq`, so the delta of
`reflex___state____state.playground___state____bench_state` echoes it as
`last_seq_rx_state_`:

| Handler | Also does |
| --- | --- |
| `set_seq` | Nothing else. |
| `set_seq_complex` | Sets `part_a`, `part_b` and `part_c`, which the `#bench-parts` computed var chain reads. |
| `set_seq_cross` | Increments `PlaygroundState.count` through `get_state` (an async handler). |
| `set_seq_background` | Runs as a background task: yields once, then sets `last_seq` in `async with self`. |

The websocket event name is the handler's full name, for example
`reflex___state____state.playground___state____bench_state.set_seq_complex`.

The shared state benchmarks use `BoardState`, an `rx.SharedState`, whose full name on the
wire is `reflex___state____state.playground___state____board_state`:

| Handler | Payload | Does |
| --- | --- | --- |
| `join` | `{"token": <str>}` | Links the session to the board `token` (`_link_to`); the reply delta carries every `BoardState` var. |
| `set_seq_shared` | `{"seq": <int>, "client": <int>}` (`client` defaults to 0) | Sets `last_seq` and `last_client`, so the delta echoes them as `last_seq_rx_state_` and `last_client_rx_state_` to the sender and to every other session linked to the same board. |

A benchmark links its sessions to a fresh board token per load, so no board carries
the linked clients of an earlier load.

## Changing the app

- **Keep it running on reflex 0.8.23.** The benchmarks are backfilled to 0.8.23, so
  the app imports only `reflex` and uses no API added after 0.8.23, unless guarded like
  `RadixThemesPlugin` in `rxconfig.py`. The `examples` CI workflow compiles the app with
  0.8.23 and with this checkout.
- **Update the content hash.** `.content-hash` identifies this version of the app in
  the benchmark results, so any change here resets the benchmark baselines. The
  `hash-examples` pre-commit hook rewrites it (or run
  `uv run python scripts/hash_examples.py`), and CI fails when it is stale. The hash
  covers every file git tracks or would track here, so commit new files and delete
  stray ones.
- **Commit no lock files.** The app runs against several reflex versions, so
  `reflex.lock/` and `uv.lock` stay out of git.
