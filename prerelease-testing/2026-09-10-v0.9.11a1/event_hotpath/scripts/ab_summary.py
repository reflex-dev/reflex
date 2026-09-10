"""Aggregate logs3/ab_<label>_r<N>.json into a comparison table (median over rounds).

Usage: python ab_summary.py <logs_dir> [--md]
worker CPU = CPU delta of the granian worker process (the non-root pid with the largest delta); tree CPU = all server pids.
"""
from __future__ import annotations

import glob
import json
import statistics
import sys
from collections import defaultdict

d = sys.argv[1]
md = "--md" in sys.argv
rows = defaultdict(list)  # (label, mode) -> list of run dicts
for f in sorted(glob.glob(f"{d}/ab_*_r*.json")):
    j = json.load(open(f))
    label = j["label"].rsplit("_r", 1)[0]
    for r in j["runs"]:
        pid_cpu = r.get("cpu_by_pid_s", {})
        root = str(min(int(p) for p in pid_cpu)) if pid_cpu else None
        worker = max((p for p in pid_cpu if p != root), key=lambda p: pid_cpu[p], default=None)
        r["worker_cpu_us_per_event"] = round(pid_cpu[worker] / r["n"] * 1e6, 1) if worker and r.get("n") else (
            round(pid_cpu[worker] / int(r["mode"].split("_")[1]) * 1e6, 1) if worker else None)
        r["root_cpu_s"] = pid_cpu.get(root)
        rows[(label, r["mode"])].append(r)


def med(rs, k):
    xs = [r[k] for r in rs if r.get(k) is not None]
    return round(statistics.median(xs), 2) if xs else None


keys = ["ev_per_s", "p50_ms", "p99_ms", "worker_cpu_us_per_event", "server_cpu_us_per_event", "rss_mb"]
out = []
hdr = ["label", "mode", "rounds", "exact", *keys, "server_py", "load_before"]
out.append(hdr)
for (label, mode), rs in sorted(rows.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    out.append([label, mode, len(rs), all(r["exact"] for r in rs), *[med(rs, k) for k in keys],
                rs[0].get("server_py") or "", "/".join(r.get("load1_before", "?") for r in rs)])
w = [max(len(str(r[i])) for r in out) for i in range(len(hdr))]
if md:
    print("| " + " | ".join(hdr) + " |"); print("|" + "|".join("---" for _ in hdr) + "|")
    for r in out[1:]:
        print("| " + " | ".join(str(x) for x in r) + " |")
else:
    for r in out:
        print("  ".join(str(x).ljust(w[i]) for i, x in enumerate(r)))
# ratios new vs old per python version
print()
for py in ("311", "313"):
    for mode in sorted({m for (_, m) in rows}):
        n, o = rows.get((f"new{py}", mode)), rows.get((f"old{py}", mode))
        if n and o:
            def r(k, inv=False):
                a, b = med(n, k), med(o, k)
                if not a or not b:
                    return "n/a"
                return f"{(a / b - 1) * 100:+.1f}%"
            print(f"py{py} {mode:20} new vs old: throughput {r('ev_per_s')}  p50 {r('p50_ms')}  p99 {r('p99_ms')}  worker CPU/event {r('worker_cpu_us_per_event')}  tree CPU/event {r('server_cpu_us_per_event')}")
