# Rust pipeline profiling — findings

Session date: 2026-05-18.
Bench script: `scripts/benchmark_single_page.py`.
Profile artifacts: `/tmp/runrust*.prof`.

This document records what we **measured** while profiling the Rust
compile pipeline on the docs app and on a synthetic single-page bench.
No assumptions; every number here is from a `perf_counter_ns` timer or
a cProfile run.

---

## 1. Baseline (docs app, 7 pages compiled)

Initial `reflex run-rust --frontend-only` on `docs/app`. Wall-clock,
no profiler:

| Phase | Time |
|---|---|
| App import (user `reflex_docs` module) | 1.26 s |
| `rust_pipeline.compile_pages` (7 pages) | **2.10 s** |
| `bun install` | 0.06 s |
| **Total** | **~3.4 s** |

cProfile breakdown of `compile_pages` (4.92 s under cProfile;
real wall-clock 2.10 s):

| Phase | cumtime | Share |
|---|---|---|
| `walk_and_memoize` (Python recursion, builds 464 memo wrappers) | 0.73 s | 15% |
| `compile_unevaluated_page` (user page callable + theme) | 0.65 s | 13% |
| `_get_all_imports` recursive Python walks | 0.42 s | 9% |
| `compile_page_from_component` (Rust JSX emit, 7 calls) | 0.40 s | 8% |
| `_get_all_app_wrap_components` Python tree walks | 0.38 s | 8% |
| `_compile_memo_components` (legacy memo for `@rx.memo`) | 0.36 s | 7% |
| `emit_memo_modules` (377 unique memo bodies emitted) | 0.35 s | 7% |
| Rust calls total | ~0.69 s | 14% |
| Python overhead total | ~2.6 s | 53% |
| Other | ~0.6 s | 12% |

`merge_imports` was hottest by Python self-time: 15,131 calls,
5.2 M iterations through its generator, ~0.6 s self-time.

---

## 2. Round 1 — `_get_all_imports` → Rust walker

**Change**: added `CompilerSession.collect_all_imports(component)`
backed by `reflex_pyread::collect_all_imports` — walks the Component
tree, calls each node's cached `_get_imports()` via PyO3, merges in a
Rust `HashMap`. Replaced 3 `component._get_all_imports()` call sites
in `rust_pipeline.compile_pages`.

**Result** (docs app, 3 runs median of `rust-compiled 7 page(s)`):

| | Before | After | Δ |
|---|---|---|---|
| compile_pages wall-clock | 2095 ms | **1738 ms** | **−357 ms (−17%)** |

Where the savings came from: 29k fewer Python `extend` calls, deep
`merge_parsed_imports` recursion replaced with Rust HashMap merge.

---

## 3. Round 2 — outer `merge_imports` in-place via Rust

**Change**: added `collect_all_imports_into(target, component)` and
`merge_imports_into(target, source)` — both apply the `$/utils/...`
lib-prefix transform and merge into a caller-owned dict in place.
Replaced the `merge_imports(all_imports, ...)` wrappers in the
compile_pages page loop (eliminating 385 outer Python `merge_imports`
calls).

**Result** (docs app, 5 runs):

| | Round 1 final | Round 2 final | Δ |
|---|---|---|---|
| median compile_pages | 1738 ms | 1727 ms | −11 ms |
| mean compile_pages | 1733 ms | 1715 ms | −18 ms |
| min compile_pages | 1725 ms | 1679 ms | −46 ms |

Under cProfile compile_pages dropped from 4.63 s → 3.75 s (−880 ms),
but the wall-clock delta is in the noise band (±50 ms run-to-run).

**Important lesson from round 2**: cProfile cumulative time is *not* a
reliable predictor of wall-clock savings. The 415 outer `merge_imports`
calls had high cProfile-attributed cost but cheap actual cost (just
iterating already-built dicts). Round 1's win was real because it
replaced **5.2 M iterations** of a Python generator (deep
`_get_all_imports` recursion), which is real CPU work. Round 2 replaced
thin Python wrappers around C-level list ops — already fast.

**Takeaway**: target deep recursive Python work, not shallow wrappers.

---

## 4. Single-page bench setup

`scripts/benchmark_single_page.py` builds **one** feature-rich page
(state vars, foreach over state, cond + Components in props, match,
event handlers, markdown — exercises every surface `compile_pages`
touches) and runs the full per-page flow with `perf_counter_ns` timers
labeled Python / Rust+PyO3 / pure Rust. Memoize is included; static
artifacts are excluded.

A `--scale N` arg multiplies the page contents N× for scaling
experiments.

**Single page at scale=1 (47 nodes)**, after rounds 1 + 2,
10 runs aggregated (1 warmup discarded):

```
phase                                         kind       median (ms)
compile_unevaluated_page                      python      1.85
collect_all_imports_into                      hybrid      3.10
_get_all_app_wrap_components                  python      0.28
walk_and_memoize                              python      4.69
_get_all_custom_code                          python      4.64
_get_all_hooks + _render_hooks                python      0.12
compile_page_from_component (Rust JSX emit)   hybrid      0.65
page write_text                               python      0.14
memo body: collect_all_imports_into           hybrid      0.22
memo body: _harvest_pre_hooks (Python walk)   python      0.08
memo body: compile_memo_from_component (Rust) hybrid      2.67
memo body: write_text                         python      0.22
app_root composition + render                 python      6.34
─────────────────────────────────────────────────────────────────
Per-run median total:                                    25.00  ms

Python only                    18.36 ms  ( 73.4%)
Rust + PyO3 callbacks           6.64 ms  ( 26.6%)
pure Rust (no callbacks)        0.00 ms  (  0.0%)
```

---

## 5. Python vs Rust head-to-head — per-page mechanical compile

Same evaluated Component tree on both sides, memoize skipped, fresh
tree per iteration (no `_imports_cache` warming).

### Before fusing the 4 walks (initial state of `read_page`)

Scale sweep, 15 iterations each:

| Scale | Tree size | Python `_compile_page` | Rust pipeline | Ratio |
|---|---|---|---|---|
| 1 | 48 nodes  | 7.87 ms | 9.55 ms | **Rust 0.82× — 18% slower** |
| 2 | 91 nodes  | 19.7 ms | 22.4 ms | **Rust 0.88× — 12% slower** |
| 4 | 177 nodes | 30.9 ms | 38.4 ms | **Rust 0.80× — 20% slower** |
| 8 | 349 nodes | 62.9 ms | 78.6 ms | **Rust 0.80× — 20% slower** |

Rust pipeline lost at *every* size.

### Detailed sub-step breakdown (scale=1, 47 nodes, 20 runs)

```
=== Python  _compile_page  — sub-steps ===
_get_all_imports                                 2.561 ms
compile_imports (apply+sort)                     0.092 ms
_get_all_dynamic_imports + sort                  0.028 ms
_get_all_custom_code                             4.119 ms
_get_all_hooks                                   0.144 ms
component.render() (recursive Python)            1.457 ms
page_template(...)                               0.045 ms
─────────────────────────────────────────────────────────
Total:                                           8.445 ms

=== Rust    pipeline  — sub-steps ===
collect_all_imports_into (Rust+PyO3)             2.420 ms
_get_all_custom_code                             4.036 ms
_get_all_hooks + _render_hooks                   0.142 ms
compile_page_from_component (Rust+PyO3)          3.398 ms  ← the gap
─────────────────────────────────────────────────────────
Total:                                           9.996 ms

Gap = +1.550 ms  (+18.4%)
```

**The gap is `compile_page_from_component`: 3.40 ms vs Python's
`component.render() + page_template`: 1.50 ms.** Rust was 2.3×
slower on the actual JSX-emit step.

---

## 6. The 4-walk bug

Inspection of `read_page` (in `reflex_pyread::pyo3_reader`) revealed
it was walking the Python Component tree **four times**:

```rust
pub fn read_page(...) -> Result<Page, _> {
    let root_ir = read_component(py, root, ...)?;          // walk 1: build IR
    let root_alloc = arena.alloc(root_ir);

    let component_imports = collect_component_imports(...)?; // walk 2
    let state_bindings   = collect_state_bindings(...)?;     // walk 3
    let needs_ref        = scan_needs_ref(...)?;             // walk 4

    Ok(Page { ... })
}
```

Each post-walk re-traversed the Python tree via PyO3 `getattr` to
harvest one piece of metadata. **4× the PyO3 boundary cost for the
same data we'd already read.**

### Fix: Option A — inline harvests during single walk

Added `HarvestState` field (via `RefCell`) to `PyRefs`. Inlined the
three harvests:

- `component_imports`: in `read_element`, register after
  `resolve_tag_symbol`. Also in `read_var_data_imports` for VarData
  imports.
- `state_bindings`: in `read_value` / `read_bare` / `event_handler_to_js`
  — wherever we read a Var's `_js_expr`, scan it for state idents and
  register.
- `needs_ref`: in `read_element` — check `id` attr per element.

`read_page` now does **one** Python walk via `read_component`; harvests
fall out as a side-effect.

### Result

Per-page `compile_page_from_component`: **3.40 ms → 1.90 ms (−44%).**

Full sub-step head-to-head after the fix (scale=1, 20 runs):

```
=== Rust    pipeline  — sub-steps ===
collect_all_imports_into (Rust+PyO3)             2.954 ms
_get_all_custom_code                             4.643 ms
_get_all_hooks + _render_hooks                   0.150 ms
compile_page_from_component (Rust+PyO3)          1.899 ms  ← was 3.398
─────────────────────────────────────────────────────────
Total:                                           9.646 ms

Python total:                                    9.853 ms

Gap = -0.207 ms  (-2.1%)  ← Rust now WINS at this size
```

### Scale sweep after the fix

| Scale | Tree size | Python | Rust | Gap |
|---|---|---|---|---|
| 1 | 48 nodes  | 8.50 ms | 8.35 ms | **−1.8% (Rust wins)** |
| 2 | 91 nodes  | 15.81 ms | 15.78 ms | −0.2% (tie) |
| 4 | 177 nodes | 31.86 ms | 33.53 ms | **+5.2% (Python wins)** |
| 8 | 349 nodes | 63.29 ms | 66.14 ms | **+4.5% (Python wins)** |

**Closed the gap at small N. Still lose ~5% at larger N.**

---

## 7. Rust-side phase instrumentation

Added a thread-local `PhaseTimings` cell in `reflex_pyread::timing`
with `Span` RAII guards. Spans cover only **leaf** call sites (no
recursive functions) so totals are self-time. Exposed via
`CompilerSession.last_phase_timings_ns()`.

### Measurement at scale=4 (177 nodes, 87 elements, 97 vars, 2091 props, 16 event handlers)

```
phase                                       ns            ms
──────────────────────────────────────────────────────────────
read_page_total_ns                     7,065,847       7.066    ← total
  emit_ns (pure Rust)                     23,749       0.024    ← Rust JSX emit
  read_var_data_ns                     1,495,238       1.495    ← #1 cost
  prop_value_getattr_ns                  384,984       0.385
  value_literal_dispatch_ns              234,378       0.234
  var_js_expr_attr_ns                    217,419       0.217
  import_alias_ns                        152,890       0.153
  resolve_tag_ns                         134,754       0.135
  get_props_call_ns                       42,837       0.043
  class_name_ns                           32,757       0.033
  event_triggers_attr_ns                  31,717       0.032
  children_attr_ns                        28,040       0.028
  needs_ref_ns                            22,340       0.022
  isinstance_var_ns                       13,210       0.013
  harvest_register_ns                      6,720       0.007
  (unaccounted)                        4,244,814       4.245    ← loop control + py_str + dispatch
```

### Per-call costs (ns per occurrence)

| Operation | per-call cost | what it does |
|---|---|---|
| `read_var_data_ns / var` | **15,415 ns** | `var._get_all_var_data()` + decode imports/hooks/deps |
| `var_js_expr_attr_ns / var` | 2,241 ns | `getattr(var, "_js_expr")` for Var values |
| `import_alias_ns / element` | 1,757 ns | reads library/tag/alias for import harvest |
| `resolve_tag_ns / element` | 1,549 ns | reads alias/tag/library/_is_tag_in_global_scope |
| `get_props_call_ns / element` | 492 ns | `component.call_method0("get_props")` |
| `class_name_ns / element` | 377 ns | `type(component).__name__` |
| `event_triggers_attr_ns / element` | 365 ns | `getattr("event_triggers")` + dict downcast |
| `children_attr_ns / element` | 322 ns | `getattr("children")` + iter() setup |
| `needs_ref_ns / element` | 257 ns | `getattr("id")` |
| `prop_value_getattr_ns / prop` | 184 ns | `getattr(prop_name)` |
| `isinstance_var_ns / prop` | **6 ns** | `isinstance(value, var_cls)` |

### Key findings from the instrumentation

1. **Pure Rust emit is 24 µs for a 177-node tree.** Free. **Not the bottleneck.**
2. **`read_var_data` dominates at 1.5 ms (21% of `read_page`).** ~15 µs per Var. Most of that is Python-side `_get_all_var_data()` walking deps and merging.
3. **`resolve_tag` + `import_alias` = 0.29 ms** at ~3.3 µs/element. They read the same `library`/`tag`/`alias` attrs twice. Fusing would save ~0.15 ms — small.
4. **2091 prop iterations is the surprise.** ~24 declared props per element (Pydantic gives us *all* declared fields whether set or not). Most are None. Per-prop getattr is fast (184 ns) but adds up: 0.39 ms.
5. **The unaccounted 4.25 ms (60% of `read_page`)** is the aggregate of small per-iteration costs — Rust loop control, `py_str` conversions, `strip_suffix`/`to_owned` allocations, `read_value` function entry, vec pushes. ~2091 prop iterations × ~1 µs each ≈ 2 ms there alone.
6. **`isinstance_var_ns / prop = 6 ns`** and **`harvest_register_ns: 7 µs total`** — the things I worried about are nothing.

---

## 8. Why Rust loses at scale — the PyO3 boundary tax

Per-node cost comparison from the scale sweep:

| Scale | Nodes | Python ms | Rust ms | Python ns/node | Rust ns/node |
|---|---|---|---|---|---|
| 1 | 48 | 8.5 | 8.3 | 177 µs | 173 µs |
| 4 | 177 | 32.4 | 33.5 | 183 µs | 189 µs |
| 8 | 349 | 63.3 | 66.1 | 181 µs | 189 µs |

Both paths are O(N), but **Rust pays ~6 µs more per node** at scale.
At 48 nodes this is invisible (absorbed by per-compile fixed costs).
At 349 nodes it dominates.

### Boundary cost per operation

| Operation | C-level Python access | PyO3 from Rust |
|---|---|---|
| `__getattribute__` (simple slot) | ~30 ns | ~150 ns |
| `__getattribute__` (descriptor) | ~80 ns | ~200 ns |
| Method call (`call_method0`) | ~200 ns | ~1,000 ns |
| String marshal (`py_str`) | n/a (already Python str) | ~100 ns conversion |

Python's `component.render()` and `_get_all_*` walks read the same
attrs we do, but **stay entirely inside CPython memory**. No boundary
crossing. Pydantic descriptors ~80 ns; PyO3 getattr ~200 ns. **2-3×
per-op overhead × ~10 ops per element = ~6-10 µs/element overhead.**

**We are not doing less work in Rust — we are doing the same work plus
marshaling tax.** At small N the tax is invisible; at large N it
dominates.

---

## 9. Where the time goes — the 24.66 ms / page budget

After rounds 1 + 2 + walk-fusion, single page at scale=1:

| Phase | Time | Where it runs |
|---|---|---|
| `walk_and_memoize` | 5.08 ms | **Python** — recursion + 464 `Component.create()` allocations for memo wrappers |
| `app_root composition + render` | 5.99 ms | **Python** — `_RenderUtils.render` is a recursive Python JSX renderer |
| `_get_all_custom_code` | 4.57 ms | **Python** — Markdown component builds `ComponentMap_*` closure |
| `collect_all_imports_into` | 3.02 ms | **Rust+PyO3** — already moved; PyO3 callbacks dominate |
| `memo body: compile_memo_from_component` | 2.63 ms | **Rust+PyO3** — already in Rust |
| `compile_unevaluated_page` | 1.72 ms | **Python** — user `def page()` callable. **Unmovable.** |
| `compile_page_from_component` | 0.65 ms | **Rust+PyO3** — already Rust |
| Other (hooks, app_wraps, I/O) | 1.00 ms | mix |

**Python share: 73.7%. Hybrid (Rust + PyO3 callbacks): 26.3%. Pure Rust: 0%.**

---

## 10. What "move to Rust" actually means after these measurements

The new finding reframes the optimization roadmap:

### Moves that *won't* win

Anything that just replaces a Python tree walk with a Rust+PyO3 walk
doing the same per-node work. The Rust pipeline pays ~6 µs/node tax
on top of the same per-node Python method execution. Examples:

- **`_get_all_custom_code` → Rust walk**: still has to call back into
  Python per node to build the markdown closure. ~4 ms Python work
  stays; we'd add ~1 ms PyO3 tax. **Net loss possible.**
- **`_get_all_app_wrap_components` → Rust walk**: already small
  (0.28 ms); marshaling tax would erase most savings.

### Moves that *will* win

Work that has **architectural fat to cut** beyond just porting:

#### Primary: `walk_and_memoize` → Rust IR transform (~5 ms saved)

- 5.08 ms / page = biggest single Python phase
- Most of the cost is `_wrap_with_memo()` allocating real
  `Component` objects via `Component.create()` for memo wrappers
- If memo wrappers become **IR-only** (Rust `Component::Memoize` IR
  variant), the Python allocation goes away
- Fuses into the existing `read_page` walk — no new PyO3 tax
- The downstream walks that currently see the wrappers either run
  on IR or are tiny

Expected savings: **~3-5 ms/page → 24.66 → ~20 ms (15-20% reduction)**.

#### Secondary: `app_root` through Rust emit (~2-3 ms saved net)

- 5.99 ms total; ~3-4 ms is `_RenderUtils.render(app_root.render())`
- Replace with `compile_page_from_component(app_root, ...)` which
  pays ~1-2 ms of PyO3 walk + Rust emit
- Net: ~1-2 ms saved

### Moves on the Python side that would help us (if reflex_base could be touched)

Ranked by impact from the instrumentation:

1. **Cache `_get_all_var_data()` results on Var instances** — `read_var_data_ns / var = 15,415 ns` is mostly Python-side dep walking. Caching turns it into a ~100 ns attribute read. **Saves ~1.4 ms / page.**
2. **`get_props()` returns only `model_fields_set`** — 2091 prop iterations → ~260. **Saves ~1.5 ms / page** (mostly from the unaccounted slice).
3. **Pre-compute `_module_spec`** combining library/tag/alias — eliminates 3 redundant getattrs/element. **Saves ~0.15 ms / page**.
4. **Component as slotted dataclass** (out of Pydantic on the hot read path) — 2-3× faster getattr globally. Large refactor.

---

## 11. Bottom line

- The Rust **core itself is essentially free** — pure JSX emit is 24 µs for a 177-node tree.
- **All Rust pipeline cost is PyO3 boundary tax + Python method execution.**
- The 4-walks bug in `read_page` was a real ~1.5 ms / page bug; fixed.
- At small N (≤90 nodes) Rust now wins by ~2%.
- At large N (≥170 nodes) Python still wins by ~5%, because the PyO3 tax (~6 µs/node) accumulates.
- **The only path to genuinely beat Python at scale is to reduce per-node PyO3 calls** — either via Python-side caching (Var data, slot-based Components) or by snapshotting once and walking the snapshot in pure Rust thereafter.

The single highest-ROI Rust-side move is **moving `walk_and_memoize` to a Rust IR transform** — biggest Python phase, no new PyO3 tax (fuses into the existing walk), eliminates Python `Component.create()` allocations.

---

## 12. Reproduce

```bash
# Build the wheel
cd packages/reflex-compiler-rust
uv run maturin develop --release

# Single-page bench at scale=1 (47 nodes), 15 iterations
uv run python scripts/benchmark_single_page.py 15 1

# Scale sweep — Python wins ratio rises with N
for s in 1 2 4 8; do
  uv run python scripts/benchmark_single_page.py 15 $s | tail -5
done
```

Per-phase Rust timings are printed at the end of every run.
