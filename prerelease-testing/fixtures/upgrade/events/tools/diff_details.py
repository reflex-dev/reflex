"""Compare the details of every suite record between two reports, ignoring timing noise.

Usage: diff_details.py A_report.json B_report.json
Drops keys that carry wall-clock data (timeline, t, *_seconds*, capture_counters, stopped_pids, hits timing) and
prints every record whose remaining details differ, plus records present on one side only.
"""

import json
import sys

NOISE = {"timeline", "t", "capture_counters", "stopped_pids", "b0_seconds_after_click", "typing_seconds",
         "closed_after", "client_ws_closed_after_s", "reconnect_delay_s", "frames", "tb", "handler_counts_before",
         "handler_counts_after", "exc_list", "exc_tail", "console", "page_errors", "delivered_after_s", "ws_closed_after"}


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items() if k not in NOISE and "seconds" not in k and not k.endswith("_s")}
    if isinstance(x, list):
        return [clean(v) for v in x]
    return x


def load(p):
    out = {}
    for r in json.load(open(p))["results"]:
        out.setdefault(r["name"], []).append((r["status"], clean(r["details"])))
    return out


a, b = load(sys.argv[1]), load(sys.argv[2])
same = 0
for name in list(dict.fromkeys(list(a) + list(b))):
    if name.endswith("[console]"):
        continue
    if name not in a or name not in b:
        print(f"ONLY-ONE-SIDE {name}: A={a.get(name)} B={b.get(name)}")
        continue
    if a[name] == b[name]:
        same += 1
        continue
    print(f"DIFF {name}")
    print("   A:", json.dumps(a[name])[:1500])
    print("   B:", json.dumps(b[name])[:1500])
print(f"identical records: {same}")
