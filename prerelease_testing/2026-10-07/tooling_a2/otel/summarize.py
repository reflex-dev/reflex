"""Derive compact telemetry findings from retained exports and browser results."""

import collections
import gzip
import json
import re
import urllib.parse
from pathlib import Path

from traces import read_spans


def main():
    """Summarize complete runs and independently verify full-payload omissions."""
    root = Path(__file__).resolve().parent
    summary = {"runs": [], "browser_checks": 0, "browser_passed": 0, "executions": 0}
    for runpath in sorted(root.glob("runs/*/run.json")):
        run = json.loads(runpath.read_text())
        folder = runpath.parent
        row = {
            "label": run["label"],
            "passed": run["passed"],
            "runner_error": run.get("runner_error"),
            "cleanup_empty": not run["listeners_after_cleanup"]
            and all(not process["after_cleanup"] for process in run["processes"]),
            "browsers": {},
            "compile_spans": run["compile_spans"],
        }
        collector = folder / "collector.jsonl.gz"
        if collector.exists():
            raw = gzip.decompress(collector.read_bytes()).decode()
            requests = [json.loads(line) for line in raw.splitlines()]
            spans = read_spans(collector)
            row["requests"] = len(requests)
            row["content_types"] = dict(
                collections.Counter(request["content_type"] for request in requests)
            )
            row["spans"] = len(spans)
            row["services"] = dict(
                collections.Counter(span["service"] for span in spans)
            )
            row["kinds"] = dict(collections.Counter(span["kind"] for span in spans))
            row["span_names"] = dict(
                collections.Counter(span["name"] for span in spans)
            )
            compile_roots = {
                span["span_id"] for span in spans if span["name"] == "reflex.compile"
            }
            compile_children = [
                span for span in spans if span["name"].startswith("reflex.compile.")
            ]
            row["compile_child_links_valid"] = (
                bool(compile_roots)
                and bool(compile_children)
                and all(span["parent_id"] in compile_roots for span in compile_children)
            )
            row["valid_trace_and_span_ids"] = all(
                re.fullmatch("[0-9a-f]{32}", span["trace_id"])
                and re.fullmatch("[0-9a-f]{16}", span["span_id"])
                for span in spans
            )
            row["browser_public_header_present"] = all(
                request["public_header"] == "public-fixture"
                for request in requests
                if request["origin"]
            )
            row["asgi_server_spans"] = [
                span for span in spans if span["kind"] == "SERVER"
            ]
            row["payload_markers_absent_from_full_requests"] = (
                "QA_PAYLOAD_MUST_NOT_EXPORT_" not in raw
            )
        else:
            raw = ""
        for path in sorted(folder.glob("*-results.json")):
            browser = json.loads(path.read_text())
            engine = browser["engine"]
            frames = json.loads(
                gzip.decompress((folder / f"{engine}-frames.json.gz").read_bytes())
            )
            tokens = {
                token
                for frame in frames
                for token in urllib.parse.parse_qs(
                    urllib.parse.urlparse(frame["url"]).query
                ).get("token", [])
            }
            before = json.loads(
                gzip.decompress(
                    (folder / f"{engine}-spans_before_outage.json.gz").read_bytes()
                )
            )
            counts = {
                name: sum(
                    span["service"] == "qa-backend"
                    and span["name"].endswith("." + name)
                    for span in before
                )
                for name in ("add", "audit", "replenish", "fail")
            }
            expected = {"add": 3, "audit": 3, "replenish": 1, "fail": 1}
            item = {
                "passed": browser["passed"],
                "checks": len(browser["checks"]),
                "failed": [
                    check["name"] for check in browser["checks"] if not check["passed"]
                ],
                "anomalies": len(browser["anomalies"]),
                "anomaly_types": dict(
                    collections.Counter(
                        message["type"] for message in browser["anomalies"]
                    )
                ),
                "pre_outage_backend_event_counts": counts,
                "pre_outage_expected_counts": expected,
                "one_span_per_handler_before_outage": counts == expected,
                "tokens_captured": len(tokens),
                "raw_tokens_absent_from_full_requests": bool(tokens)
                and all(token not in raw for token in tokens),
                "before_reload_recovery_checked": any(
                    check["name"] == "restored-trace-link-before-reload"
                    for check in browser["checks"]
                ),
                "outage_started": browser.get("outage_started"),
                "collector_restored": browser.get("collector_restored"),
            }
            row["browsers"][engine] = item
            summary["executions"] += 1
            summary["browser_checks"] += len(browser["checks"])
            summary["browser_passed"] += sum(
                check["passed"] for check in browser["checks"]
            )
        logs = "\n".join(
            gzip.decompress(path.read_bytes()).decode()
            for path in folder.glob("server-*.log.gz")
        )
        row["server_diagnostics"] = [
            line
            for line in logs.splitlines()
            if re.search(
                r"Warning|Traceback|Error:|ERROR|Failed to export|Attempting to instrument|Overriding of current",
                line,
            )
        ]
        summary["runs"].append(row)
    (root / "SUMMARY.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({key: value for key, value in summary.items() if key != "runs"}))


if __name__ == "__main__":
    main()
