"""Build a markdown status table from several suite reports.

Usage: make_table.py OUT_ROOT label1 label2 ...   (reads OUT_ROOT/<label>/<label>_report.json,
or OUT_ROOT/<label>/<sub>_report.json for every report found in the label dir)
"""
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
labels = sys.argv[2:]
cols: dict[str, dict[str, str]] = {}
order: list[str] = []
for lab in labels:
    cols[lab] = {}
    for rp in sorted((root / lab).glob("*_report.json")):
        for r in json.loads(rp.read_text())["results"]:
            n = r["name"]
            if n.endswith("[console]"):
                n = n.replace(" [console]", "") + " [console]"
            if n not in order:
                order.append(n)
            prev = cols[lab].get(n)
            cols[lab][n] = r["status"] if prev is None else f"{prev}/{r['status']}"
print("| check | " + " | ".join(labels) + " |")
print("|---|" + "---|" * len(labels))
for n in order:
    row = [cols[lab].get(n, "-") for lab in labels]
    print(f"| {n} | " + " | ".join(row) + " |")
