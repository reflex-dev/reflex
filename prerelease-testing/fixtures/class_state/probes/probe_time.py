"""Finding 4 timing (no tracemalloc): class-definition time of a state with a large backend default, warm process.

Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_time.py <rows|floats|ndarray|df>
"""
import os
import sys
import time
from typing import Any

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402


class Warm(rx.State):
    _w: list = [1]
    w: list = [1]


kind = sys.argv[1]
if kind == "rows":
    data = [{"id": i, "name": f"row{i}", "score": i * 0.5} for i in range(200_000)]
elif kind == "floats":
    data = [float(i) for i in range(1_000_000)]
elif kind == "ndarray":
    import numpy as np

    data = np.random.default_rng(0).random(6_553_600)
else:
    import numpy as np
    import pandas as pd

    data = pd.DataFrame(np.random.default_rng(0).random((819_200, 8)))
ts = []
for i in range(3):
    t0 = time.perf_counter()
    type(f"Big{i}", (rx.State,), {"__module__": __name__, "__annotations__": {"_data": Any}, "_data": data})
    ts.append(1000 * (time.perf_counter() - t0))
print(f"{version('reflex'):9} {kind:7} classdef ms (3 runs): " + " ".join(f"{t:7.1f}" for t in ts))
