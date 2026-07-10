"""Micro-benchmark for ENG-10094: MutableProxy per-element overhead.

Measures:
  1. Iterating a 1000-int list through the state proxy (per-element wrapping).
  2. Repeated attribute reads of a mutable var (proxy construction/caching).
  3. Per-element reads via indexing.
"""

import cProfile
import io
import pstats
import time


def build_state():
    import reflex as rx

    class BenchFix2State(rx.State):
        numbers: list[int] = []

    state = BenchFix2State(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    state.numbers = list(range(1000))
    return state


def bench_iterate(state, n: int = 200) -> float:
    start = time.perf_counter()
    for _ in range(n):
        for _item in state.numbers:
            pass
    return (time.perf_counter() - start) / n * 1000


def bench_attr_read(state, n: int = 20000) -> float:
    start = time.perf_counter()
    for _ in range(n):
        _ = state.numbers
    return (time.perf_counter() - start) / n * 1_000_000


def bench_index_read(state, n: int = 100) -> float:
    start = time.perf_counter()
    for _ in range(n):
        nums = state.numbers
        for i in range(1000):
            _ = nums[i]
    return (time.perf_counter() - start) / n * 1000


def main():
    state = build_state()

    iter_ms = bench_iterate(state)
    attr_us = bench_attr_read(state)
    index_ms = bench_index_read(state)
    print(f"iterate 1000-int list via proxy: {iter_ms:8.4f} ms/op")
    print(f"read mutable var attribute:      {attr_us:8.3f} us/op")
    print(f"index 1000 elements via proxy:   {index_ms:8.4f} ms/op")

    profiler = cProfile.Profile()
    profiler.enable()
    bench_iterate(state, n=20)
    bench_attr_read(state, n=2000)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(12)
    print("cProfile (20 iterations + 2000 attr reads):")
    print(stream.getvalue())


if __name__ == "__main__":
    main()
