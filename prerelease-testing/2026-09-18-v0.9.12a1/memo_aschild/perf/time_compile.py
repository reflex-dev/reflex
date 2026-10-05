"""Time reflex's python-side compile of a ~500-component page."""
import os, sys, time, shutil
import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
print("VERSION", rx.constants.Reflex.VERSION, flush=True)
from reflex.utils import prerequisites
from reflex.config import get_config
import importlib
mod = importlib.import_module("perfapp.perfapp")
app = mod.app
from reflex.compiler import compiler
times = []
for rep in range(4):
    app._pages = {}
    t0 = time.perf_counter()
    app._compile(dry_run=True, use_rich=False)
    t1 = time.perf_counter()
    times.append(t1 - t0)
    print(f"rep{rep}: {t1-t0:.3f}s", flush=True)
times_sorted = sorted(times)
print("MEDIAN", f"{(times_sorted[1]+times_sorted[2])/2:.3f}", "MIN", f"{min(times):.3f}")
