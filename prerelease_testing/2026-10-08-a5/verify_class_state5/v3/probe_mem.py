"""Finding 4: what the extra up-front copy costs, measured with tracemalloc in a warm process.

Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_mem.py <rows|floats|ndarray> <keep|drop>
keep = the module keeps its own reference to the data (DATA = load(); class S: _data = DATA)
drop = the default is only referenced by the class (inline literal / del after)
"""
import gc
import os
import sys
import time
import tracemalloc
from typing import Any

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402


class Warm(rx.State):  # pay the framework's first-subclass cost outside the measurement
    _w: list = [1]
    w: list = [1]


kind, mode = sys.argv[1], sys.argv[2]


def load():
    if kind == "rows":
        return [{"id": i, "name": f"row{i}", "score": i * 0.5} for i in range(200_000)]
    if kind == "floats":
        return [float(i) for i in range(1_000_000)]
    import numpy as np

    return np.random.default_rng(0).random(6_553_600)  # 50 MiB, every page touched


def mb(n):
    return f"{n / 2**20:7.1f}MB"


tracemalloc.start()
data = load()
gc.collect()
base, _ = tracemalloc.get_traced_memory()
tracemalloc.reset_peak()
t0 = time.perf_counter()


class Big(rx.State):
    _data: Any = data
    page: int = 0


t1 = time.perf_counter()
if mode == "drop":
    del data
gc.collect()
after_cls, peak_cls = tracemalloc.get_traced_memory()
f = Big.__fields__["_data"] if hasattr(Big, "__fields__") else None
held = None
if f is not None and f.default_factory is not None and hasattr(f.default_factory, "args"):
    held = f.default_factory.args[0]
elif hasattr(Big, "backend_vars"):
    held = Big.backend_vars.get("_data")
same = (held is data) if mode == "keep" else "n/a(dropped)"
s1 = Big(_reflex_internal_init=True)
_ = s1._data
gc.collect()
after_inst, _ = tracemalloc.get_traced_memory()
print(
    f"{version('reflex'):9} {kind:7} {mode:4} classdef={1000 * (t1 - t0):7.1f}ms  "
    f"held-after-classdef(net vs data loaded)={mb(after_cls - base)}  classdef-peak={mb(peak_cls - base)}  "
    f"+first-instance={mb(after_inst - after_cls)}  class holds the user's object itself={same}"
)
