"""Derive a compact report from the retained raw browser evidence."""

import gzip
import json
from pathlib import Path


def main():
    """Summarize recorded assertions, anomalies, churn and cleanup."""
    root = Path(__file__).resolve().parent
    summary = {
        "cases": {},
        "checkpoints": 0,
        "pass": 0,
        "fail": 0,
        "driver_errors": 0,
        "browser_executions": 0,
        "background_visible_anomalies": [],
        "churn": {},
    }
    for path in sorted((root / "runs").glob("*/run.json")):
        run = json.loads(path.read_text())
        case = {
            "args": run["args"],
            "browsers": {},
            "cleanup_empty": all(
                not (server["after_cleanup"] or server["listeners_after_cleanup"])
                for server in run["servers"]
            ),
            "runner_error": run.get("runner_error"),
            "servers": len(run["servers"]),
        }
        for engine in run["browsers"]:
            raw = path.with_name(engine + "-results.json.gz")
            data = json.loads(gzip.decompress(raw.read_bytes()))
            passed = sum(row["passed"] for row in data["checks"])
            summary["checkpoints"] += len(data["checks"])
            summary["pass"] += passed
            summary["fail"] += len(data["checks"]) - passed
            summary["driver_errors"] += bool(data.get("driver_error"))
            summary["browser_executions"] += 1
            case["browsers"][engine] = {
                "checkpoints": len(data["checks"]),
                "pass": passed,
                "failed": [row for row in data["checks"] if not row["passed"]],
                "driver_error": data.get("driver_error"),
                "browser_anomalies": len(data["anomalies"]),
                "browser_version": data["browser_version"],
            }
            if "after_job_visible" in data:
                expected = {"root": 10, "child": 0, "a": 0, "b": 0}
                if data["after_job_visible"] != expected:
                    summary["background_visible_anomalies"].append({
                        "case": run["label"],
                        "engine": engine,
                        "expected_server_values": expected,
                        "actual_dom": data["after_job_visible"],
                        "server_check": next(
                            row
                            for row in data["checks"]
                            if row["name"] == "expired-background-reacquire-server"
                        ),
                    })
            if "contexts" in data:
                summary["churn"][run["label"]] = {
                    key: data[key]
                    for key in (
                        "before",
                        "peak",
                        "after_load",
                        "after_expiry",
                        "load_started",
                        "load_finished",
                    )
                }
                summary["churn"][run["label"]].update({
                    "contexts": len(data["contexts"]),
                    "successful_contexts": sum(
                        row["passed"] for row in data["contexts"]
                    ),
                    "warmup": data["warmup"]["passed"],
                })
        case["log_observations"] = []
        for log in sorted(path.parent.glob("server-*.log.gz")):
            text = gzip.decompress(log.read_bytes()).decode(errors="replace")
            case["log_observations"].append({
                "file": log.name,
                "cancelled_lifespan_tracebacks": text.count(
                    "asyncio.exceptions.CancelledError: lifespan_cleanup"
                ),
                "unexpected_worker_exit": text.count(
                    "[ERROR] Unexpected exit from worker-1"
                ),
                "traceback_headers": text.count("Traceback (most recent call last)"),
                "deprecated_debounce_warnings": text.count(
                    "REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS has been"
                ),
            })
        summary["cases"][run["label"]] = case
    durations = json.loads((root / "durations/results.json").read_text())
    summary["duration_probes"] = {
        "total": len(durations),
        "pass": sum(row["passed"] for row in durations),
    }
    (root / "SUMMARY.json").write_text(json.dumps(summary, indent=2))
    print(
        json.dumps({
            key: value
            for key, value in summary.items()
            if key not in {"cases", "churn", "background_visible_anomalies"}
        })
    )


if __name__ == "__main__":
    main()
