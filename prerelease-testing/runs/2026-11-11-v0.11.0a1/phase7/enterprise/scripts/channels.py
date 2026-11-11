"""Summarise the browser channels of fixture driver reports (console errors/warnings, page errors, failed requests, 4xx/5xx).

Usage: channels.py <out/run dir or json> ...   (the fixture drivers write <run>/<scenario>.json with an `anomalies` block)
Known-benign: AG Grid licence banners, favicon 404, the mock-IdP / map-tile tunnel failures are listed but counted separately.
"""

import collections
import json
import re
import sys
from pathlib import Path

BENIGN = re.compile(r"AG Grid|ag-grid|hide the watermark|^\*+|favicon\.ico|ERR_TUNNEL_CONNECTION_FAILED|tile|openstreetmap|arcgis", re.I)
for arg in sys.argv[1:]:
    p = Path(arg)
    files = [p] if p.is_file() else sorted(p.glob("*.json"))
    tot = collections.Counter()
    samples = collections.defaultdict(collections.Counter)
    for f in files:
        try:
            a = json.loads(f.read_text()).get("anomalies") or {}
        except (ValueError, AttributeError):
            continue
        for k in ("console_errors", "console_warnings", "page_errors", "failed_requests", "http_errors"):
            for item in a.get(k, []):
                txt = item if isinstance(item, str) else (item.get("text") or f"{item.get('status', '')} {item.get('url', '')} {item.get('failure', '')}")
                kind = k + ("(benign)" if BENIGN.search(str(txt)) else "")
                tot[kind] += 1
                samples[kind][re.sub(r"\d{4,}|txn=[^& ]+", "#", str(txt))[:160]] += 1
    print(f"== {arg}: {dict(tot) or 'clean'}")
    for kind, c in samples.items():
        for t, n in c.most_common(4):
            print(f"   {kind} x{n}: {t}")
