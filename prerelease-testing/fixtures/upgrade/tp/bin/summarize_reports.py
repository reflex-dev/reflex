"""Summarize drive_*.py report JSONs: checks passed/failed per run, failed check names, non-benign console anomalies.

Usage: python3 summarize_reports.py <out_dir> [glob]
"""
import glob
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
pat = sys.argv[2] if len(sys.argv) > 2 else "*-report.json"
for f in sorted(out.glob(pat)):
    d = json.loads(f.read_text())
    ch = d.get("checks", [])
    failed = [c["name"] for c in ch if not c["ok"]]
    an = d.get("anomalies", {})
    print(f"{f.name}: checks={len(ch)} failed={len(failed)}  console_err/warn={len(an.get('console_nonbenign', []))} pageerrors={len(an.get('page_errors', []))} failedreq={len(an.get('failed_requests', []))} badresp={len(an.get('bad_responses', []))}")
    for n in failed:
        print(f"    FAIL {n}")
