# Event processing benchmarks

Run the event benchmarks with:

```sh
uv run pytest tests/benchmarks/test_event_processing.py --codspeed
```

Omit `--codspeed` for local wall-clock measurements.

`test_process_event` measures three counter increments through the event processor.
`test_process_table_event` models an order-management dashboard with 1,000
dataclass rows. Each sample runs six events: filter open orders, clear the filter,
and filter paid orders, twice, reversing the sort direction on every event.
Each update includes sorted matching rows and a computed total.

The table benchmark warms the state before timing and returns to the same filter
and sort direction after each sample. It covers event queueing, in-memory state
access, mutations, proxied row iteration, computed-variable invalidation and
evaluation, delta generation, and Reflex JSON serialization. Processor startup
and shutdown are included. Initial hydration, Socket.IO packet framing, network
transport, database access, and browser rendering are excluded.

`test_table_event_deltas` checks serialized results across two batches separately
from timing, so missing rows or stale computed values cannot silently look like
performance improvements.
