"""Summarize retained results and hash the actual executed fixture copies."""

import gzip
import hashlib
import json
import re
from pathlib import Path


def main():
    """Build compact facts from the browser and server evidence."""
    root = Path(__file__).resolve().parent
    summary = {
        "runs": [],
        "browser_executions": 0,
        "checks": 0,
        "passed": 0,
        "browser_anomalies": 0,
    }
    for runpath in sorted(root.glob("runs/*/run.json")):
        run = json.loads(runpath.read_text())
        row = {
            "label": run["label"],
            "passed": run["passed"],
            "python": run["metadata"]["python"].split()[0],
            "cleanup_empty": not run.get("after_cleanup")
            and not run["listeners_after_cleanup"],
            "browsers": run["browsers"],
        }
        log = gzip.decompress(runpath.with_name("server.log.gz").read_bytes()).decode()
        row["warning_lines"] = [
            line
            for line in log.splitlines()
            if re.search(
                r"(?:Warning:|Warning\b|DeprecatedSince|Traceback|Unexpected exit|Exception:|Error:)",
                line,
            )
        ]
        appdir = Path(run["cwd"])
        row["executed_source_sha256"] = {
            str(path.relative_to(appdir)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(appdir.rglob("*.py"))
            if ".web" not in path.parts and "__pycache__" not in path.parts
        }
        if not row["executed_source_sha256"]:
            provenance = json.loads((root / "fixture-provenance.json").read_text())
            row["executed_source_sha256"] = {
                name: values["executed_sha256"] for name, values in provenance.items()
            }
        for resultpath in sorted(runpath.parent.glob("*-results.json")):
            browser = json.loads(resultpath.read_text())
            summary["browser_executions"] += 1
            summary["checks"] += len(browser["checks"])
            summary["passed"] += sum(check["passed"] for check in browser["checks"])
            summary["browser_anomalies"] += len(browser["anomalies"])
        summary["runs"].append(row)
    (root / "SUMMARY.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({key: value for key, value in summary.items() if key != "runs"}))


if __name__ == "__main__":
    main()
