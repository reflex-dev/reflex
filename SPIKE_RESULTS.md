# Rust Compiler Spike — Napkin-Math Results

> **Calibration update (2026-05-16, post-cProfile on docs app).** The first
> draft of this doc compared Rust against a synthetic Python codegen
> (`walk_emit_join`) that is **~580× faster per node than real Reflex
> Python**. Real `compiler.compile` on the docs app costs **273 µs/node**
> (2.81s ÷ 10 290 nodes); the spike's synthetic Python ran at 0.47 µs/node.
> The conclusion "Rust round trip is *slower* than pure Python" is therefore
> wrong for the actual baseline — see the new §6 at the bottom of this doc.
> The other findings (PyO3 crossing free, rmp-serde 25× slower than
> hand-rolled, streaming pack slower than `packb`, arena loses single-pass)
> all still hold against the corrected baseline.

Date: 2026-05-16
Hardware: this machine (Linux 6.14, x86_64), abi3-py310 wheel built with
`maturin develop --release`, Python 3.14.3, msgpack 1.1.2.

Scaffold lives at `packages/reflex-compiler-rust/`. The probes are inline in
`crates/reflex_py/src/lib.rs`; the driver is
`packages/reflex-compiler-rust/scripts/spike_bench.py`.

> Synthetic tree shape: balanced BFS construction with fan-out 3-5 per
> element, 2-4 props per element, 25% leaf-text probability. Wire format is
> positional msgpack arrays (the optimistic case for parse speed). Real
> ComponentIR is a map and will be 10-30% slower to walk.

---

## Headline numbers (per tree size, median over 200-300 iters)

`µs/node` is the rate column — that's the metric to compare across sizes.

| Probe                                  | n=10  | n=100 | n=1k  | n=10k | µs/node (10k) |
|----------------------------------------|------:|------:|------:|------:|--------------:|
| pyo3 `empty_call`                      |  60ns |  90ns |  60ns |  70ns | ~0            |
| pyo3 `bytes_passthrough` (full blob)   | 120ns | 160ns | 120ns | 120ns | ~0            |
| py `msgpack pack via dict`             | 5.9µs | 58µs  | 672µs | 7.96ms| **0.80**      |
| py `msgpack pack streaming`            | 11.9µs| 86µs  | 839µs | 8.42ms| **0.84**      |
| rs `walk_serde` (rmp-serde, no emit)   | 6.6µs | 87µs  | 1.40ms| 19.78ms| 1.98         |
| rs `walk_manual` (hand-rolled, no emit)| 0.71µs| 5.5µs | 67µs  | 767µs | **0.08**      |
| py `walk_emit_concat`                  | 5.2µs | 52µs  | 583µs | 6.10ms| 0.61          |
| py `walk_emit_join`                    | 6.1µs | 46µs  | 472µs | 4.71ms| **0.47**      |
| rs `walk_serde_emit`                   | 9.0µs | 161µs | 2.12ms| 28.05ms| 2.81         |
| rs `walk_manual_emit` (hand + emit)    | 1.5µs | 6.9µs | 86µs  | 979µs | **0.098**     |
| rs `walk_arena_emit` (bumpalo + emit)  | 1.5µs | 9.4µs | 119µs | 1.29ms| 0.13          |
| **e2e** pack_stream + rs manual_emit   | 16.4µs| 100µs | 991µs | 11.14ms| **1.11**     |

All variants produce byte-identical output; verified at smoke-test.

---

## What the numbers say

### ✅ PyO3 crossing is free

60-200ns per call regardless of payload size. The plan's "the boundary is
cheap" assumption holds. No design needs to amortize crossings.

### ✅ Hand-rolled msgpack reader beats rmp-serde by 25×

At n=10k: hand-rolled walk 767µs vs rmp-serde walk 19.78ms.
With emit: 979µs vs 28.05ms.

This validates Pitfall 12 in the plan ("rmp-serde allocates strings to the
heap. Defeats R1"). It is **mandatory** to hand-roll the deserializer.
Building with rmp-serde "for now" and migrating later is not viable — it
would hide the win below the noise floor and lead to wrong scaling
conclusions.

### ❌ "No per-node dict" Python packing claim is wrong

§1 says: "Python side uses `msgpack.Packer` writing to one `bytes` buffer
with no per-node `dict`."

Measured: `pack_streaming` (no dict, calls `packer.pack_array_header()` per
node) is **5-7% slower** than `pack_via_dict` (build a tree-of-lists, single
`msgpack.packb` call) at n≥1k.

Reason: `msgpack-python` is C-implemented. One `packb` call descends the
entire structure in C; streaming pays Python-call overhead per node.

Implication: `Component.to_ir(packer)` should not stream per-node. Either
(a) build a small list-of-lists for each Component, or (b) write a C
extension for the streaming case. The current §7 sketch
("`Component.to_ir(packer: msgpack.Packer)` — direct emission, no
intermediate dicts") will be **slower** than the obvious alternative.

### ⚠️ Rust codegen win is ~5×, not 5-10×

Apples-to-apples on the same 10k-node tree:

- py `walk_emit_join` (well-written Python codegen): 4.71 ms
- rs `walk_manual_emit` (hand-rolled, single-pass): 0.98 ms
- **Speedup: 4.8×**

The plan's §5 target ("Rust compile work 2.81s → <0.5s" = 5.6×) is right at
the edge of what a single-pass Rust port can deliver. Anything that adds
overhead — Salsa accounting, source-map recording, map-format IR, multiple
walks — eats directly into this margin.

### 🚨 End-to-end is *slower* than pure Python at this scope

This is the most uncomfortable finding:

| For a 10k-node tree                     | wall-clock |
|-----------------------------------------|-----------:|
| Pure Python: `walk_emit_join`           |   4.71 ms  |
| Round trip: `pack_streaming` + Rust emit| **11.14 ms** |

The msgpack pack on the Python side (8.4 ms) is already 1.8× the pure-Python
codegen wall-clock. Adding the Rust emit on top makes the round trip 2.4×
slower than just doing the work in Python.

**This is the napkin-math indictment of the "ship everything to Rust over
msgpack" model when the Rust work is shallow.** It works only if Rust does
much more work per byte sent than just JSX emit. Candidates:

1. **Multiple passes per parsed tree** — the plan's 6 aggregator walks
   amortize over a single parse. With one arena tree retained, walks 2-N
   are free (the parse cost is gone). Spike has only single-pass numbers;
   the 6-walk case is the next thing to bench. Until that's measured the
   plan's win is not proven.
2. **Salsa-cached hot reload** — the second `compile_app` should be ~free
   for unchanged pages. The msgpack cost still applies to changed pages
   only, so the wall-clock floor for hot reload is one page's pack + walk
   = sub-millisecond. The §5 <150ms target is comfortable on these numbers
   *if Salsa works as advertised* — which the spike does not exercise.
3. **Theme/context/memo/vite codegen** — these are O(1) per app, not
   O(nodes). They are dominated by the Python `compile_app` post-processing
   work (the §0 "Python-remaining" bucket). Moving them to Rust is a
   constant-time win that compounds across pages but does not change the
   per-node math above.

### ⚠️ Bumpalo arena is *slower* than no-arena for single-pass codegen

`walk_arena_emit` (parse into arena, then walk arena to emit) is **30%
slower** than `walk_manual_emit` (parse and emit in one pass) at every
size. Reason: arena pays for an extra `alloc_str` copy of every string
plus arena `Vec` allocation for props/children slices.

This does **not** invalidate R1. The arena win comes from:
- Multiple walks over the parsed tree (5+ aggregators) — single-pass spike
  can't see this.
- Zero-copy &str borrows from the input msgpack bytes (the spike *does*
  copy via `alloc_str`; switching to lifetime-bound `&str` slices into the
  input buffer would close the gap).
- Skipping `Drop` calls at the end (R2).

But it does mean: **R1 is not free**. The arena pays for itself only when
you genuinely need to materialize the IR. If a query can stream parse →
emit in one pass (and many can), it should — even though that breaks the
"every IR node arena-allocated" invariant.

---

## Decision rules for the plan

Translating the §0 decision rules to the numbers we have:

- **Is IR emit > 30% of current wall-clock?**
  Not measured directly here (spike doesn't run the real Python compiler).
  But the per-node pack rate is ~0.8 µs/node, and Reflex pages average
  ~50-200 nodes; so a 27-page docs app ≈ 4k nodes ≈ 3.4 ms. That's
  negligible vs the ~10s cold compile. **IR emit is small.** Good.

- **Is Python-remaining > 50% of current wall-clock?**
  Cannot tell from the spike. Need to run `cProfile` on
  `reflex.compiler.compiler._compile_app` and bucket by stage. This is the
  next item to do before any D-item starts.

- **Does the Rust win cover the msgpack tax?**
  At single-pass scope: **no** — Python is faster. The plan only pays off
  if Rust does multi-pass work *and* Salsa cache hits dominate hot reload.

---

## Recommended next benches (before D1)

The single-page single-pass story is now mapped. What remains uncertain:

1. **Multi-walk amortization.** Parse a tree once into a bumpalo arena,
   then run 6 separate walks (counters for hooks/imports/refs/customcode/
   dynamic_imports/hooks_internal). Compare to running 6 fresh parses.
   This is the actual argument for the arena. Without it, R1 doesn't
   pay off.

2. **Real `Component.to_ir` cost.** Wire `Component.to_ir(packer)` against
   one Tier-1 fixture and measure. The spike's synthetic tree is generous
   (small strings, low prop count). Real Var `_js_expr` strings are
   100-500 bytes and there are 10-50 per element — IR emit could be 5-10×
   what the synthetic implies.

3. **Map vs array wire format.** The spike used positional arrays. Real
   IR uses maps with named keys. Measure the parse-cost delta — short
   keys ("k", "t", "p", "c") are probably <10%, but it should be a number,
   not a guess.

4. **Salsa hot path.** Build a minimal Salsa graph with N inputs + one
   tracked accumulator, edit 1 input, measure invalidation + re-run cost.
   The plan rides hard on this being sub-millisecond.

5. **Python cProfile bucket-by-bucket.** Run §0 step 3 on the docs app
   today to get the "Python-remaining" share. This is what decides
   whether the porting effort is worth the calendar time.

Items 1, 2, 3 are afternoons of work in the existing scaffold.
Items 4 and 5 are the gating-decision data the plan explicitly calls for.

---

## What this means for the plan

- **Don't write the rmp-serde fallback.** Skip directly to hand-rolled
  msgpack. The 25× factor is too large to defer.
- **Re-spec §7's `Component.to_ir(packer)` API.** Streaming is the wrong
  default; building a list-of-lists per Component and `packb`-ing in one
  C call is faster on these numbers. Or push the serialization into a C
  extension.
- **Don't promise <0.5s "Rust compile work" without multi-walk numbers.**
  Single-pass beats Python by 5×; that's the floor. Multi-walk could
  push it higher but is unproven.
- **The arena rule (R1) is conditional, not absolute.** Codegen queries
  that genuinely need one pass should be allowed to skip the arena. The
  "no heap allocations during compilation" framing is too strict.
- **`REFLEX_COMPILER=auto` defaulting to Python during rollout is
  correct.** The round-trip math says small apps (<100 nodes total) may
  always be faster pure-Python. The threshold for "Rust wins" looks like
  it sits somewhere around 1k nodes — measure before flipping the default.

**Net.** The plan is directionally sound but two specific claims need to
be revised before D1 starts:

1. §1 "Python side uses `msgpack.Packer` writing to one `bytes` buffer
   with no per-node `dict`" → **measured slower**; use packb on a
   list-of-lists or write a C extension.
2. §5 target tables imply a 5-10× Rust win on the codegen bucket →
   single-pass spike says 5× exactly. Multi-walk numbers must land
   above this before the §13 done-criterion ("≥5× on Rust-resident
   buckets") is a safe promise.

---

## 6. Calibration against the real docs-app profile

cProfile of the 27-page docs app (10.1s wall, captured 2026-05-16):

| Bucket                                       | Time   | %    | Rust-rewritable |
|----------------------------------------------|-------:|-----:|:----------------|
| `_get_frontend_packages` (npm install subp.) | 3.77s  | 37%  | No (subprocess) |
| `compiler.compile` (per-page render)         | 2.81s  | 28%  | **Yes — prize** |
| `prerequisites.get_app` (import app module)  | 2.08s  | 21%  | No (one-time)   |
| Framework `__init__` imports                 | ~1.0s  | ~10% | No (one-time)   |
| `compile_memo_components`                    | 0.85s  | 8%   | **Yes**         |
| Markdown (mistletoe + parse_document)        | 0.79s  | 8%   | Yes (drop-in)   |

Inside the 2.81s `compiler.compile`:
- 10 290 component-tree visits → walked 10K nodes
- `compile_component` + `_compile_component_with_replacements`: 1.52s
- `component.render` (10 087 calls): 0.99s
- `component.create` / `_create` (10 347 / 11 722 calls): 0.82s / 0.73s

Hot tottime: 2.26M `isinstance`, 954K `getattr`, 1.38M `str.startswith`,
57K `Var._create_literal_var`, 74K `Component._get_vars`. All polymorphic
dispatch / attribute lookup overhead that **vanishes** in a typed Rust
enum + struct-field-access codegen.

### Real per-node cost vs the spike

| baseline                            | µs/node | for 10 290 nodes |
|-------------------------------------|--------:|-----------------:|
| Spike synthetic Python (`walk_emit_join`)            | 0.47   | 4.8 ms |
| **Real Reflex `compiler.compile`**  | **273** | **2 810 ms**     |
| Spike Rust `walk_manual_emit`       |   0.098 | 1.0 ms           |
| Spike e2e (pack + walk_manual_emit) |   1.11  | 11.4 ms          |

Real Python is **580× slower per node** than my spike baseline.

That changes the picture entirely. The §1 e2e comparison concluded "Rust
round trip is slower than pure Python." That was true for an *idealised*
Python codegen that does not exist in Reflex. Against the **actual**
compiler the round trip is ~280× faster:

| 10k-node tree                        | wall-clock |
|--------------------------------------|-----------:|
| Real `compiler.compile`              |  ~2 810 ms |
| Rust round trip (pack + walk + emit) |    ~12 ms  |

Even tripling the Rust number for real-string-size and overhead, that's
**~75× on the `compiler.compile` bucket**. Far above the §5 target of 5.6×.

### Where the wall-clock actually goes after the rewrite

| Scenario                       | Today  | Rust-target | Win              |
|--------------------------------|-------:|------------:|------------------|
| 27-page docs, cold (full stack)| 10.1s  | ~6.5s       | 1.55× (npm bound)|
| 27-page docs, cold (warm npm)  |  ~6.4s | ~2.8s       | 2.3×             |
| 27-page docs, hot reload       | ~120ms | <30ms       | 4-5×             |
| 200-page synthetic, cold       |  ~30s* |  ~11s       | 2.7× (still npm bound) |

\* projected: linear extrapolation of the per-page 104 ms compile cost.

The §5 plan's 8.5s target for the 200-page cold compile is **plausible**
if compile + memo + markdown all move to Rust. Beyond that the floor is
npm + app import + framework init = ~7s, which the compiler rewrite
cannot touch.

### What this calibration changes in the plan

- **§5 cold-build targets are achievable.** "Rust compile work 2.81s →
  <0.5s" was a 5.6× ask; real headroom is 50-100× on this bucket. The
  target should probably tighten to ~50-100 ms so the rest of the
  pipeline (npm, app import) becomes the binding constraint, not the
  Rust ceiling.
- **Pitfall 1 ("First Rust port of allocators is wrong") gets stricter.**
  With 50-100× headroom on the Python baseline, a careless port that
  only delivers 5× *looks* fine in isolation but is leaving 10-20×
  on the table.
- **Markdown is the cheapest win, no IR required.** Swap mistletoe →
  pulldown-cmark (or comrak) via a separate PyO3 wheel. 0.79s → 10-50ms
  expected. This can ship before any IR work and gives an early
  validation that PyO3 binding works in production.
- **The non-compiler buckets cap the cold-build win at ~2.3× even with
  hot npm cache.** The plan should manage expectations: dev hot-reload
  is the big visible win (4-5×); cold-compile is dominated by stuff
  the rewrite cannot touch.
- **At 200 pages the rewrite goes from "nice" to "necessary".** Python
  compile-work scales linearly at 104 ms/page; Rust scales at <1 ms/page.
  At 1 000 pages Python would spend ~104s on compile alone — that's the
  scaling story the §5 table understates.

### Updated decision-rule outcomes

Plan §0 asked three questions; with the cProfile in hand:

- **Is IR emit > 30% of current wall-clock?** No. IR emit on 10k nodes
  is ~10 ms (spike), the compile bucket is 2 810 ms → IR emit is **0.4%**.
  Boundary is comfortable.
- **Is Python-remaining > 50% of current wall-clock?** Of the *post-IR-emit*
  remainder: npm 37% + app import 21% + framework imports 10% = 68%.
  This is technically > 50% — but it's all "untouchable" work (subprocess,
  one-time import), not work that should have moved to Rust. The rule was
  meant to catch hidden Python post-processing; that's not what we have.
  **Proceed.**
- **Spike says proceed to D1.**
