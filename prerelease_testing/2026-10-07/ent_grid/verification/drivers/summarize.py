"""Summarise the verifier runs (out/<run>/<scenario>.json) as markdown tables.

Usage: $SB/envs/driver/bin/python drivers/summarize.py out > out/SUMMARY.md
"""

import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
ENT_RUNS = ["entv_s912_prod", "entv_a1_prod", "entv_a2_prod", "entv_a2_dev", "entv_a2_prod_lazyflag"]
CORE_RUNS = ["corev_s912_prod", "corev_a1_prod", "corev_a2_prod", "corev_a2_dev"]


def cell(grids: dict, wid: str) -> str:
    g = grids.get(wid)
    if not g:
        return "-"
    return f"{len(g['headers'])}h/{g['cells']}c"


def load(run: str, scen: str):
    p = root / run / f"{scen}.json"
    return json.loads(p.read_text()) if p.exists() else None


ent_scen = sorted({p.stem for r in ENT_RUNS for p in (root / r).glob("s[0-9]*.json")}, key=lambda s: int(s.split("_")[0][1:]))
print("## Enterprise fixture (entv): `.ag-header-cell` / `.ag-cell` counts 4 s after boot settled\n")
print("Cells: state-var grid | literal grid (or the grids present on that page). h = header cells, c = body cells.\n")
print("| scenario | " + " | ".join(ENT_RUNS) + " |")
print("|---|" + "---|" * len(ENT_RUNS))
for s in ent_scen:
    row = []
    for r in ENT_RUNS:
        d = load(r, s)
        if not d:
            row.append("n/a")
            continue
        g = d["measure_plus4s"]["grids"]
        parts = [f"{k}={cell(g, k)}" for k in g]
        if "detail" in d:
            parts.append("detail-grid headers: " + ", ".join(f"{k}={v['detail_headers']}" for k, v in d["detail"].items()))
        if "badges" in d:
            parts.append(f"badges={d['badges']}")
        if d["pageerrors"]:
            parts.append("PAGEERROR " + d["pageerrors"][0][:40])
        crash = [c for c in d["console"] if "#130" in c["text"]]
        if crash:
            parts.append("React #130 (page crashed)")
        row.append("<br>".join(parts))
    print(f"| {s} | " + " | ".join(row) + " |")

core_scen = sorted({p.stem for r in CORE_RUNS for p in (root / r).glob("c[0-9]*.json")})
print("\n## Core-only fixture (corev, no enterprise): ReflexProbe text (`typeof window.__reflex` at render) and render count\n")
print("| scenario | " + " | ".join(CORE_RUNS) + " |")
print("|---|" + "---|" * len(CORE_RUNS))
for s in core_scen:
    row = []
    for r in CORE_RUNS:
        d = load(r, s)
        if not d:
            row.append("n/a")
            continue
        m = d["measure_plus4s"]
        parts = []
        for pid, txt in m["probes"].items():
            label = pid.removeprefix("probe-")
            parts.append(f"{label}: {txt.split('|')[1]} (renders {m['probeCounts'].get(label)})")
        if "dyn_badge" in d:
            parts.append(f"dynamic component badge={d['dyn_badge']!r}")
        row.append("<br>".join(parts))
    print(f"| {s} | " + " | ".join(row) + " |")

print("\n## Boot websocket deltas (first full load) — substates carried by each delta frame\n")
for r, s in [(r, "c1_full_load") for r in CORE_RUNS] + [(r, "s1_full_load") for r in ENT_RUNS]:
    d = load(r, s)
    if not d:
        continue
    print(f"- **{r} / {s}**: `window.__reflex` assigned at {d['measure']['reflexSetAt']:.1f} ms")
    for f in d["boot_frames"]:
        if f["dir"] == "ws_out" and (f.get("auth_event_name") or f.get("event_name")):
            print(f"  - {f['t']} ms OUT {f.get('auth_event_name') or f.get('event_name')}" + (" (in socket.io connect auth)" if f.get("auth_event_name") else ""))
        if f.get("delta") is not None:
            subs = [k.split(".")[-1] for k in f["delta"]]
            print(f"  - {f['t']} ms IN delta {subs}")
