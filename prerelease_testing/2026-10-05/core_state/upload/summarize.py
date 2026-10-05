"""Summarize saved real-browser evidence without framework imports."""

import json
import sys
from pathlib import Path


def main() -> None:
    """Validate complete scenario results and emit their compact evidence summary."""
    root = Path(sys.argv[1])
    summary = {}
    for mode in ("dev", "prod"):
        data = json.loads((root / mode / "browser-results.json").read_text())
        assert len(data["scenarios"]) == 7
        assert all(scenario["status"] == "pass" for scenario in data["scenarios"])
        assert not data["page_errors"]
        summary[mode] = {
            "browser_version": data["browser_version"],
            "scenarios": [
                {
                    key: scenario[key]
                    for key in (
                        "name",
                        "status",
                        "duration_seconds",
                        "timing_separation_seconds",
                        "late_delta_separation_seconds",
                        "lineage_assertions",
                    )
                    if key in scenario
                }
                for scenario in data["scenarios"]
            ],
            "visible_assertions": sum(
                len(scenario["assertions"]) for scenario in data["scenarios"]
            ),
            "page_errors": data["page_errors"],
            "console_errors": [
                message for message in data["console"] if message["type"] == "error"
            ],
            "failed_requests": [
                request for request in data["requests"] if request["phase"] == "failed"
            ],
        }
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
