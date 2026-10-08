"""Import-time cost of many states with small mutable defaults (a4 vs a5 vs 0.9.12).
Run: EXPECT_VENV=<venv> python -I probe_many_states.py"""
import os
import time

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402


class Warm(rx.State):
    a: int = 0


t0 = time.perf_counter()
for i in range(400):
    type(f"S{i}", (rx.State,), {"__module__": __name__, "__annotations__": {"items": list[str], "cfg": dict[str, int], "_rows": list[dict], "tags": set[str], "n": int},
                                "items": ["a", "b", "c"], "cfg": {"x": 1, "y": 2}, "_rows": [{"id": j} for j in range(20)], "tags": {"t"}, "n": 0})
t1 = time.perf_counter()
print(f"{version('reflex')}: 400 states x 4 small mutable defaults: {1000 * (t1 - t0):.0f} ms")
