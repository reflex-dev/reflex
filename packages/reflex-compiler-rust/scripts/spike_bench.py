"""Napkin-math microbenchmarks for the Rust-compiler spike.

Run with:

    uv run --with msgpack python packages/reflex-compiler-rust/scripts/spike_bench.py

Produces a comparison table for each tree size, hitting the four claims in
RUST_REWRITE_PLAN.md that we wanted to stress-test:

    1. PyO3 crossing cost (empty + bytes passthrough)
    2. msgpack pack cost on the Python side (with vs without per-node dicts)
    3. rmp-serde vs hand-rolled msgpack deserializer in Rust
    4. Python tree-walk + JSX-like emit vs the same in Rust (both via PyO3)

The tree shape is intentionally close to PageIR/ComponentIR (plan §4.1):
element nodes have a tag, a list of (prop_name, prop_expr) pairs, and
children; text nodes have a string. Wire format is positional msgpack arrays
(documented at the top of reflex_py/src/lib.rs).
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
import time
from io import BytesIO
from typing import Callable

import msgpack
from reflex_compiler_rust import _native

sys.setrecursionlimit(50_000)


# ---- synthetic tree ---------------------------------------------------------


TAG_POOL = ["Box", "Text", "Flex", "Button", "Stack", "Heading", "Link", "Image"]
PROP_NAMES = ["color", "size", "weight", "padding", "margin", "onClick", "href", "src"]
PROP_VALS = [
    '"red"',
    '"blue"',
    "1",
    "2",
    "state.value",
    '"sm"',
    "() => set(true)",
    '"/foo"',
]


def make_tree(n_nodes: int, seed: int = 0) -> dict:
    """Build a breadth-balanced tree with ~n_nodes total nodes.

    Depth stays at O(log n) because we expand the next un-expanded element on
    every step (BFS), giving each element 3-5 children until the budget is
    spent. Real Reflex pages look like this — bushy, not linear.
    """
    rng = random.Random(seed)

    def new_element() -> dict:
        n_props = rng.randint(2, 4)
        return {
            "kind": 0,
            "tag": rng.choice(TAG_POOL),
            "props": [
                (rng.choice(PROP_NAMES), rng.choice(PROP_VALS)) for _ in range(n_props)
            ],
            "children": [],
        }

    def new_text() -> dict:
        return {"kind": 1, "value": "lorem " + "ipsum " * rng.randint(1, 4)}

    root = new_element()
    frontier = [root]
    created = 1
    while frontier and created < n_nodes:
        parent = frontier.pop(0)
        n_children = rng.randint(3, 5)
        for _ in range(n_children):
            if created >= n_nodes:
                break
            if rng.random() < 0.25:
                parent["children"].append(new_text())
                created += 1
            else:
                child = new_element()
                parent["children"].append(child)
                frontier.append(child)
                created += 1
    return root


def count_nodes(node: dict) -> int:
    stack = [node]
    n = 0
    while stack:
        cur = stack.pop()
        n += 1
        if cur["kind"] == 0:
            stack.extend(cur["children"])
    return n


# ---- packers ----------------------------------------------------------------
#
# Two packing strategies:
#
#   pack_via_dict:  build a tree-of-dicts (what naive code would do) then
#                   msgpack.packb the whole thing. Pays the dict construction
#                   cost + msgpack walks the dict.
#
#   pack_streaming: call Packer methods directly while walking the tree, so
#                   we never materialize a per-node dict. This is the §1 claim:
#                   "no per-node dict". For napkin math we walk the same
#                   tree-of-dicts to be fair, but real Python emit code would
#                   walk Component objects via Component.to_ir(packer).


def pack_via_dict(tree: dict) -> bytes:
    """Convert tree-of-dicts to positional arrays, then packb."""

    def to_arr(n):
        if n["kind"] == 1:
            return [1, n["value"]]
        return [
            0,
            n["tag"],
            [[k, v] for (k, v) in n["props"]],
            [to_arr(c) for c in n["children"]],
        ]

    return msgpack.packb(to_arr(tree), use_bin_type=True)


def pack_streaming(tree: dict) -> bytes:
    """Stream directly into a Packer; no intermediate per-node objects."""
    buf = BytesIO()
    packer = msgpack.Packer(use_bin_type=True)

    def emit(n):
        if n["kind"] == 1:
            buf.write(packer.pack_array_header(2))
            buf.write(packer.pack(1))
            buf.write(packer.pack(n["value"]))
            return
        props = n["props"]
        children = n["children"]
        buf.write(packer.pack_array_header(4))
        buf.write(packer.pack(0))
        buf.write(packer.pack(n["tag"]))
        buf.write(packer.pack_array_header(len(props)))
        for k, v in props:
            buf.write(packer.pack_array_header(2))
            buf.write(packer.pack(k))
            buf.write(packer.pack(v))
        buf.write(packer.pack_array_header(len(children)))
        for c in children:
            emit(c)

    emit(tree)
    return buf.getvalue()


# ---- pure-Python walk + emit (the baseline) ---------------------------------
#
# Two flavors:
#
#   walk_emit_concat:  the dumb O(n^2) version with string concatenation.
#   walk_emit_join:    list-of-fragments + "".join at the end. This is what
#                      well-written Python codegen would do.
#
# Both walk the same tree-of-dicts. The shape mirrors what Rust emits.


def walk_emit_concat(tree: dict) -> bytes:
    def go(n):
        if n["kind"] == 1:
            return f'"{n["value"]}"'
        s = "jsx(" + n["tag"] + ",{"
        for i, (k, v) in enumerate(n["props"]):
            if i:
                s += ","
            s += k + ":" + v
        s += "}"
        for c in n["children"]:
            s += "," + go(c)
        s += ")"
        return s

    return go(tree).encode()


def walk_emit_join(tree: dict) -> bytes:
    parts: list[str] = []
    app = parts.append

    def go(n):
        if n["kind"] == 1:
            app('"')
            app(n["value"])
            app('"')
            return
        app("jsx(")
        app(n["tag"])
        app(",{")
        for i, (k, v) in enumerate(n["props"]):
            if i:
                app(",")
            app(k)
            app(":")
            app(v)
        app("}")
        for c in n["children"]:
            app(",")
            go(c)
        app(")")

    go(tree)
    return "".join(parts).encode()


# ---- timer ------------------------------------------------------------------


def bench(label: str, fn: Callable[[], object], iters: int) -> tuple[str, float, float]:
    """Run fn() iters times, return (label, median_ns_per_op, min_ns_per_op)."""
    # warmup
    for _ in range(min(3, iters)):
        fn()
    samples = []
    for _ in range(iters):
        t0 = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - t0)
    return label, float(statistics.median(samples)), float(min(samples))


def fmt_time(ns: float) -> str:
    if ns < 1_000:
        return f"{ns:7.0f}ns"
    if ns < 1_000_000:
        return f"{ns / 1_000:7.2f}µs"
    if ns < 1_000_000_000:
        return f"{ns / 1_000_000:7.2f}ms"
    return f"{ns / 1_000_000_000:7.3f}s "


# ---- main -------------------------------------------------------------------


def run_size(n_nodes: int, iters: int) -> None:
    print(f"\n=== tree size: target n={n_nodes} nodes, iters={iters} ===")
    tree = make_tree(n_nodes)
    actual_n = count_nodes(tree)
    blob = pack_streaming(tree)
    print(f"actual node count = {actual_n}, msgpack size = {len(blob)} bytes "
          f"({len(blob) / actual_n:.1f} B/node)")

    rows = []

    # 1. PyO3 crossing
    rows.append(bench("pyo3 empty_call", _native.empty_call, iters))
    rows.append(bench("pyo3 add_one(1)", lambda: _native.add_one(1), iters))
    rows.append(
        bench(
            f"pyo3 bytes_passthrough ({len(blob)}B)",
            lambda: _native.bytes_passthrough(blob),
            iters,
        )
    )

    # 2. Python pack
    rows.append(bench("py msgpack pack (via dict)", lambda: pack_via_dict(tree), iters))
    rows.append(bench("py msgpack pack (streaming)", lambda: pack_streaming(tree), iters))

    # 3. Rust deserialize-only
    rows.append(bench("rs walk_serde   (rmp-serde, no emit)", lambda: _native.walk_serde(blob), iters))
    rows.append(bench("rs walk_manual  (hand-rolled, no emit)", lambda: _native.walk_manual(blob), iters))

    # 4. Walk + emit (the actual codegen analog)
    rows.append(bench("py walk_emit_concat", lambda: walk_emit_concat(tree), iters))
    rows.append(bench("py walk_emit_join", lambda: walk_emit_join(tree), iters))
    rows.append(bench("rs walk_serde_emit  (rmp-serde + emit)", lambda: _native.walk_serde_emit(blob), iters))
    rows.append(bench("rs walk_manual_emit (hand-rolled + emit)", lambda: _native.walk_manual_emit(blob), iters))
    rows.append(bench("rs walk_arena_emit  (bumpalo + emit)", lambda: _native.walk_arena_emit(blob), iters))

    # 5. End-to-end Python→Rust round-trip vs pure-Python join
    def e2e():
        b = pack_streaming(tree)
        return _native.walk_manual_emit(b)

    rows.append(bench("e2e pack_streaming + rs walk_manual_emit", e2e, max(iters // 2, 1)))

    print(f"{'label':<46} {'median':>10}  {'min':>10}  {'µs/node':>9}")
    print("-" * 80)
    for label, med, mn in rows:
        per_node = (med / actual_n) / 1_000  # µs per node
        print(f"{label:<46} {fmt_time(med):>10}  {fmt_time(mn):>10}  {per_node:>8.3f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sizes",
        type=str,
        default="10,100,1000,10000",
        help="comma-separated tree-size targets",
    )
    parser.add_argument("--iters", type=int, default=50)
    args = parser.parse_args()

    sizes = [int(s) for s in args.sizes.split(",")]
    iter_for = lambda n: max(1, min(args.iters, 2000 // max(1, n // 100)))

    print(f"python: {sys.version.split()[0]}")
    print(f"msgpack: {msgpack.__version__}")
    for n in sizes:
        run_size(n, iter_for(n))


if __name__ == "__main__":
    main()
