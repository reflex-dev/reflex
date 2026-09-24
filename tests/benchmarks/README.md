# Benchmarks

## Event processing benchmarks

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

## Linked shared state benchmarks

```sh
uv run pytest tests/benchmarks/test_shared_state.py --codspeed
```

Linking resolves one `SharedState` substate of many client state trees to a
single shared token's instance. Every event on a linked client pays for that
indirection, and every write fans out to the other clients on the same token.
These run against `StateManagerMemory` and an in-process `EventNamespace` whose
socket emit is stubbed, so the numbers cover taking the shared token's lock,
patching the linked state into the tree, resolving deltas through it and
re-driving one `modify_state` per other client -- not redis or websocket
transport.

- `test_process_event`: the same four counter events (two increments, two
  decrements, so the batch returns the counter to its starting value) under
  four scenarios. `private` is never linked; `linked` adds the shared token's
  lock, the patch into the tree and the router vars `_patch_state` re-dirties;
  `linked_1_client` and `linked_8_clients` add one full `modify_state` and
  emitted update per other client per event, so the fixed cost of the fan-out
  and its per-client slope can be read apart.
- `test_modify_state`: `app.modify_state` cycles, the path a background task or
  an API route takes into client state. Resolves links the same way an event
  does with less on top of it, so a change to the patching machinery is easier
  to see. Ten cycles per measured call, because entering the event loop costs a
  few microseconds no matter what happens inside it.
- `test_link_and_unlink`: what a client pays on the `on_load` that joins it to
  a room. Both halves patch with `full_delta=True`, re-marking every Var of the
  state being swapped in and resolving the delta from the root, which makes
  this the most expensive single operation in the feature. The cycle leaves the
  client unlinked, so every sample links from the same starting point.

`test_fanout_updates_every_linked_client` separately asserts that every other
linked client receives every step of the batch, because the fan-out is silently
skipped for a token with no connected socket -- without it the linked scenarios
could quietly measure an empty task set.

`private` is the baseline for every comparison here, and it is not a
shared-state-free one. The module isolates state registration during collection
and enables the root state's linked-state flags only while a shared benchmark
scenario runs. Other benchmark modules keep their original registrations, app,
and event path. The difference between `private` and `linked` is the cost of
resolving a link, not the cost of the feature existing.

## Var operation benchmarks

```sh
uv run pytest tests/benchmarks/test_var_operations.py --codspeed
```

Building any derived Var — arithmetic, comparisons, string/array/object
methods, `rx.cond` — goes through a `@var_operation`, which interpolates each
operand into the JavaScript expression it returns. The page benchmarks spend
most of their time constructing components, so they barely register a change to
that path; these isolate it.

- `test_arithmetic_operations`, `test_comparison_operations`: flat operations
  over one operand, parametrized by whether it carries `VarData` — a bare Var
  carries none, a state var carries its state name, field name, context
  imports, hook and app wraps.
- `test_boolean_operations`, `test_datetime_operations`: the two-operand cases.
  `&` and `|` interpolate both sides into a `pyAnd`/`pyOr` call and carry their
  own imports; the date comparisons put both into a `compareDatetime` call.
- `test_chained_operations`: each operand is the previous result, so every level
  interpolates a freshly built expression and merged `VarData`. This is the only
  one here that nests; the rest stay flat so the two effects can be read apart.
  Parametrized by depth, each building the same number of operations, so the
  three differ only in how deeply they nest.
- `test_string_operations`, `test_array_operations`, `test_object_operations`,
  `test_cond_operations`: the per-type operations, over state vars. Each stays
  inside its own family — a `cond` whose branches are string operations would
  mostly re-measure `test_string_operations`.
- `test_iteration_operations`: `map`, `filter`, `reduce` and `flat_map`, what
  `rx.foreach` builds. Each traces the Python callable it is given into an
  `ArgsFunctionOperation` first, making them the most expensive family per
  operation built.
- `test_cast_operations`: `to_string()`, `to()` and `bool()` — what
  `rx.text(State.count)` and every truthiness check go through. `bool()`
  interpolates its operand into an `isTrue` call while the other two build
  through a function call and a ToOperation, so both shapes are covered.
- `test_string_concat_operation`, `test_array_index_operation`,
  `test_array_range_operation`, `test_match_operation`: kept apart from their
  families because they are built without interpolating an operand — `+` builds
  a `ConcatVarOperation` that assembles its expression with `str()`,
  `array_item_operation` and `array_range_operation` render their operands with
  `!s`, which likewise calls `str()` rather than `__format__`, and a `match`
  switch is built from its cases. Folded into the family benchmarks they would
  be a few percent of the body, too little for a change to any of them to be
  readable. The concat one renders what it builds, because a
  `ConcatVarOperation` defers its whole assembly to `_cached_var_name` and
  would otherwise report only the allocation.
- `test_format_var_outside_operation`: the control. Interpolating a var in user
  code (`f"Count: {State.count}"`) is a different path from interpolating an
  operand inside an operation, and is not meant to move with it.
- `test_evaluate_var_heavy_page`: a dashboard-shaped page whose props and
  children are derived vars rather than literals — the families mixed and
  nested the way application code writes them.

Every benchmark repeats its operation set enough times to build roughly two
milliseconds' worth of operations uninstrumented; the `*_SETS` constants at the
top of the module hold the counts, which differ because the sets do. Bodies of
a comparable, non-trivial size keep the fixed cost of entering the measured
call from dominating any one benchmark, which is what makes a small benchmark
report a change it never exercised. Retune the counts from the wall-clock table
`uv run pytest tests/benchmarks/test_var_operations.py` prints if an
operation's cost changes materially. The page benchmark is deliberately the one
exception, sized like the other page benchmarks here.

Timing covers building the operations, not rendering them: `Component.render()`
memoizes, so a benchmark around it would measure the cache.
