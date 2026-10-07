"""Compare non-benign console/page errors between driver report JSONs (normalising ports, hashes, addresses).

Usage: python3 compare_console.py <report_a.json> <report_b.json> [<report_c.json> ...]
"""
import json
import re
import sys


def norm(s: str) -> str:
    s = re.sub(r"localhost:\d+", "localhost:PORT", s)
    s = re.sub(r"v=[0-9a-f]{6,}", "v=H", s)
    s = re.sub(r"0x[0-9a-f]+", "0xA", s)
    s = re.sub(r"\d{5,}", "N", s)
    return s[:160].replace("\n", " ")


sets = []
for f in sys.argv[1:]:
    d = json.load(open(f))
    items = set()
    for c in d["console_all"]:
        if c["type"] in ("error", "warning") and not c["benign"]:
            items.add(("console-" + c["type"], c["where"], norm(c["text"])))
    for e in d["anomalies"]["page_errors"]:
        items.add(("pageerror", e["where"], norm(e["error"])))
    sets.append((f, items))
base_f, base = sets[0]
print(f"base {base_f}: {len(base)} distinct anomalies")
for f, s in sets[1:]:
    print(f"== {f}: {len(s)} distinct; only-in-base={len(base - s)} only-in-this={len(s - base)}")
    for x in sorted(base - s):
        print("   only in base:", x)
    for x in sorted(s - base):
        print("   only in this:", x)
