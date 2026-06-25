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

## Stage B — registry-driven native elements (`stage_b.py`)

`register_component(name, tag, is_element)` registers a component with the Rust
core; `make(name, children, props)` is one generic factory that builds any
registered type natively. `fastnodes.el.div/span/...` are the `rx.el.*` set
registered this way. Verified byte-identical to `Component.create` +
`_RenderUtils` across multi-prop, `id`→`ref`, nesting, and native-parent +
cond/foreach-child trees, and purity-gated.

```
uv run python experimental/reflex-compiler-core/stage_b.py
equivalence:  multi-prop sort / id->ref / nested / cond child / foreach child  all OK
purity:       pure element tree -> BUILD-NATIVE (GIL-pure, 0 fallbacks)
              tree with cond    -> codegen-native, construction still Python (GIL-pure=False, 1 fallback)
benchmark:    ~12000 element nodes, construction  slow 122ms  fast 10ms  ~12x
```

**The "ordering gap" is solved, and simpler than expected.** Reflex's
`format_props` *sorts* props by their (camelCased) key, so the fast path just
camelCases, adds the `id`-derived `ref`, and sorts — no per-component
field-order table is needed. The registry therefore only needs `{tag, kind}`
(plus a style mapping for radix, next).

## Three levels of native-ness (and how the gate tells them apart)

1. **Build-native** — element built via `make`; renders GIL-released. Gold.
2. **Codegen-native only** — a Python construct (cond/foreach/custom component)
   is pre-rendered to its dict at build (`RawDict`); codegen runs natively over
   the dict (0 Python at render) but construction stayed in Python, so it fails
   the GIL-pure render and counts on the ledger.
3. **(removed)** — there is no longer a render-time `_RenderUtils` callback.

Output equality can't distinguish 1 from 2 (both emit identical JS), which is
exactly why the GIL-pure structural gate + build-time ledger exist.

## What this does NOT cover yet (next steps toward docs/app)

- **Radix components** (`rx.box/text/flex/...`, the #1 by frequency): same
  registry, but need the JS tag + `add_style` (theme prop → class) mapping
  generated from the Python class.
- **Native Cond/Iterable construction** (so cond/foreach become build-native,
  not just codegen-native) — requires reading the Var `_js_expr` at build.
- Var props (state-bound) carrying `(js_expr, VarData)`; event props; the
  plugin pass on Rust nodes.
- Collection/color/datetime literals in `literal_to_js`.
- Packaging (wheel matrix / abi3) and the import-guard fallback.
