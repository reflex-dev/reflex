"""Compare two result documents metric by metric.

Entries are paired by id, params and dims, and compared only when their full
series keys match (machine profile, fixture and benchmark version too). Each
metric gets a Mann-Whitney U test and a bootstrap CI of the change; Holm's
correction runs across all tested metrics of the comparison; exact metrics
compare values directly. An entry that fails or times out in head without
failing in base is a regression whatever its series key; statuses are seen from
the compared arms, so the two arms of one ``ab`` document compare too. The
verdicts are written into the head document, so an annotated document is
self-describing for ``show`` and ``export``.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import NamedTuple

from reflex_bench import stats
from reflex_bench.scheduler import CORRECTION, derive_seed
from reflex_bench.schema import (
    BenchmarkDoc,
    ComparedToDoc,
    ComparisonDoc,
    ComparisonSideDoc,
    FailedInHeadDoc,
    MetricDoc,
    NotComparableDoc,
    ResultDoc,
    Status,
    Verdict,
    entry_name,
    timed_values,
)
from reflex_bench.store import entry_key, series_key

_FAMILY_ORDER = ("time", "bytes", "rate", "count")
_FAILED = frozenset({"failed", "timeout"})


class Row(NamedTuple):
    """One compared metric of an annotated document."""

    name: str
    metric: str
    doc: MetricDoc
    comparison: ComparisonDoc


class _Pending(NamedTuple):
    """A metric comparison waiting for its multiple-testing correction."""

    metric: MetricDoc
    raw: stats.SampleComparison
    base: ComparisonSideDoc
    head: ComparisonSideDoc


def _arm_status(entry: BenchmarkDoc, arm: str) -> Status:
    """Tell an entry's status as one of its arms saw it.

    Args:
        entry: The benchmark entry.
        arm: The arm.

    Returns:
        ``ok`` for an arm that is not in the ``failed_arms`` of a failed entry
        (its samples just stopped early), else the entry's status.
    """
    failed_arms = entry.get("failed_arms")
    if (
        entry["status"] in _FAILED
        and failed_arms is not None
        and arm not in failed_arms
    ):
        return "ok"
    return entry["status"]


def _side(
    invocation_id: str, arm: str, values: list[float], confidence: float
) -> ComparisonSideDoc:
    """Summarize one side of a comparison.

    Args:
        invocation_id: The invocation the samples come from.
        arm: Their arm.
        values: The timed samples.
        confidence: The confidence level of the median CI.

    Returns:
        The side's sample count, median and median CI.
    """
    ci = stats.median_ci(values, confidence)
    return {
        "invocation_id": invocation_id,
        "arm": arm,
        "n": len(values),
        "median": stats.median(values),
        "ci": None if ci is None else list(ci),
    }


def compare(
    base: ResultDoc,
    head: ResultDoc,
    *,
    threshold: float,
    alpha: float,
    confidence: float = 0.95,
    resamples: int = 10_000,
    seed: int = 0,
    force: bool = False,
    base_label: str = "base",
    head_label: str = "head",
    base_arm: str = "A",
    head_arm: str = "A",
) -> ComparedToDoc:
    """Compare every metric of ``head`` with ``base`` and annotate ``head``.

    Args:
        base: The baseline document.
        head: The document to judge; its ``comparison`` blocks and
            ``compared_to`` are replaced.
        threshold: The practical threshold, as a fraction.
        alpha: The significance level.
        confidence: The confidence level of all intervals.
        resamples: Bootstrap resamples per metric.
        seed: The bootstrap seed; each metric derives its own stream from it.
        force: Compare entries even when their series keys differ.
        base_label: How to name the baseline in reports.
        head_label: How to name the head in reports.
        base_arm: The arm of ``base`` to compare.
        head_arm: The arm of ``head`` to compare.

    Returns:
        The ``compared_to`` block, also stored in ``head``.
    """
    for entry in head["benchmarks"]:
        for metric in entry["metrics"].values():
            metric["comparison"] = None
    base_entries = {entry_key(entry): entry for entry in base["benchmarks"]}
    head_keys = {entry_key(entry) for entry in head["benchmarks"]}
    base_id = base["invocation"]["id"]
    head_id = head["invocation"]["id"]
    not_comparable: list[NotComparableDoc] = []
    failed_in_head: list[FailedInHeadDoc] = []
    pending: list[_Pending] = []
    for head_entry in head["benchmarks"]:
        base_entry = base_entries.get(entry_key(head_entry))
        name = entry_name(head_entry)
        head_status = _arm_status(head_entry, head_arm)
        base_status = None if base_entry is None else _arm_status(base_entry, base_arm)
        if head_status in _FAILED and base_status not in _FAILED:
            failed_in_head.append({
                "id": name,
                "status": head_status,
                "base_status": base_status,
                "error": head_entry["error"],
            })
            continue
        if base_entry is None:
            continue
        reasons = (
            []
            if force
            else series_key(base, base_entry).differences(series_key(head, head_entry))
        )
        reasons.extend(
            f"{side} status is {status}"
            for side, status in (("base", base_status), ("head", head_status))
            if status != "ok"
        )
        reasons.extend(
            f"metric {metric_name!r} is missing in {side}"
            for side, present, other in (
                ("base", base_entry, head_entry),
                ("head", head_entry, base_entry),
            )
            for metric_name in sorted(
                other["metrics"].keys() - present["metrics"].keys()
            )
        )
        samples = (
            {}
            if reasons
            else {
                metric_name: (
                    timed_values(base_entry, metric_name, base_arm),
                    timed_values(head_entry, metric_name, head_arm),
                )
                for metric_name in head_entry["metrics"]
            }
        )
        reasons.extend(
            f"metric {metric_name!r} has no timed samples"
            for metric_name, (a, b) in samples.items()
            if not a or not b
        )
        if reasons:
            not_comparable.append({"id": name, "reasons": reasons})
            continue
        for metric_name, (a, b) in samples.items():
            metric = head_entry["metrics"][metric_name]
            raw = stats.compare_samples(
                a,
                b,
                exact=metric["assume"] == "exact",
                confidence=confidence,
                resamples=resamples,
                seed=derive_seed(seed, name, metric_name),
            )
            pending.append(
                _Pending(
                    metric,
                    raw,
                    _side(base_id, base_arm, a, confidence),
                    _side(head_id, head_arm, b, confidence),
                )
            )
    tested = [
        (index, item.raw.p)
        for index, item in enumerate(pending)
        if item.raw.p is not None
    ]
    adjusted = dict(
        zip(
            (index for index, _ in tested),
            stats.holm([p for _, p in tested]),
            strict=True,
        )
    )
    for index, item in enumerate(pending):
        p_adj = adjusted.get(index)
        exact = item.metric["assume"] == "exact"
        # A relative threshold does not apply to an absolute change.
        applied = threshold if item.raw.mode == "ratio" else 0.0
        verdict = stats.verdict(
            item.raw.effect,
            item.raw.ci,
            p_adj,
            direction=item.metric["direction"],
            threshold=applied,
            alpha=alpha,
            exact=exact,
            min_p=item.raw.min_p,
        )
        item.metric["comparison"] = {
            "base": item.base,
            "head": item.head,
            "mode": item.raw.mode,
            "ratio": item.raw.effect
            if item.raw.mode == "ratio" and math.isfinite(item.raw.effect)
            else None,
            "ci": None if item.raw.ci is None else list(item.raw.ci),
            "p": item.raw.p,
            "p_adj": p_adj,
            "test": item.raw.test,
            "threshold_rel": threshold,
            "verdict": verdict,
            "runs_needed": stats.runs_needed(
                min(item.base["n"], item.head["n"]),
                item.raw.effect,
                item.raw.ci,
                applied,
                alpha=alpha,
                confidence=confidence,
            )
            if verdict == "inconclusive"
            else None,
        }
    compared_to: ComparedToDoc = {
        "base_label": base_label,
        "head_label": head_label,
        "invocation_id": base_id,
        "profile_id": base["machine"]["profile_id"],
        "alpha": alpha,
        "threshold_rel": threshold,
        "confidence": confidence,
        "correction": CORRECTION,
        "bootstrap_resamples": resamples,
        "seed": seed,
        "family_size": len(tested),
        "forced": force,
        "only_in_base": [
            entry_name(entry)
            for key, entry in base_entries.items()
            if key not in head_keys
        ],
        "only_in_head": [
            entry_name(entry)
            for entry in head["benchmarks"]
            if entry_key(entry) not in base_entries
        ],
        "not_comparable": not_comparable,
        "failed_in_head": failed_in_head,
    }
    head["compared_to"] = compared_to
    return compared_to


def rows(doc: ResultDoc) -> list[Row]:
    """List the compared metrics of an annotated document.

    Args:
        doc: The head document after :func:`compare`.

    Returns:
        One row per metric with a comparison, in document order.
    """
    return [
        Row(entry_name(entry), name, metric, metric["comparison"])
        for entry in doc["benchmarks"]
        for name, metric in entry["metrics"].items()
        if metric["comparison"] is not None
    ]


def failed_in_head(doc: ResultDoc) -> list[FailedInHeadDoc]:
    """List the entries of an annotated document that started failing in head.

    Args:
        doc: The head document after :func:`compare`.

    Returns:
        The entries that failed or timed out in head without failing in base.
    """
    compared_to = doc.get("compared_to")
    return [] if compared_to is None else compared_to.get("failed_in_head", [])


def verdict_counts(doc: ResultDoc) -> Counter[Verdict]:
    """Count the verdicts of an annotated document.

    Args:
        doc: The head document after :func:`compare`.

    Returns:
        How many metrics got each verdict.
    """
    return Counter(row.comparison["verdict"] for row in rows(doc))


def geomeans(doc: ResultDoc) -> dict[str, float]:
    """Summarize the changes of an annotated document per unit family.

    Args:
        doc: The head document after :func:`compare`.

    Returns:
        The geometric mean change of each unit family, time first, then bytes,
        rates, counts and other units in order of appearance.
    """
    changes: dict[str, list[float]] = {family: [] for family in _FAMILY_ORDER}
    for row in rows(doc):
        if row.comparison["ratio"] is not None:
            changes.setdefault(stats.unit_family(row.doc["unit"]), []).append(
                row.comparison["ratio"]
            )
    return {
        family: mean
        for family, ratios in changes.items()
        if (mean := stats.geomean_ratios(ratios)) is not None
    }
