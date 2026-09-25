# Reflex playground

A small multi-page Reflex app: a navigation bar, a counter, a dynamic route, a list
rendered with `rx.foreach` and a board shared between sessions with `rx.SharedState`.
It targets reflex 0.8.23 and later, and it is the app the Reflex macro benchmarks drive
through the real `reflex` CLI.

```bash
uv run reflex run
```

From the repository root, `uv run --directory examples/playground --project ../.. reflex run`
runs it against this checkout instead of the latest release. The pages are `/`,
`/counter`, `/board` and `/item/[item_id]` (for example `/item/42`).

## Benchmark contract

The benchmarks rely on these element ids. Every page renders them through `layout.py`,
except `#bench-marker-leaf`, which only the index page renders, and the `board-*` ids,
which only `/board` renders.

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

The hot reload benchmarks rewrite exactly the string literal on a line carrying a
`# bench:hmr-target <name>` pragma, then wait for the new value to show:

| Pragma line | File | Shows in |
| --- | --- | --- |
| `LEAF_MARKER = "m-initial-leaf"  # bench:hmr-target leaf` | `playground/components/marker.py` | `#bench-marker-leaf` |
| `ROOT_MARKER = "m-initial-root"  # bench:hmr-target root` | `playground/layout.py` | `#bench-marker-root` |
| `HANDLER_MARKER = "m-initial-handler"  # bench:hmr-target handler` | `playground/state.py` | `#bench-handler-value`, once `bench_value` runs |

Keep each target on its own line, in exactly this form. `assets/favicon.ico` (the one
`reflex init` creates) and `assets/playground.css` are there for the asset hot reload
benchmarks.

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
