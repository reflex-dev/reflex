"""Summarize a vauthd audit JSONL: counts per (action, outcome, route) and page-guard records whose route is not a protected page.

Usage: $SB/envs/driver/bin/python -I audit_routes.py <audit.jsonl>
"""

import json
import sys
from collections import Counter
from urllib.parse import urlparse

PROTECTED = ("/vault", "/vault2", "/item/")
recs = [json.loads(line) for line in open(sys.argv[1]) if line.strip()] if len(sys.argv) > 1 else []
c = Counter()
odd = []
for r in recs:
    u = urlparse(r.get("route") or "")
    route = u.path + (f"?{u.query}" if u.query else "")
    c[(r["action"], r["outcome"], route, r.get("sub"), r.get("handler"))] += 1
    if r["action"] == "page_load" and not u.path.startswith(PROTECTED):
        odd.append(r)
print(f"audit records: {len(recs)}; session_id present in {sum(1 for r in recs if r.get('session'))}")
for (a, o, route, sub, h), n in sorted(c.items(), key=lambda kv: (kv[0][0], kv[0][2] or "")):
    print(f"  {n:3d} x {a:16s} {o:22s} route={route!r} sub={sub} handler={h}")
print(f"page_load records with a non-protected route (stale router view?): {len(odd)}")
for r in odd[:10]:
    print("   ", json.dumps(r))
