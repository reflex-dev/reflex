"""Compare two import_sweep outputs (JSON, possibly preceded by non-JSON lines): status + last error line per module.

Usage: cmp_sweep.py <expected.json, e.g. tp/expected/import_sweep.json> <this run.json>  (venv paths are normalized)
"""
import json
import re
import sys


def load(p):
    s = open(p).read()
    return json.loads(s[s.index("{"):])


a, b = load(sys.argv[1]), load(sys.argv[2])
ma, mb = a.get("results", a), b.get("results", b)
for m in sorted(set(ma) | set(mb)):
    ra, rb = ma.get(m, {}), mb.get(m, {})
    sa = (ra.get("status"), [re.sub(r"/\S*/envs/[^/]+/", "<venv>/", e) for e in (ra.get("error") or "").strip().splitlines()[-1:]])
    sb = (rb.get("status"), [re.sub(r"/\S*/envs/[^/]+/", "<venv>/", e) for e in (rb.get("error") or "").strip().splitlines()[-1:]])
    print(("SAME " if sa == sb else "DIFF ") + f"{m:32s} expected={sa} this={sb}" + (f" warn expected={len(ra.get('warnings') or [])} this={len(rb.get('warnings') or [])}"))
