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

# Var operation benchmarks

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
- `test_boolean_operations`: `&`, `|` and `~`. The two-operand ones interpolate
  both sides into a `pyAnd`/`pyOr` call and carry their own imports.
- `test_chained_operations`: each operand is the previous result, so every level
  interpolates a freshly built expression and merged `VarData`. This is the only
  one here that nests; the rest stay flat so the two effects can be read apart.
  Parametrized by depth, because each added level costs more than the last.
- `test_string_operations`, `test_array_operations`, `test_object_operations`,
  `test_cond_operations`: the per-type operations, over state vars. Each stays
  inside its own family — a `cond` whose branches are string operations would
  mostly re-measure `test_string_operations`.
- `test_string_concat_operation`, `test_array_index_operation`: concatenation
  and indexing, kept apart from their families because they are built without
  interpolating an operand — `+` builds a `ConcatVarOperation` that assembles
  its expression with `str()`, and `array_item_operation` renders its operands
  with `!s`, which calls `str()` rather than `__format__`. Folded into the
  family benchmarks they would be a few percent of the body, too little for a
  change to either to be readable.
- `test_format_var_outside_operation`: the control. Interpolating a var in user
  code (`f"Count: {State.count}"`) is a different path from interpolating an
  operand inside an operation, and is not meant to move with it.
- `test_evaluate_var_heavy_page`: a dashboard-shaped page whose props and
  children are derived vars rather than literals — the families mixed and
  nested the way application code writes them.

Timing covers building the operations, not rendering them: `Component.render()`
memoizes, so a benchmark around it would measure the cache.
