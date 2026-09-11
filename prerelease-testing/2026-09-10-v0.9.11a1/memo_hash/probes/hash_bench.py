"""Micro-benchmark of the memo content hash on this app's heaviest page.

Usage (from an app dir): <venv>/bin/python ../probes/hash_bench.py <venv-name> [reps]
"""

import statistics
import sys
import time

import reflex

VENV = sys.argv[1]
REPS = int(sys.argv[2]) if len(sys.argv) > 2 else 11
assert f"/envs/{VENV}/" in reflex.__file__, reflex.__file__

from reflex.utils import prerequisites

app = prerequisites.get_and_validate_app().app
app._compile(dry_run=True, use_rich=False, trigger="probe")

try:  # 0.9.11a1
    from reflex_base.components.memo import component_hash
    from reflex_base.utils.deterministic_hash import clear_hash_caches

    def h(c):
        return component_hash(c, recursive=True)
except ImportError:  # 0.9.10.post2
    def clear_hash_caches():
        return None

    def h(c):
        return c._get_component_hash()

import reflex as rx

from memoapp.memoapp import page2  # noqa: E402

comp = rx.compiler.compiler.into_component(page2)
comp.render()  # warm render caches so we time hashing, not rendering

times = []
for _ in range(REPS):
    clear_hash_caches()
    t0 = time.perf_counter()
    h(comp)
    times.append(time.perf_counter() - t0)
print(
    f"{reflex.constants.Reflex.VERSION}: min={min(times) * 1000:.2f}ms "
    f"median={statistics.median(times) * 1000:.2f}ms reps={REPS}"
)
