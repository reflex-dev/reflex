"""Micro-benchmark for ENG-10093: deep type-validation on hot paths.

Measures:
  1. Assigning a 100k-int list to a state var (__setattr__ _isinstance walk).
  2. Reading a cached computed var returning 10k dicts (return-type check).

Runs in the current env mode, then re-execs itself with REFLEX_ENV_MODE=prod.
"""

import cProfile
import io
import os
import pstats
import subprocess
import sys
import time


def build_state():
    import reflex as rx

    class BenchFix1State(rx.State):
        items: list[int] = []

        @rx.var(cache=True)
        def big(self) -> list[dict[str, int]]:
            return [{"a": i} for i in range(10_000)]

    return BenchFix1State()  # pyright: ignore [reportCallIssue]


def bench_assign(state, n: int = 10) -> float:
    payload = list(range(100_000))
    start = time.perf_counter()
    for _ in range(n):
        state.items = payload
    return (time.perf_counter() - start) / n * 1000


def bench_cached_read(state, n: int = 200) -> float:
    _ = state.big  # prime the cache
    start = time.perf_counter()
    for _ in range(n):
        _ = state.big
    return (time.perf_counter() - start) / n * 1000


def main():
    mode = os.environ.get("REFLEX_ENV_MODE", "dev")
    state = build_state()

    assign_ms = bench_assign(state)
    read_ms = bench_cached_read(state)
    print(f"[{mode}] assign 100k-int list:     {assign_ms:8.3f} ms/op")
    print(f"[{mode}] cached computed var read: {read_ms:8.4f} ms/op")

    profiler = cProfile.Profile()
    profiler.enable()
    bench_assign(state, n=3)
    bench_cached_read(state, n=20)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(12)
    print(f"[{mode}] cProfile (3 assigns + 20 cached reads):")
    print(stream.getvalue())

    if "REFLEX_ENV_MODE" not in os.environ:
        env = os.environ | {"REFLEX_ENV_MODE": "prod"}
        subprocess.run([sys.executable, os.path.abspath(__file__)], env=env, check=True)


if __name__ == "__main__":
    main()
