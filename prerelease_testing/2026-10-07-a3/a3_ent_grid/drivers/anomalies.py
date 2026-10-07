"""List non-benign console errors/warnings and page errors per scenario, plus grid-vs-__reflex timing.

Usage: $SB/envs/driver/bin/python drivers/anomalies.py out/<run> [out/<run> ...]
For every <scenario>.json: page errors, console errors/warnings that are not AG Grid licence banners / known-benign,
the time `window.__reflex` was assigned, and the first time each grid wrapper had header cells (from the 50 ms poll).
"""

import json
import re
import sys
from pathlib import Path

assert "/scratchpad/envs/driver/" in sys.executable, sys.executable

BENIGN = [
    re.compile(r"^\*+$|AG Grid Enterprise License|License Key Not Found|unlocked for trial|hide the watermark|^\* *\*$|^\*\s.*\*$"),
    re.compile(r"Hey developer|HydrateFallback|Download the React DevTools|\[vite\] (connecting|connected)"),
    re.compile(r"favicon\.ico"),
]


def benign(t: str) -> bool:
    return any(p.search(t.strip()) for p in BENIGN)


for run in sys.argv[1:]:
    print(f"== {run}")
    for f in sorted(Path(run).glob("*.json")):
        if f.name == "server_check.json":
            continue
        d = json.loads(f.read_text())
        bad = [c for c in d.get("console", []) if c["type"] in ("error", "warning") and not benign(c["text"])]
        first = {}
        for line in d.get("timeline", []):
            m = re.match(r"\s*([\d.]+)ms grid counts \(headers, cells\) (.*)$", line)
            if m:
                for k, v in json.loads(m.group(2)).items():
                    if v[0] and k not in first:
                        first[k] = float(m.group(1))
        rs = d["measure"].get("reflexSetAt")
        cr = d["measure"].get("cellRenders") or {}
        if cr.get("n"):
            tim_cr = f"; trace cell renders n={cr['n']} first@{cr['first_t']:.0f}ms without_reflex={cr['without_reflex']}"
        else:
            tim_cr = ""
        tim = ", ".join(f"{k} headers@{v:.0f}ms" for k, v in first.items())
        he = d.get("http_errors", [])
        print(f"  {f.stem}: __reflex@{rs if rs is None else round(rs)}ms; {tim or 'no grid headers'}{tim_cr}; pageerrors={len(d.get("pageerrors", []))} non-benign console={len(bad)} http>=400/failed={[(h.get("status") or h.get("failure"), h["url"].split("/", 3)[-1][:60]) for h in he]}")
        for e in d.get("pageerrors", [])[:5]:
            print(f"     PAGEERROR {e[:300]}")
        for c in bad[:8]:
            print(f"     {c['type'].upper()} {c['text'][:300]}")
