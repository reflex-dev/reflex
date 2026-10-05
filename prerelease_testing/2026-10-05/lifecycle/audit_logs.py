"""Validate completed CLI JSON streams and expected lifecycle markers."""

import argparse
import json
from pathlib import Path


def main() -> None:
    """Check real application logs without hiding unexpected backend errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    summaries = []
    for filename in ("prod-normal-json.log", "dev-json.log", "prod-prefix-json.log"):
        lines = (args.root / filename).read_text().splitlines()
        wrapper_output = []
        if lines[0] == "WARN `--no-project` was provided, but no project was found":
            wrapper_output.append(lines.pop(0))
        records = [json.loads(line) for line in lines]
        messages = [record["message"] for record in records]
        for marker in (
            "QA_APP_IMPORT_STDOUT",
            "QA_APP_IMPORT_STDERR",
            "QA_EVENT_STDOUT",
            "QA_DESCENDANT_STDOUT",
            "QA_LIFESPAN_STARTED",
            "QA_LIFESPAN_CANCELLED",
        ):
            assert any(marker in message for message in messages), (filename, marker)
        errors = [record for record in records if record["level"] == "error"]
        assert errors and all(
            "QA_INTENTIONAL_EVENT_FAILURE" in record["message"] for record in errors
        ), errors
        assert not any(
            "CancelledError: lifespan_cleanup" in message for message in messages
        )
        summaries.append(
            {
                "file": filename,
                "json_records": len(records),
                "uv_wrapper_output": wrapper_output,
                "intentional_event_errors": len(errors),
                "package_install_cache_reused": any(
                    "Using cached value for _install_frontend_packages" in message
                    for message in messages
                ),
                "lifespan_cancel_marker": True,
                "unexpected_errors": [],
            }
        )
    (args.root / "log-audit.json").write_text(json.dumps(summaries, indent=2) + "\n")


if __name__ == "__main__":
    main()
