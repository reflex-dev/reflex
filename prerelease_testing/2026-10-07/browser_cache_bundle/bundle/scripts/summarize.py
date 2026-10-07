"""Aggregate comparable browser-reported byte metrics without timing claims."""

import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for directory in sorted((root / "runs").iterdir()):
    if not directory.is_dir() or directory.name == "harness-negative":
        continue
    assets = json.loads((directory / "assets.json").read_text())
    for path in sorted(directory.glob("*-summary.json")):
        result = json.loads(path.read_text())
        phases = result["phases"]
        checks = [c for g in phases.values() for c in g.get("checks", [])]
        row = {
            "label": directory.name,
            "browser": result["browser"],
            "browser_version": result["browser_version"],
            "checks_passed": sum(c["ok"] for c in checks),
            "checks_failed": sum(not c["ok"] for c in checks),
            "driver_exception": result.get("exception"),
            "js_raw_bytes": assets[".js"]["raw_bytes"],
            "js_gzip_estimate_bytes": assets[".js"]["gzip_estimate_bytes"],
            "css_raw_bytes": assets[".css"]["raw_bytes"],
            "actual_frontend_versions": assets["actual_frontend_versions"],
            "phases": {},
        }
        for name, phase in phases.items():
            row["phases"][name] = {
                k: phase.get(k)
                for k in [
                    "reported_transfer_bytes",
                    "reported_encoded_body_bytes",
                    "websocket_bytes",
                ]
            }
            row["phases"][name]["cdp_finished_encoded_bytes"] = (
                sum(r["finished_encoded_bytes"] for r in phase.get("cdp_requests", []))
                if result["browser"] == "chromium"
                else None
            )
            row["phases"][name]["response_count"] = len(phase.get("responses", []))
            row["phases"][name]["pageerror_count"] = len(phase.get("pageerrors", []))
            row["phases"][name]["failed_request_count"] = len(
                phase.get("failed_requests", [])
            )
        rows.append(row)
(root / "comparison.json").write_text(json.dumps(rows, indent=1))
print("label browser pass fail cold-home reload reports editor warm-reports initial-ws")
for row in rows:
    p = row["phases"]
    print(
        row["label"],
        row["browser"],
        row["checks_passed"],
        row["checks_failed"],
        *[
            p.get(name, {}).get("reported_transfer_bytes")
            for name in [
                "cold_home",
                "warm_reload",
                "reports_nav",
                "editor_nav",
                "warm_reports",
            ]
        ],
        p["cold_home"]["websocket_bytes"]["received"],
    )
