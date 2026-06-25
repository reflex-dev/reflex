# reflex-compiler-core (proving slice)

Tests one question: **is building component nodes natively in Rust — skipping
Python `Component` instantiation entirely — actually faster, while producing
identical output?**

Prior experiments showed that "build the Python `Component` tree, freeze it,
hand it to Rust" buys almost nothing, because the dominant compile cost is the
per-component instantiation itself (`Component._post_init` → per-prop
`LiteralVar.create` + `satisfies_type_hint`, per-event `EventChain.create`, on
top of the pydantic model machinery). That cost is paid *before* any freeze.

This slice moves the PyO3 seam to the factory call. `fast_div(...)` carries only
a tag string and hands raw children + props to Rust; `make_node` builds a native
node directly. Literal props are rendered straight to JS in Rust — `LiteralVar`
is never created. The Python `Component` object is never instantiated.

## What it implements

- `make_node(tag, is_element, children, props)` → a `NodeHandle` (owned Rust
  subtree; consumed when it becomes a child, so the tree is moved, not copied).
- `literal_to_js` — renders `str`/`int`/`float`/`bool`/`None` to JS matching
  `str(LiteralVar.create(x))`.
- `to_camel_case` / `format_ref` / `id`→`ref` — ports of the Reflex formatters.
- `render_to_js` — lowers a node to its `jsx(...)` string, mirroring
  `_RenderUtils.render`.
- **Fallback bridge:** a child that is a real Python `Component` (custom or
  not-yet-ported) is stored as an opaque leaf and rendered by calling back into
  `_RenderUtils` — the pydantic-core `FunctionWrapValidator` pattern. A fast
  Rust node and a slow Python node compose in the same tree, both directions.

## Build + run

```bash
uv pip install maturin
# build the extension into the reflex venv (abi3, forward-compat for py3.14):
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 \
  uv run maturin develop --release -m experimental/reflex-compiler-core/Cargo.toml
uv run python experimental/reflex-compiler-core/bench.py
```

## Result (2000-row tree, ~20k nodes, best of 5; numbers are machine-dependent)

```
                              slow (py)   fast (rust)   speedup
construction                   166.08 ms     12.50 ms     13.3x
construction + render          473.44 ms     14.80 ms     32.0x
```

- **Output is byte-identical** to `_RenderUtils.render(component.render())` on
  the benchmark tree (asserted in `bench.py`), so the speedup is real, not the
  product of emitting different JS.
- The 13.3x on *construction* is the headline: it is exactly the
  `_post_init`/`LiteralVar.create` cost the experiment identified, and it
  includes the PyO3 marshalling crossing on every node (an honest measurement).
- The fallback bridge to real Python components is byte-identical too.

## Purity validation — proving the work is native, not a Python wrapper

The central risk of this whole effort: an implementation can make the
equivalence tests pass by quietly delegating to Python (`render_py_leaf`) and
string-matching the output. It *looks* ported; nothing moved. `validate.py`
enforces three layers — the first two do **not** trust the Rust code's
self-report:

1. **Structural (strongest):** `render_to_js_pure` runs with the GIL released
   (`Python::allow_threads`). That region is handed no `Python` token and
   rejects GIL-bound captures, so it *cannot* call Python. If it returns a
   string, zero Python executed. If the tree needs Python, it errors instead of
   silently falling back.
2. **External profiler:** `sys.setprofile` counts real Python function entries
   during a render. Native render → 0; every fallback → many (515 in the demo).
3. **Self-reported ledger:** `set_strict(True)` turns any fallback into a hard
   error; `py_fallback_count()` gives graded coverage for CI.

```
uv run python experimental/reflex-compiler-core/validate.py
tree                    structural  py_calls  fallbacks     verdict
pure (all native)           native         0          0    NATIVE ✓
cheat (python leaf)        BLOCKED       515          1  FALLBACK ✗
```

**The CI gate:** build a tree of *only* the components claimed native and assert
`render_to_js_pure` succeeds **and** `py_calls == 0` **and** `fallbacks == 0`.
If a future change sneaks a Python fallback into a "ported" path, the gate fails
automatically — you cannot pass it by matching strings.

## Known gap (deliberately not solved here)

Multi-prop **ordering**: the Python path emits props in component
field-definition order (e.g. `className,id`); this slice preserves user-kwarg
order (`id,className`). Values, refs, and camelCasing all match. Closing this
needs the per-component field-order table — i.e. the code-generated component
registry the design calls for (source of truth: the existing Python class
definitions + `.pyi`). Single-prop nodes and the benchmark match exactly.

## What this slice does NOT cover (next steps)

- The component registry (prop kind/order metadata) generated from Python classes.
- Var props (state-bound) carrying `(js_expr, VarData)` across the seam.
- Event props beyond capture; the plugin pass operating on Rust nodes.
- Collection/color/datetime literals in `literal_to_js`.
- Packaging (wheel matrix / abi3 distribution) and the import-guard fallback.
