"""Compile one app N times in a single interpreter, tracking RSS and hash-cache size.

The app's ``props_mod.make_local_dataclass`` mints a fresh dataclass type on every
page evaluation, so a type-keyed encoding cache that is never released pins one
more class per compile.

Usage (from the app dir):
  <venv>/bin/python ../probes/recompile_rss.py <venv-name> [N]
"""

import gc
import json
import os
import sys

import reflex

VENV = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 25
assert f"/envs/{VENV}/" in reflex.__file__, reflex.__file__
print("reflex", reflex.constants.Reflex.VERSION, "N =", N, flush=True)

from reflex.utils import prerequisites

try:
    from reflex_base.utils import deterministic_hash as dh
except ImportError:
    dh = None


def rss_kb():
    with open("/proc/self/statm") as f:
        return int(f.read().split()[1]) * (os.sysconf("SC_PAGE_SIZE") // 1024)


def cache_sizes():
    if dh is None:
        return {}
    return {
        "str": len(dh._hash_str_encodings),
        "dc_enc": len(dh._hash_dataclass_encodings),
        "dc_layout": len(dh._hash_dataclass_layouts),
        "encoders": len(dh._hash_encoders),
    }


app = prerequisites.get_and_validate_app().app
rows = []
for i in range(1, N + 1):
    app._compile(dry_run=True, use_rich=False, trigger="probe")
    gc.collect()
    rows.append({"i": i, "rss_kb": rss_kb(), "caches": cache_sizes()})
    if i in (1, 2, 3, 5, 10, 15, 20, N):
        print(rows[-1], flush=True)

first, last = rows[0]["rss_kb"], rows[-1]["rss_kb"]
mid = rows[len(rows) // 2]["rss_kb"]
print(
    json.dumps(
        {
            "version": reflex.constants.Reflex.VERSION,
            "n": N,
            "rss_first_kb": first,
            "rss_mid_kb": mid,
            "rss_last_kb": last,
            "growth_first_to_last_kb": last - first,
            "growth_mid_to_last_kb": last - mid,
            "caches_after_last_compile": rows[-1]["caches"],
        },
        indent=2,
    )
)
with open(f"recompile_rss_{VENV}.json", "w") as f:
    json.dump(rows, f, indent=2)
