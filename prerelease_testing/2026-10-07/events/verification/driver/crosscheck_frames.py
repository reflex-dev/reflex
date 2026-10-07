#!/usr/bin/env python
"""Cross-check the in-page WebSocket recorder against Playwright's CDP-level frame capture.

For every case of every report: number of /_event data frames ("42/_event,...") received and sent,
as seen by (a) the in-page hook and (b) CDP.  Prints mismatches only (plus a summary).
usage: crosscheck_frames.py <report.json> [...]
"""
import json
import sys

assert "/envs/driver" in sys.prefix, sys.prefix
tot = bad = 0
for path in sys.argv[1:]:
    data = json.load(open(path))
    for name, rep in data["cases"].items():
        tl = rep["timeline"]
        pg_recv = sum(1 for t in tl if t["kind"] == "ws-recv" and t.get("sio"))
        pg_send = sum(1 for t in tl if t["kind"] == "ws-send" and t.get("sio"))
        cdp_recv = sum(1 for f in rep["cdp_frames"] if f["dir"] == "recv" and f["payload"].startswith("42/_event"))
        cdp_send = sum(1 for f in rep["cdp_frames"] if f["dir"] == "send" and f["payload"].startswith("42/_event"))
        tot += 1
        if (pg_recv, pg_send) != (cdp_recv, cdp_send):
            bad += 1
            print(f"MISMATCH {data['label']} {name}: in-page recv/send={pg_recv}/{pg_send} cdp recv/send={cdp_recv}/{cdp_send}")
print(f"checked {tot} cases, {bad} mismatches")
