#!/usr/bin/env python
"""Cross-version / cross-manager table from the drive_verify reports.

usage: make_table.py <out_dir_root> > table.md

Cell = `t1 | t2 | t3` of the case's primary variable:
  t1 = browser, error settled, NO other event sent
  t2 = browser, after an unrelated `ping` click
  t3 = after a page reload (= what the server holds)
Class (vs. the 0.8.26 behaviour as the "ideal": delta delivered with the error, persisted):
  OK       t1 == t3 == ideal
  STALE    t1 old, t2 == t3 == ideal      (E-1: delivered only with the next event)
  DROPPED  t1 == t2 == t3 == old          (never delivered, not persisted)
  DIVERGED t1 shows a value the server does not have (t3 != t1)  (E-2)
"""

import json
import sys
from pathlib import Path

assert "/envs/driver" in sys.prefix, sys.prefix
root = Path(sys.argv[1])
COMPACT = "--compact" in sys.argv

# (case -> (primary var id, ideal final value, old/initial value))
PRIMARY = {
    "direct": ("v-status", "direct-partial", "idle"),
    "async": ("v-status", "async-partial", "idle"),
    "chain": ("v-log", "B-partial", ""),
    "gen": ("v-status", "gen-after", "idle"),
    "agen": ("v-status", "agen-after", "idle"),
    "spinner": ("v-spinner", "off", "on"),  # initial is off; the stale/bad value is "on"
    "bg_inside": ("v-status", "bg-inside-partial", "idle"),
    "bg_two": ("v-status", "bg-block2-partial", "bg-block1-committed"),
    "onload_initial": ("v-load_note", "load-partial", "none"),
    "sup_split": ("v-log", None, None),
    "sup_same": ("v-log", None, None),
}

RUNS = [
    ("disk/memory", [
        ("0.8.26 dev disk", "r0826_dev_disk"),
        ("0.9.0 dev disk", "r090_dev_disk"),
        ("0.9.12 dev disk", "stable_dev_disk"),
        ("0.10.0a1 dev disk", "alpha_dev_disk"),
        ("0.10.0a2 dev disk", "alpha2_dev_disk"),
        ("0.10.0a2 dev disk (run 2)", "alpha2_dev_disk_run2"),
        ("0.10.0a2 dev memory", "alpha2_dev_memory"),
        ("0.10.0a2 prod disk", "alpha2_prod_disk"),
        ("0.9.12 prod disk", "stable_prod_disk"),
    ]),
    ("redis", [
        ("0.8.26 dev redis", "r0826_dev_redis"),
        ("0.9.0 dev redis", "r090_dev_redis"),
        ("0.9.12 dev redis", "stable_dev_redis"),
        ("0.10.0a1 dev redis", "alpha_dev_redis"),
        ("0.10.0a2 dev redis", "alpha2_dev_redis"),
        ("0.10.0a2 prod redis (1 worker)", "alpha2_prod_redis"),
        ("0.10.0a2 prod redis (9 workers)", "alpha2_prod_redis_mw"),
        ("0.9.12 prod redis (1 worker)", "stable_prod_redis"),
        ("0.10.0a2 dev redis + OPLOCK", "alpha2_dev_redis_oplock"),
    ]),
]


def load(label):
    p = root / label / f"{label}_report.json"
    cases = json.load(open(p))["cases"] if p.exists() else {}
    # the 0.9.12 supersedes cases of the first run hit a load hiccup (a was superseded before its post-yield code
    # ran, see NOTES); the clean re-run replaces them
    if label == "stable_dev_disk":
        rp = root / "stable_dev_disk_rerun_sup" / "stable_dev_disk_rerun_sup_report.json"
        if rp.exists():
            rerun = json.load(open(rp))["cases"]
            for k in ("sup_same", "sup_split"):
                if k in rerun:
                    cases[k] = rerun[k]
    return cases


def classify(case, t1, t2, t3):
    var, ideal, old = PRIMARY[case]
    if ideal is None:  # no ideal known (supersedes cases): only flag browser/server divergence
        return "DIVERGED" if t1 != t3 else ""
    if t1 == ideal and t3 == ideal:
        return "OK"
    if t1 != ideal and t2 == ideal and t3 == ideal:
        return "STALE"
    if t1 == old and t2 == old and t3 == old and case != "spinner":
        return "DROPPED"
    if t3 != t1:
        return "DIVERGED"
    return "?"


for title, runs in RUNS:
    print(f"\n#### {title}\n")
    labels = [r[0] for r in runs]
    print("| case (primary var) | " + " | ".join(labels) + " |")
    print("|---|" + "---|" * len(labels))
    data = {lab: load(lab) for _, lab in runs}
    for case, (var, ideal, old) in PRIMARY.items():
        cells = []
        for name, lab in runs:
            rep = data[lab].get(case)
            if not rep or not rep["snapshots"].get("t1"):
                cells.append("-")
                continue
            s = rep["snapshots"]
            t1, t2, t3 = (s.get(k, {}).get(var) for k in ("t1", "t2", "t3"))
            c = classify(case, t1, t2, t3)
            if COMPACT:
                cells.append(c or f"`{t3}`")
            else:
                cells.append(f"`{t1}` / `{t2}` / `{t3}`" + (f" **{c}**" if c else ""))
        print(f"| {case} (`{var[2:]}`) | " + " | ".join(cells) + " |")
