"""Micro-benchmark for ENG-10095: dirty-propagation runs in full on every mutation.

Measures per-mutation cost with computed vars defined:
  1. Proxied list append (each triggers _mark_dirty -> _mark_dirty_computed_vars).
  2. Plain int setattr in a loop.
  3. Raw list append baseline (no state involved).
"""

import cProfile
import io
import pstats
import time


def build_state():
    import reflex as rx

    class BenchFix3State(rx.State):
        items: list[int] = []
        other: int = 0

        @rx.var(cache=True)
        def total(self) -> int:
            return len(self.items)

        @rx.var(cache=True)
        def other_doubled(self) -> int:
            return self.other * 2

    return BenchFix3State(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]


def bench_append(state, n: int = 10000) -> float:
    proxy = state.items
    start = time.perf_counter()
    for i in range(n):
        proxy.append(i)
    return (time.perf_counter() - start) / n * 1_000_000


def bench_setattr(state, n: int = 10000) -> float:
    start = time.perf_counter()
    for i in range(n):
        state.other = i
    return (time.perf_counter() - start) / n * 1_000_000


def bench_raw_append(n: int = 100000) -> float:
    raw = []
    start = time.perf_counter()
    for i in range(n):
        raw.append(i)
    return (time.perf_counter() - start) / n * 1_000_000


def main():
    state = build_state()

    append_us = bench_append(state)
    setattr_us = bench_setattr(state)
    raw_us = bench_raw_append()
    print(f"proxied list append:  {append_us:8.3f} us/op")
    print(f"int var setattr:      {setattr_us:8.3f} us/op")
    print(f"raw list append:      {raw_us:8.4f} us/op")

    # Correctness spot-check: computed vars still update after the loop.
    state._clean()
    state.items = [1, 2, 3]
    assert state.total == 3
    state.other = 21
    assert state.other_doubled == 42
    print("correctness spot-check passed")

    profiler = cProfile.Profile()
    profiler.enable()
    bench_append(state, n=2000)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(12)
    print("cProfile (2000 proxied appends):")
    print(stream.getvalue())


if __name__ == "__main__":
    main()
