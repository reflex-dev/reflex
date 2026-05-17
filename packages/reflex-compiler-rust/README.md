# reflex-compiler-rust (spike phase)

Workspace skeleton for the Rust rewrite of the Reflex compiler. See
`ignore/RUST_REWRITE_PLAN.md` (§3 — crate skeleton) for the long version.

**Status:** scaffold + napkin-math benchmarks only. No real compiler logic
yet. All non-`reflex_py` crates are stub `lib.rs` files. Do NOT depend on
this package; it is not published and the IR contract is in flux.

## Why this exists right now

The plan claims the round trip `Python → msgpack → Rust → emit → bytes`
beats the current Python compiler. Before writing any real port we need
numbers on the dominant costs:

1. PyO3 crossing cost (per call)
2. msgpack serialize on the Python side
3. msgpack deserialize on the Rust side (rmp-serde vs hand-rolled)
4. Tree walk + JSX-like emit (Python vs Rust)

The spike code lives in `crates/reflex_py/src/lib.rs`; the driver in
`scripts/spike_bench.py`.

## Build + run

```
cd packages/reflex-compiler-rust
uv venv .venv && . .venv/bin/activate
uv pip install maturin msgpack
maturin develop --release
uv run python scripts/spike_bench.py --sizes 10,100,1000,10000
```

`maturin develop --release` is non-negotiable — the debug profile is 5–20×
slower and would lie about the steady-state cost.

## Layout

```
Cargo.toml                  # workspace root, all 8 crates
pyproject.toml              # maturin, abi3-py310, points to crates/reflex_py
rust-toolchain.toml         # pinned stable
python/reflex_compiler_rust # thin python wrapper around the cdylib
crates/
  reflex_ir/      stub      # IR enum types — §3.2
  reflex_arena/   stub      # bumpalo + thread-local stash — §3.1
  reflex_intern/  stub      # Symbol interning — §3
  reflex_db/      stub      # Salsa boundary — §3.3
  reflex_semantic/ stub     # six aggregator walks — D7
  reflex_codegen/ stub      # IR → JS/JSX/CSS — D8
  reflex_py/      REAL      # PyO3 entry + spike probes
  reflex_bench/   stub      # criterion benches (TODO)
scripts/
  spike_bench.py            # the napkin-math driver
```

## What the spike measures vs the real plan

| Spike probe                        | Plan section / claim it tests |
|------------------------------------|-------------------------------|
| `empty_call`, `bytes_passthrough`  | §5 hot-reload budget — the per-call floor |
| `pack_streaming` (Python)          | §1 "no per-node dict" / §5 IR-emit <0.10ms/page |
| `walk_serde`                       | Pitfall 12: "rmp-serde allocates strings to heap" |
| `walk_manual`                      | §1 "custom Rust deserializer into bumpalo arena" |
| `walk_manual_emit` / `walk_arena_emit` | §5 "Rust compile work 2.81s → <0.5s" |
| `walk_emit_join` (Python)          | The Python baseline for codegen |
