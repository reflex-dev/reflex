"""Verify published JSON supervision including late descendants and tracebacks."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import reflex_base
from reflex_base.utils.log import supervise_output


def main() -> None:
    """Run a failing worker through the public JSON output supervisor.

    Raises:
        RuntimeError: Intentional child failure used to exercise traceback framing.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("check", "supervise", "child"), default="check"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    assert Path(reflex_base.__file__).is_relative_to(Path(sys.prefix))
    script = str(Path(__file__).resolve())
    if args.mode == "child":
        print("QA_UNICODE_STDOUT #100% ✓", flush=True)
        print("QA_STDERR", file=sys.stderr, flush=True)
        print(
            json.dumps(
                {
                    "timestamp": "2026-10-05T00:00:00+00:00",
                    "level": "info",
                    "logger": "fixture",
                    "message": "QA_ALREADY_JSON",
                }
            ),
            flush=True,
        )
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import time; time.sleep(0.1); print('QA_LATE_DESCENDANT', flush=True)",
            ]
        )
        raise RuntimeError("QA_WORKER_TRACEBACK")
    if args.mode == "supervise":
        raise SystemExit(supervise_output([sys.executable, script, "--mode", "child"]))
    process = subprocess.run(
        [sys.executable, script, "--mode", "supervise"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    records = [
        json.loads(line)
        for stream in (process.stdout, process.stderr)
        for line in stream.splitlines()
    ]
    assert process.returncode == 1, process
    assert any(record["message"] == "QA_UNICODE_STDOUT #100% ✓" for record in records)
    assert any(record["message"] == "QA_LATE_DESCENDANT" for record in records)
    assert any(
        record.get("exception", "").endswith("RuntimeError: QA_WORKER_TRACEBACK\n")
        for record in records
    ), records
    assert any(
        record["logger"] == "fixture" and record["message"] == "QA_ALREADY_JSON"
        for record in records
    )
    result = {
        "python": sys.executable,
        "import_origin": reflex_base.__file__,
        "returncode": process.returncode,
        "records": records,
        "status": "passed",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
