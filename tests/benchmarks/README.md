# Event processing benchmarks

```sh
uv run pytest tests/benchmarks/test_event_processing.py --codspeed
```

Omit `--codspeed` for local wall-clock measurements.

- `counter`: three increments through the in-memory event processor.
- `table`: six filter/sort events over 1,000 dataclass orders, including computed
  rows and totals and JSON encoding of each `StateUpdate`. The batch cycles
  through open/all/paid orders twice, reversing sort direction on every event.

The table is warmed before timing; each batch returns to the same filter and
sort direction. Timing includes processor startup/shutdown, but excludes initial
hydration, Socket.IO packet framing, network transport, databases, and rendering.
