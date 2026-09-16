# Event processing benchmarks

```sh
uv run pytest tests/benchmarks/test_event_processing.py --codspeed
```

Omit `--codspeed` for local wall-clock measurements.

- `counter`: two increments and two decrements through the in-memory event
  processor.
- `table`: six filter/sort events over 1,000 dataclass orders, including computed
  rows and totals and JSON encoding of each `StateUpdate`. The batch cycles
  through open/all/paid orders twice, reversing sort direction on every event.

The table is warmed before timing, and both batches return state to its
starting point so every sample measures identical work.
`test_table_event_deltas` separately verifies the serialized rows, sort
direction, and totals that the table benchmark encodes.
Timing includes processor startup/shutdown, but excludes initial
hydration, Socket.IO packet framing, network transport, databases, and rendering.
