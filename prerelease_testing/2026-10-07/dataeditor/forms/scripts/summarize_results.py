"""Summarize saved browser assertions without trusting historical exit codes."""

import argparse
import json
from pathlib import Path


def summarize(root: Path) -> dict:
    """Read saved runs and count assertions and captured errors.

    Args:
        root: Directory containing version/mode run directories.

    Returns:
        Per-run results plus aggregate assertion counts.
    """
    result = {"runs": {}, "assertions": 0, "passed": 0, "failed": 0}
    for path in sorted(root.glob("*/*/results.json")):
        data = json.loads(path.read_text())
        groups = {}
        for name, group in data["groups"].items():
            checks = group["checks"]
            failures = [check["name"] for check in checks if not check["ok"]]
            groups[name] = {
                "assertions": len(checks),
                "failed": failures,
                "pageerrors": len(group["pageerrors"]),
                "failed_requests": len(group["failed_requests"]),
                "http_errors": group["http_errors"],
                "warnings": [
                    message["text"]
                    for message in group["console"]
                    if message["type"] in ("warning", "error")
                ],
            }
            result["assertions"] += len(checks)
            result["failed"] += len(failures)
            result["passed"] += len(checks) - len(failures)
        result["runs"][str(path.relative_to(root))] = {
            "browser": data["browser"],
            "groups": groups,
        }
    return result


def main():
    """Print an assertion-based JSON summary of archived results."""
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    print(json.dumps(summarize(parser.parse_args().root), indent=2))


if __name__ == "__main__":
    main()
