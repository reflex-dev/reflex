"""Compare two import_sweep outputs (JSON, possibly preceded by non-JSON lines): status + error per module."""
import json
import sys


def load(p):
    s = open(p).read()
    return json.loads(s[s.index("{"):])


a, b = load(sys.argv[1]), load(sys.argv[2])
ma, mb = a.get("results", a), b.get("results", b)
for m in sorted(set(ma) | set(mb)):
    ra, rb = ma.get(m, {}), mb.get(m, {})
    sa = (ra.get("status"), (ra.get("error") or "").strip().splitlines()[-1:])
    sb = (rb.get("status"), (rb.get("error") or "").strip().splitlines()[-1:])
    print(("SAME " if sa == sb else "DIFF ") + f"{m:32s} a3={sa} a4={sb}" + (f" warn a3={len(ra.get('warnings') or [])} a4={len(rb.get('warnings') or [])}"))
