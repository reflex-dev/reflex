"""Time reflex.utils.build.zip_app() on an already-exported app (the #7450 measurement).

Run from the app directory after a `reflex deploy`/`reflex export` left .web/_static in place:
  EXPECT_VENV=cloud_cli-new python -I zip_timing.py <iterations> [exclude_dir ...]
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

import reflex

expect = os.environ["EXPECT_VENV"]
assert f"/envs/{expect}/" in reflex.__file__, reflex.__file__

import logging  # noqa: E402

logging.disable(logging.CRITICAL)
from reflex.utils.build import zip_app  # noqa: E402

iterations = int(sys.argv[1])
excluded = tuple(Path(p).resolve() for p in sys.argv[2:])
front, back, sizes = [], [], {}
for _ in range(iterations):
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.perf_counter()
        zip_app(frontend=True, backend=False, zip_dest_dir=tmp)
        t1 = time.perf_counter()
        zip_app(frontend=False, backend=True, zip_dest_dir=tmp, backend_excluded_dirs=excluded)
        t2 = time.perf_counter()
        front.append(t1 - t0)
        back.append(t2 - t1)
        sizes = {p.name: p.stat().st_size for p in Path(tmp).iterdir()}
print(
    f"{expect}: frontend.zip median {statistics.median(front):.3f}s (min {min(front):.3f}), "
    f"backend.zip median {statistics.median(back) * 1000:.1f}ms (min {min(back) * 1000:.1f}), sizes {sizes}"
)
