"""Proving-slice benchmark: native Rust node construction vs Component.create.

Measures the thing the experiment identified as the real bottleneck:
per-component instantiation. Builds an identical tree two ways and reports:
  1. construction time (the _post_init cost we are trying to delete), and
  2. construction + render-to-JS time (end to end, incl. PyO3 marshalling).
It also asserts the two paths emit byte-identical JS, so the speedup is not
bought by producing different output.

Run:  uv run python experimental/reflex-compiler-core/bench.py
"""

import gc
import time

import reflex as rx
from reflex_base.compiler.templates import _RenderUtils

import fastnodes as fast


def build_slow(n_rows):
    """Build the tree with the real Reflex component path."""
    rows = [
        rx.el.div(
            rx.el.h1(f"Title {i}", class_name="hd"),
            rx.el.span(f"item {i}", class_name="sp"),
            rx.el.div(
                rx.el.span("x", class_name="a"),
                rx.el.span("y", class_name="b"),
                class_name="inner",
            ),
            class_name="row",
        )
        for i in range(n_rows)
    ]
    return rx.el.div(*rows, class_name="root")


def build_fast(n_rows):
    """Build the same tree natively in Rust via the factory shims."""
    rows = [
        fast.fast_div(
            fast.fast_h1(f"Title {i}", class_name="hd"),
            fast.fast_span(f"item {i}", class_name="sp"),
            fast.fast_div(
                fast.fast_span("x", class_name="a"),
                fast.fast_span("y", class_name="b"),
                class_name="inner",
            ),
            class_name="row",
        )
        for i in range(n_rows)
    ]
    return fast.fast_div(*rows, class_name="root")


def render_slow(tree):
    return _RenderUtils.render(tree.render())


def render_fast(tree):
    return fast.render_to_js(tree)


def _time(fn, iters):
    gc.collect()
    gc.disable()
    best = float("inf")
    for _ in range(iters):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    gc.enable()
    return best


def main():
    # Correctness first: byte-identical JS on a small identical tree.
    small_slow = render_slow(build_slow(3))
    small_fast = render_fast(build_fast(3))
    assert small_slow == small_fast, (
        "OUTPUT MISMATCH\n--- slow ---\n"
        + small_slow
        + "\n--- fast ---\n"
        + small_fast
    )
    print("equivalence: fast JS == slow JS  (byte-identical) ✓")
    print("sample JS:", small_fast[:120], "...\n")

    n_rows = 2000
    # ~6 element nodes + 4 text nodes per row.
    approx_nodes = n_rows * 10
    iters = 5

    t_slow_build = _time(lambda: build_slow(n_rows), iters)
    t_fast_build = _time(lambda: build_fast(n_rows), iters)

    tree_slow = build_slow(n_rows)
    tree_fast = build_fast(n_rows)
    t_slow_full = _time(lambda: render_slow(build_slow(n_rows)), iters)
    t_fast_full = _time(lambda: render_fast(build_fast(n_rows)), iters)

    # Confirm equivalence at scale too.
    assert render_slow(tree_slow) == render_fast(tree_fast), "mismatch at scale"

    def row(label, slow, fast):
        return f"{label:<28} {slow * 1e3:9.2f} ms {fast * 1e3:9.2f} ms   {slow / fast:6.1f}x"

    print(f"tree: {n_rows} rows (~{approx_nodes} nodes), best of {iters}\n")
    print(f"{'':<28} {'slow (py)':>12} {'fast (rust)':>12}   speedup")
    print("-" * 70)
    print(row("construction", t_slow_build, t_fast_build))
    print(row("construction + render", t_slow_full, t_fast_full))


if __name__ == "__main__":
    main()
