"""Summarize the independent expiry runs without starting an app or browser."""

import gzip
import json
import re
from pathlib import Path


def received_deltas(case: dict) -> list[dict]:
    """Decode retained Socket.IO state deltas with their observation phase.

    Args:
        case: One browser case from the raw results.

    Returns:
        Received event deltas and their phase labels.
    """
    deltas = []
    for frame in case["websocket"]:
        if frame["kind"] != "framereceived" or not frame["frame"].startswith(
            "42/_event,"
        ):
            continue
        event = json.loads(frame["frame"].split(",", 1)[1])
        if event[0] == "event" and "delta" in event[1]:
            deltas.append({"phase": frame["phase"], "delta": event[1]["delta"]})
    return deltas


def audit_run(path: Path) -> dict:
    """Audit every browser channel and the server's diagnostic lines.

    Args:
        path: Compressed raw results for one server run.

    Returns:
        Compact evidence, retaining the exact background completion delta.
    """
    result = json.loads(gzip.decompress(path.read_bytes()))
    log = gzip.decompress((path.parent / "server.log.gz").read_bytes()).decode()
    lines = re.sub(r"\x1b\[[0-9;]*m", "", log).splitlines()
    origins = [
        json.loads(line.split("VERIFY_ORIGIN ", 1)[1])
        for line in lines
        if line.startswith("VERIFY_ORIGIN ")
    ]
    cases = []
    for case in result["cases"]:
        deltas = received_deltas(case)
        completion = [
            event["delta"]
            for event in deltas
            if event["phase"] == "background-wait"
            and any(
                fields.get("status_rx_state_") == "complete"
                for fields in event["delta"].values()
            )
        ]
        zeroed_children = [
            event["phase"]
            for event in deltas
            if sum(
                fields.get("count_rx_state_") == 0 for fields in event["delta"].values()
            )
            == 3
        ]
        cases.append(
            {
                "engine": case["engine"],
                "browser_version": case["browser_version"],
                "kind": case["kind"],
                "expiry_receipt_reload_checks_pass": case.get(
                    "expiry_and_persistence_checks_pass", False
                ),
                "visible_before_inspection": case.get("visible_before_inspection"),
                "backend_receipt": case.get("public_server_receipt"),
                "visible_backend_mismatch": case.get("visible_backend_mismatch"),
                "completion_deltas": completion,
                "zeroed_child_delta_phases": zeroed_children,
                "console_errors": sum(
                    item["type"] == "error" for item in case["console"]
                ),
                "console_warnings": [
                    item["text"]
                    for item in case["console"]
                    if item["type"] == "warning"
                ],
                "pageerror_count": len(case["pageerrors"]),
                "http_error_count": len(case["http_errors"]),
                "failed_request_count": len(case["failed_requests"]),
                "websocket_frames": len(case["websocket"]),
                "capture_limit_reached": len(case["console"]) >= 100
                or len(case["websocket"]) >= 300
                or len(case["failed_requests"]) >= 60,
                "error": case.get("error"),
            }
        )
    return {
        "name": result["name"],
        "raw_evidence": str(path.relative_to(Path(__file__).parent)),
        "published_imports": origins,
        "ttl_seconds": result["ttl_seconds"],
        "external_job_seconds": result["external_job_seconds"],
        "cases": cases,
        "server_diagnostic_lines": [
            {"line": number, "text": line}
            for number, line in enumerate(lines, 1)
            if re.search(
                r"^Warning:|^DeprecationWarning:|^\[ERROR\]|^Traceback|Debug: (error:|warn:)",
                line,
            )
        ],
        "harness_error": result.get("harness_error"),
        "cleanup_remaining": result["cleanup"]["remaining"],
        "listeners_after_cleanup": result["listeners_after_cleanup"],
    }


def main() -> None:
    """Write a structured summary from the four primary retained runs."""
    root = Path(__file__).parent
    names = [
        f"{env}-{manager}-dev-1"
        for manager in ("memory", "disk")
        for env in ("stable", "alpha2")
    ]
    runs = [audit_run(root / "results" / name / "results.json.gz") for name in names]
    cases = [case for run in runs for case in run["cases"]]
    background = [case for case in cases if case["kind"] == "background"]
    idle = [case for case in cases if case["kind"] == "idle"]
    expected_mismatch = {
        "section": {"visible": 11, "backend": 0},
        "left": {"visible": 13, "backend": 0},
        "right": {"visible": 17, "backend": 0},
    }
    reproduced = len(background) == 8 and all(
        case["visible_backend_mismatch"] == expected_mismatch for case in background
    )
    controls_pass = len(idle) == 8 and all(
        case["expiry_receipt_reload_checks_pass"]
        and not case["visible_backend_mismatch"]
        for case in idle
    )
    report = {
        "finding": "Background completion after configured session expiry leaves untouched child and component counters stale until a foreground event refreshes them.",
        "classification": "pre-existing; reproduced in 0.9.12 and 0.10.0a2"
        if reproduced and controls_pass
        else "review required",
        "severity_assessment": "low: narrow UI consistency trigger; no demonstrated downstream corruption or cross-user leakage",
        "scope": "macOS Chromium/WebKit, dev mode, memory/disk; shortened TTL simulates external work exceeding the configured session lifetime",
        "timing_claim": None,
        "background_cases": len(background),
        "background_finding_reproduced": reproduced,
        "idle_control_cases": len(idle),
        "idle_controls_pass": controls_pass,
        "receipt_reload_checks_pass": sum(
            case["expiry_receipt_reload_checks_pass"] for case in cases
        ),
        "diagnostic_error_totals": {
            key: sum(case[key] for case in cases)
            for key in (
                "console_errors",
                "pageerror_count",
                "http_error_count",
                "failed_request_count",
            )
        },
        "browser_warning_count": sum(len(case["console_warnings"]) for case in cases),
        "owned_cleanup_pass": all(
            not run["cleanup_remaining"] and not run["listeners_after_cleanup"]
            for run in runs
        ),
        "server_diagnostic_interpretation": "Shared startup Sitemap/Radix configuration and React peer warnings. Dev exit143 in all runs and worker-exit messages in stable-memory and alpha2-disk occur during deliberate process-group SIGTERM; full logs retained.",
        "runs": runs,
    }
    (root / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "runs"}, indent=2
        )
    )


if __name__ == "__main__":
    main()
