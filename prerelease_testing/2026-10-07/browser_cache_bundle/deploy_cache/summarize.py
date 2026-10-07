"""Summarize deployment checks and inspect the actual initial hydrate deltas."""

import gzip
import json
from pathlib import Path

root = Path(__file__).resolve().parent / "evidence"
summary = {"deployment": [], "uncached": [], "initial_frames": {}}
for path in sorted(root.glob("*/*/*/result.json")):
    data = json.loads(path.read_text())
    summary["deployment"].append(
        {
            "path": str(path.relative_to(root)),
            "passed": sum(check["ok"] for check in data["checks"]),
            "failed": sum(not check["ok"] for check in data["checks"]),
            "exception": data.get("exception"),
            "console_errors": data["console_errors"],
            "history_state": data.get("history_state"),
            "navigation": data["navigation"],
        }
    )
for path in sorted(root.glob("uncached-stock/*/result.json")):
    data = json.loads(path.read_text())
    for browser, result in data["browsers"].items():
        summary["uncached"].append(
            {
                "path": str(path.relative_to(root)),
                "browser": browser,
                "passed": sum(check["ok"] for check in result["checks"]),
                "failed": sum(not check["ok"] for check in result["checks"]),
                "exception": result.get("exception"),
            }
        )
for case in (
    "alpha2-alpha2-A",
    "alpha2-alpha2-B",
    "alpha2-alpha2-B-extra",
    "stable-alpha2-A",
):
    path = root / "deployment" / case / "chromium/trace.json.gz"
    with gzip.open(path, "rt") as stream:
        data = json.load(stream)
    frames = data["websockets"][0]["frames"]
    summary["initial_frames"][case] = frames[:8]
(root.parent / "summary.json").write_text(json.dumps(summary, indent=2))
print(
    json.dumps(
        {
            "deployment_checks": sum(
                row["passed"] + row["failed"] for row in summary["deployment"]
            ),
            "deployment_failed_assertions": sum(
                row["failed"] for row in summary["deployment"]
            ),
            "deployment_exceptions": sum(
                bool(row["exception"]) for row in summary["deployment"]
            ),
            "uncached_checks": sum(
                row["passed"] + row["failed"] for row in summary["uncached"]
            ),
            "uncached_failures": sum(
                row["failed"] + bool(row["exception"]) for row in summary["uncached"]
            ),
        },
        indent=2,
    )
)
