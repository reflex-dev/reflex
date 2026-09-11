"""#7050 version-check cache probe.

Runs prerequisites.check_latest_package_version() from an app dir and reports
what it did: the timestamps recorded in .web/reflex.json before and after, and
how long the call took (a real PyPI request is visibly slower than a skip).

Usage (from the app dir):
   <venv>/bin/python version_cache_probe.py <label> [--clear] [--clear-success]
Point HTTPS_PROXY at a dead port to simulate the offline/failure path.
"""
import json
import os
import sys
import time
from pathlib import Path

import reflex  # noqa: F401
assert "/envs/" in reflex.__file__, reflex.__file__
from reflex.utils import prerequisites  # noqa: E402

LABEL = sys.argv[1] if len(sys.argv) > 1 else "probe"
RJ = Path(".web/reflex.json")
KEYS = ("last_version_check_datetime", "last_version_check_attempt_datetime")


def read():
    if not RJ.exists():
        return {}
    return json.loads(RJ.read_text())


data = read()
if "--clear" in sys.argv:
    for k in KEYS:
        data.pop(k, None)
    RJ.write_text(json.dumps(data))
if "--clear-success" in sys.argv:
    data.pop("last_version_check_datetime", None)
    RJ.write_text(json.dumps(data))

before = {k: read().get(k) for k in KEYS}
t = time.perf_counter()
prerequisites.check_latest_package_version("reflex")
dt = time.perf_counter() - t
after = {k: read().get(k) for k in KEYS}

print(f"[{LABEL}] proxy={os.environ.get('HTTPS_PROXY', '')[:40]!r} elapsed={dt:.3f}s")
for k in KEYS:
    mark = "CHANGED" if before[k] != after[k] else "same   "
    print(f"    {mark} {k}: {before[k]} -> {after[k]}")
