#!/usr/bin/env python
"""Summarise one or more drive_verify reports into compact per-case tables.

usage: analyze.py <report.json> [<report.json> ...] [--md out.md] [--case name]

For every case prints:
  * the three checkpoints of the watched variables (before | t1 = error settled, no other event |
    t2 = after an unrelated ping | t3 = after reload = server truth),
  * the in-page timeline of websocket frames relative to the first scenario click:
      toast frame, every delta frame (with var names), `dom` changes of the displayed vars.
"""

import json
import sys

assert "/envs/driver" in sys.prefix, sys.prefix

VARS = ["v-status", "v-spinner", "v-log", "v-other", "v-load_note", "v-echo_backend"]


def short(v):
    return "''" if v == "" else repr(v)


def case_table(rep):
    s = rep["snapshots"]
    rows = []
    for k in ("before", "t1", "t2", "t3", "t4"):
        if k in s and s[k]:
            rows.append((k, {i: s[k].get(i) for i in VARS + ["v-pings", "hyd"]}))
    return rows


def key_events(rep):
    """Return dict with the headline timings (ms relative to the first scenario click)."""
    tl = rep["timeline"]
    clicks = [t for t in tl if t["kind"] == "click" and not str(t.get("id")).startswith("btn-mode_")]
    first_click = clicks[0]["dt_ms"] if clicks else None
    ping = next((t for t in tl if t["kind"] == "click" and t.get("id") == "btn-ping" and t["doc"] == "doc1"), None)
    out = {"first_click_ms": first_click, "ping_click_ms": ping["dt_ms"] if ping else None}
    toast_frames = [t for t in tl if t["kind"] == "ws-recv" and t.get("toast") and t["doc"] == "doc1"]
    out["toast_frame_ms"] = [t["dt_ms"] for t in toast_frames]
    toast_dom = [t for t in tl if t["kind"] == "toast" and t["count"] > 0 and t["doc"] == "doc1"]
    out["toast_dom_ms"] = [t["dt_ms"] for t in toast_dom][:3]
    deltas = [t for t in tl if t["kind"] == "ws-recv" and t.get("delta") and t["doc"] == "doc1" and (first_click is None or t["dt_ms"] >= first_click - 1)]
    out["delta_frames"] = [(t["dt_ms"], t["delta"]) for t in deltas]
    out["dom_changes"] = [
        (t["dt_ms"], t["id"], t["prev"], t["value"])
        for t in tl
        if t["kind"] == "dom" and t["doc"] == "doc1" and t["prev"] is not None and (first_click is None or t["dt_ms"] >= first_click - 1)
    ]
    out["events_after_click"] = [
        (t["dt_ms"], t.get("events"), t.get("final")) for t in tl if t["kind"] == "ws-recv" and t.get("events") and t["doc"] == "doc1" and (first_click is None or t["dt_ms"] >= first_click - 1)
    ]
    return out


def fmt_vars(d):
    return " ".join(f"{k.split('-', 1)[-1]}={short(v)}" for k, v in d.items() if v is not None and k in VARS)


def main():
    args = sys.argv[1:]
    only = None
    md = None
    if "--case" in args:
        i = args.index("--case")
        only = args[i + 1]
        del args[i : i + 2]
    if "--md" in args:
        i = args.index("--md")
        md = args[i + 1]
        del args[i : i + 2]
    lines = []
    for path in args:
        data = json.load(open(path))
        lines.append(f"### {data['label']}  ({data.get('browser')}, started {data.get('started')})")
        for name, rep in data["cases"].items():
            if only and name != only:
                continue
            lines.append(f"- case `{name}`" + (f"  ERROR={rep['error']}" if rep["error"] else ""))
            for k, d in case_table(rep):
                lines.append(f"    {k:7s} {fmt_vars(d)} pings={d.get('v-pings')}")
            ke = key_events(rep)
            lines.append(f"    first click @0; toast frame @{ke['toast_frame_ms']} ms; toast DOM @{ke['toast_dom_ms']} ms; ping click @{ke['ping_click_ms']} ms")
            for t, dl in ke["delta_frames"]:
                lines.append(f"    delta frame @{t:8.1f} ms: {json.dumps(dl)[:230]}")
            for t, i, p, v in ke["dom_changes"]:
                lines.append(f"    DOM {i:12s} @{t:8.1f} ms: {p!r} -> {v!r}")
            if rep["pageerrors"]:
                lines.append(f"    pageerrors: {[e['text'][:100] for e in rep['pageerrors']]}")
            errs = [c for c in rep["console"] if c["type"] in ("error", "warning")]
            if errs:
                lines.append(f"    console errors/warnings: {[(c['type'], c['text'][:110]) for c in errs][:4]}")
            if rep["dialogs"]:
                lines.append(f"    dialogs: {rep['dialogs']}")
    text = "\n".join(lines)
    print(text)
    if md:
        open(md, "w").write(text + "\n")


if __name__ == "__main__":
    main()
