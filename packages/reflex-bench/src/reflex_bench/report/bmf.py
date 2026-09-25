"""Export to Bencher Metric Format (https://bencher.dev/docs/reference/bencher-metric-format/).

Each instance becomes a benchmark named ``id[params]`` and each metric a
measure holding the median and the bounds of its confidence interval.
"""

from __future__ import annotations

from typing import Any

from reflex_bench.schema import ResultDoc, entry_name


def to_bmf(doc: ResultDoc) -> dict[str, dict[str, dict[str, Any]]]:
    """Convert a result's summaries to Bencher Metric Format.

    Instances without statistics (failed, smoke runs) are left out; exact metrics
    and metrics without a CI carry only a value. An ``ab`` result exports its
    head, arm B.

    Args:
        doc: The result document.

    Returns:
        ``{name: {metric: {"value", "lower_value", "upper_value"}}}``.
    """
    arm = "B" if "B" in doc["subjects"] else "A"
    exported: dict[str, dict[str, dict[str, Any]]] = {}
    for entry in doc["benchmarks"]:
        measures: dict[str, dict[str, Any]] = {}
        for name, metric in entry["metrics"].items():
            summary = metric["summary"].get(arm)
            if summary is None:
                continue
            measure: dict[str, Any] = {"value": summary["median"]}
            if summary["ci"] is not None and metric["assume"] != "exact":
                measure["lower_value"], measure["upper_value"] = summary["ci"]
            measures[name] = measure
        if measures:
            exported[entry_name(entry)] = measures
    return exported
