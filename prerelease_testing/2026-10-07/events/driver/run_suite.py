"""Run selected test groups against a running evapp. Usage: run_suite.py BASE OUTDIR LABEL group[,group...]"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import Harness  # noqa: E402

base, outdir, label, groups = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4].split(",")
only = set(sys.argv[5].split(",")) if len(sys.argv) > 5 else None
h = Harness(base, outdir, label)
try:
    for g in groups:
        modname, _, listname = g.partition(":")
        mod = __import__(f"tests_{modname}")
        for fn in getattr(mod, listname or "ALL"):
            if only and fn.__name__ not in only:
                continue
            print(f"--- {fn.__name__}", flush=True)
            h.run(fn.__name__, fn)
finally:
    p = h.dump()
    h.close()
    print("REPORT", p)
