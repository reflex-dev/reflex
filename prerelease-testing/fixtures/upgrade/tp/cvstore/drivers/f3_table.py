"""Summarize drive_cvstore results: per label x variant, the storage value(s) after reload / probe / reload2.
Usage: f3_table.py <shots/f3 dir> label [label...]"""
import json
import sys
from pathlib import Path

d = Path(sys.argv[1])
labels = sys.argv[2:]
variants = ["a", "b", "c", "d", "e_cookie", "e_session", "f", "g"]
print(f"{'variant':10s} " + " | ".join(f"{l:34s}" for l in labels))
for v in variants:
    cells = []
    for l in labels:
        f = d / f"{l}-{v}.json"
        if not f.exists():
            cells.append("(missing)")
            continue
        rec = json.loads(f.read_text())
        ph = {p["phase"]: p for p in rec["phases"]}
        def st(name):
            p = ph.get(name)
            if not p:
                return "-"
            return ",".join(repr(x) for x in p["storage"].values())
        cells.append(f"reload={st('reload')} probe={st('probe')} r2={st('reload2')}")
    print(f"{v:10s} " + " | ".join(f"{c:34s}" for c in cells))
