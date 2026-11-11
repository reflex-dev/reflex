"""Markdown status table from suite reports, one column per label.

Usage: make_table2.py label=report.json[,report2.json] ...
A check present in several reports of one column shows each status joined by '/'.
"[console]" rows (non-benign console/page errors per test) are kept.
"""
import json
import sys

cols: dict[str, dict[str, str]] = {}
labels: list[str] = []
order: list[str] = []
for arg in sys.argv[1:]:
    label, _, paths = arg.partition("=")
    labels.append(label)
    cols[label] = {}
    for p in paths.split(","):
        for r in json.load(open(p))["results"]:
            n = r["name"]
            if n not in order:
                order.append(n)
            prev = cols[label].get(n)
            cols[label][n] = r["status"] if prev is None else f"{prev}/{r['status']}"
print("| check | " + " | ".join(labels) + " |")
print("|---|" + "---|" * len(labels))
for n in order:
    print(f"| {n} | " + " | ".join(cols[l].get(n, "-") for l in labels) + " |")
