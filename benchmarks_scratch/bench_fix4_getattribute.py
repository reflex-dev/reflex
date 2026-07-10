"""Micro-benchmark for ENG-10096: __getattribute__ slow path and get_delta caches.

Measures:
  1. Framework bookkeeping attribute reads (dirty_vars, parent_state, substates,
     _backend_vars) through the state instance.
  2. An event-processing-shaped loop: mutate, get_delta, clean.
  3. get_skip_vars() throughput.
"""

import cProfile
import io
import pstats
import time


def build_state():
    import reflex as rx

    class BenchFix4State(rx.State):
        items: list[int] = []
        count: int = 0

        @rx.var(cache=True)
        def doubled(self) -> int:
            return self.count * 2

        @rx.var(cache=True, backend=True)
        def _hidden(self) -> int:
            return self.count + 1

    class BenchFix4Child(BenchFix4State):
        child_val: int = 0

    return BenchFix4State(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]


def bench_bookkeeping_reads(state, n: int = 50000) -> float:
    start = time.perf_counter()
    for _ in range(n):
        _ = state.dirty_vars
        _ = state.parent_state
        _ = state.substates
        _ = state._backend_vars
    return (time.perf_counter() - start) / n * 1_000_000


def bench_event_cycle(state, n: int = 2000) -> float:
    start = time.perf_counter()
    for i in range(n):
        state.count = i
        state.get_delta()
        state._clean()
    return (time.perf_counter() - start) / n * 1_000_000


def bench_skip_vars(state, n: int = 50000) -> float:
    cls = type(state)
    start = time.perf_counter()
    for _ in range(n):
        cls.get_skip_vars()
    return (time.perf_counter() - start) / n * 1_000_000


def main():
    state = build_state()

    reads_us = bench_bookkeeping_reads(state)
    cycle_us = bench_event_cycle(state)
    skip_us = bench_skip_vars(state)
    print(f"4 bookkeeping attr reads:   {reads_us:8.3f} us/op")
    print(f"setattr+get_delta+_clean:   {cycle_us:8.3f} us/op")
    print(f"get_skip_vars():            {skip_us:8.4f} us/op")

    profiler = cProfile.Profile()
    profiler.enable()
    bench_bookkeeping_reads(state, n=5000)
    bench_event_cycle(state, n=500)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(14)
    print("cProfile (5000 bookkeeping reads + 500 event cycles):")
    print(stream.getvalue())


if __name__ == "__main__":
    main()
