"""Losslessly gzip completed browser evidence and write small review summaries."""

import collections
import gzip
import json
from pathlib import Path


def compact(directory: Path) -> None:
    """Compress completed case evidence while retaining useful review fields.

    Args:
        directory: Case directory containing a completed results.json.
    """
    source = directory / "results.json"
    if not source.exists() or list(directory.glob("*.server.log")):
        return
    raw = source.read_bytes()
    data = json.loads(raw)
    summary = {key: data[key] for key in ("name", "metadata", "servers")}
    summary["full_evidence"] = "results.json.gz"
    summary["checks"] = [
        {key: value for key, value in check.items() if key != "observed"}
        for check in data["checks"]
    ]
    summary["install_counts"] = {
        phase: {
            key: value for key, value in package.items() if key.startswith("install_")
        }
        for phase, package in data["packages"].items()
    }
    summary["browsers"] = {}
    for engine, record in data["browsers"].items():
        console = collections.Counter(
            (entry["phase"], entry["type"], entry["text"])
            for entry in record["console"]
            if entry["type"] in ("error", "warning")
        )
        summary["browsers"][engine] = {
            key: value
            for key, value in record.items()
            if key not in ("console", "websocket", "phase")
        }
        summary["browsers"][engine]["console_grouped"] = [
            {"phase": phase, "type": kind, "text": message, "count": count}
            for (phase, kind, message), count in console.items()
        ]
        summary["browsers"][engine]["console_count"] = len(record["console"])
        summary["browsers"][engine]["websocket_count"] = len(record["websocket"])
    for key in ("driver_sha256", "format_target", "harness_error"):
        if key in data:
            summary[key] = data[key]
    target = source.with_suffix(".json.gz")
    target.write_bytes(gzip.compress(raw, mtime=0))
    assert gzip.decompress(target.read_bytes()) == raw
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    source.unlink()


def retain_screenshots(directory: Path) -> None:
    """Keep representative browser screenshots within the campaign evidence budget.

    Args:
        directory: Completed case directory.
    """
    keep = {
        "base-webkit.png",
        "memo-edit-chromium.png",
        "dependency-add-webkit.png",
        "json-format-webkit.png",
        "prod-rebuild-webkit.png",
    }
    if not (directory / "results.json.gz").exists():
        return
    for screenshot in directory.glob("*.png"):
        if screenshot.name not in keep and "failure" not in screenshot.stem:
            screenshot.unlink()


if __name__ == "__main__":
    for case in (Path(__file__).parent / "results").iterdir():
        if case.is_dir():
            compact(case)
            retain_screenshots(case)
