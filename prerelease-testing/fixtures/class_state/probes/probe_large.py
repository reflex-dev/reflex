"""Large backend-var defaults: class-definition time and memory, a4 vs a5 vs 0.9.12.
Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_large.py <list|ndarray|df|dictrows>"""
import gc
import os
import sys
import time
from typing import Any

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402


def rss_mb():
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS"):
                return int(line.split()[1]) / 1024
    return -1


def hwm_mb():
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmHWM"):
                return int(line.split()[1]) / 1024
    return -1


kind = sys.argv[1]
gc.collect()
r0 = rss_mb()
if kind == "list":
    value = list(range(1_600_000))  # ~ 57 MB of list + int objects
elif kind == "ndarray":
    import numpy as np

    value = np.zeros(6_553_600)  # 50 MiB float64
elif kind == "df":
    import numpy as np
    import pandas as pd

    value = pd.DataFrame(np.zeros((819_200, 8)))  # 50 MiB
elif kind == "dictrows":
    value = [{"id": i, "name": f"row{i}"} for i in range(200_000)]
else:
    raise SystemExit("kind?")
gc.collect()
r1 = rss_mb()
t0 = time.perf_counter()


class Big(rx.State):
    _data: Any = value
    page: int = 0


t1 = time.perf_counter()
gc.collect()
r2 = rss_mb()
t2 = time.perf_counter()
s = Big(_reflex_internal_init=True)
_ = s._data
t3 = time.perf_counter()
gc.collect()
r3 = rss_mb()
del value
gc.collect()
r4 = rss_mb()
print(
    f"{version('reflex'):10} {kind:8} value={r1 - r0:6.1f}MB classdef={1000 * (t1 - t0):8.1f}ms (+{r2 - r1:6.1f}MB) "
    f"first-instance+access={1000 * (t3 - t2):8.1f}ms (+{r3 - r2:6.1f}MB) after `del value`={r4:6.1f}MB rss peak={hwm_mb():6.1f}MB"
)
