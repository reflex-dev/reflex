#!/usr/bin/env python
"""Toast-frame vs mutated-value-frame timing table (ms after the first scenario click), from drive_verify reports.

usage: make_timings.py <out_root>  > timings.md
The "value frame" is the first websocket delta frame after the click whose payload contains the case's final
mutated value for the primary var; "ping" is when the unrelated `ping` click happened.
"""
import json
import sys
from pathlib import Path

assert "/envs/driver" in sys.prefix, sys.prefix
root = Path(sys.argv[1])
CASES = {  # case: (delta key, ideal value; for lists: the substring)
    "direct": ("v.status", "direct-partial"),
    "async": ("v.status", "async-partial"),
    "chain": ("v.log", "B-partial"),
    "gen": ("v.status", "gen-after"),
    "spinner": ("v.spinner", "off"),
}
RUNS = [("0.8.26 dev disk", "r0826_dev_disk"), ("0.9.12 dev disk", "stable_dev_disk"), ("0.10.0a1 dev disk", "alpha_dev_disk"),
        ("0.10.0a2 dev disk", "alpha2_dev_disk"), ("0.10.0a2 dev disk (run 2)", "alpha2_dev_disk_run2"),
        ("0.10.0a2 prod disk", "alpha2_prod_disk"), ("0.9.12 prod disk", "stable_prod_disk"), ("0.10.0a2 dev memory", "alpha2_dev_memory"),
        ("0.10.0a2 dev disk, 40 s idle", "alpha2_dev_disk_idle40")]


def timing(rep, key, ideal):
    tl = rep["timeline"]
    clicks = [t for t in tl if t["kind"] == "click" and not str(t.get("id")).startswith("btn-mode_") and t["doc"] == "doc1"]
    c0 = clicks[0]["dt_ms"] if clicks else 0
    ping = next((t["dt_ms"] for t in clicks if t.get("id") == "btn-ping"), None)
    toast = next((t["dt_ms"] for t in tl if t["kind"] == "ws-recv" and t.get("toast") and t["doc"] == "doc1"), None)
    val = None
    for t in tl:
        if t["kind"] == "ws-recv" and t["doc"] == "doc1" and t.get("delta") and t["dt_ms"] >= c0 - 1:
            v = t["delta"].get(key)
            if v is not None and (ideal in (v if isinstance(v, list) else [v]) or v == ideal):
                if key == "v.spinner" and v == "off" and ping is not None and t["dt_ms"] < 100:
                    continue
                val = t["dt_ms"]
                break
    return round(toast - c0, 1) if toast is not None else None, round(val - c0, 1) if val is not None else None, round(ping - c0, 1) if ping else None


print("| run | case | toast frame (ms) | frame carrying the final value (ms) | ping click (ms) | verdict |")
print("|---|---|---|---|---|---|")
for name, lab in RUNS:
    p = root / lab / f"{lab}_report.json"
    if not p.exists():
        continue
    cases = json.load(open(p))["cases"]
    if lab == "alpha2_dev_disk_idle40":
        cases = {"idle40": cases["idle40"]}
        spec = {"idle40": ("v.status", "direct-partial")}
    else:
        spec = CASES
    for case, (key, ideal) in spec.items():
        if case not in cases:
            continue
        toast, val, ping = timing(cases[case], key, ideal)
        if val is None:
            verdict = "never"
        elif toast is not None and abs(val - toast) < 40:
            verdict = "with the error"
        elif ping is not None and val >= ping:
            verdict = "with the NEXT event"
        else:
            verdict = "before the error"
        print(f"| {name} | {case} | {toast} | {val} | {ping} | {verdict} |")
