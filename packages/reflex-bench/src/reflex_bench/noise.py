"""The per-metric noise table of stored results: how much each series moves.

Every stored result of one run kind (``daily`` by default) adds one run to each
series it holds, a series being one metric of one series key (id, parameters,
dims, machine profile, fixture content hash, benchmark version), so runs of a
different machine or benchmark version never pool. Per series:

- ``within_cv``: the median of the runs' own coefficients of variation, the
  noise between the samples of one job;
- ``between_cv``: the robust CV of the run medians, ``1.4826 * MAD / median``,
  the noise from one job to the next;
- ``max_step``: the largest relative change between consecutive runs, in the
  order they started.

The class is provisional: ``exact`` for deterministic metrics, ``noisy`` below
``min_runs`` runs, else a threshold of ``max(3 %, 3 * between_cv)`` rounded up
to a whole percent makes the series a ``gate-candidate`` up to 10 % and
``track`` above.
"""

from __future__ import annotations

import hashlib
import itertools
import math
import operator
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from rich.text import Text

from reflex_bench.report.format import format_pct, format_value, scale_for
from reflex_bench.report.table import Cell, Line
from reflex_bench.schema import (
    Assume,
    Direction,
    ResultDoc,
    RunKind,
    SummaryDoc,
    entry_name,
)
from reflex_bench.stats import mad, median
from reflex_bench.store import SeriesKey, series_key

SCHEMA_ID = "reflex-bench-noise/1"
# Scales the MAD of normal data to its standard deviation.
MAD_TO_SIGMA = 1.4826
THRESHOLD_FLOOR = 0.03
THRESHOLD_SPREAD = 3.0
GATE_MAX = 0.10
DEFAULT_MIN_RUNS = 10

NoiseClass = Literal["exact", "noisy", "gate-candidate", "track"]
_COLUMNS = (
    "benchmark",
    "metric",
    "runs",
    "median",
    "within cv",
    "between cv",
    "max step",
    "threshold",
    "class",
    "series",
)


@dataclass(frozen=True)
class NoiseRow:
    """The noise of one metric of one series.

    Attributes:
        key: The series key.
        name: The instance name, e.g. ``lifecycle.compile.warm[app=playground]``.
        params: The instance's visible parameters.
        dims: The instance's dims.
        metric: The metric name.
        unit: The metric's unit.
        direction: Which way is better.
        assume: ``nothing`` or ``exact``.
        runs: The number of runs (result documents) in the series.
        median: The median of the run medians.
        within_cv: The median of the runs' CVs; ``None`` when no run has one.
        between_cv: The robust CV of the run medians; ``None`` with fewer than
            two runs or a zero median.
        max_step: The largest absolute relative change between consecutive
            runs; ``None`` with fewer than two runs with a nonzero median.
        threshold: The provisional practical threshold, for ``gate-candidate``
            and ``track`` series.
        cls: ``exact``, ``noisy``, ``gate-candidate`` or ``track``.
    """

    key: SeriesKey
    name: str
    params: dict[str, Any]
    dims: dict[str, Any]
    metric: str
    unit: str
    direction: Direction
    assume: Assume
    runs: int
    median: float
    within_cv: float | None
    between_cv: float | None
    max_step: float | None
    threshold: float | None
    cls: NoiseClass

    @property
    def series(self) -> str:
        """A short id of the series key, which tells apart series of one name.

        Returns:
            The first 8 hex digits of the SHA-256 of the key.
        """
        return hashlib.sha256(repr(tuple(self.key)).encode()).hexdigest()[:8]


def threshold(between_cv: float) -> float:
    """Derive the provisional practical threshold of a series.

    Args:
        between_cv: The robust CV of the run medians.

    Returns:
        ``max(3 %, 3 * between_cv)``, rounded up to a whole percent.
    """
    raw = max(THRESHOLD_FLOOR, THRESHOLD_SPREAD * between_cv)
    # Rounding first keeps 0.03 * 100 = 3.0000000000000004 at 3 %.
    return math.ceil(round(raw * 100, 9)) / 100


def result_files(paths: Iterable[Path]) -> list[Path]:
    """Expand directories into the result files they hold.

    Args:
        paths: Result files and directories.

    Returns:
        The files, and every ``*.json`` directly in each directory, sorted per
        directory.
    """
    files: list[Path] = []
    for path in paths:
        files.extend(sorted(path.glob("*.json")) if path.is_dir() else [path])
    return files


def of_kind(docs: Iterable[ResultDoc], kind: RunKind) -> list[ResultDoc]:
    """Keep the complete results of one run kind.

    Args:
        docs: The result documents.
        kind: The run kind.

    Returns:
        The documents of that kind that were not interrupted.
    """
    return [
        doc
        for doc in docs
        if doc["invocation"]["kind"] == kind and not doc.get("interrupted")
    ]


def _classify(
    assume: Assume, runs: int, between_cv: float | None, min_runs: int
) -> tuple[NoiseClass, float | None]:
    """Class a series.

    Args:
        assume: The metric's assumption.
        runs: The runs in the series.
        between_cv: The robust CV of the run medians.
        min_runs: The fewest runs a series needs for a threshold.

    Returns:
        The class and, for ``gate-candidate`` and ``track``, the threshold.
    """
    if assume == "exact":
        return "exact", None
    if runs < min_runs:
        return "noisy", None
    if between_cv is None:
        return "track", None
    limit = threshold(between_cv)
    return ("gate-candidate" if limit <= GATE_MAX else "track"), limit


def _row(
    key: SeriesKey,
    first: tuple[str, dict[str, Any], dict[str, Any], str, Direction, Assume],
    runs: list[tuple[str, SummaryDoc]],
    metric: str,
    min_runs: int,
) -> NoiseRow:
    """Summarize the runs of one series.

    Args:
        key: The series key.
        first: The name, params, dims, unit, direction and assumption.
        runs: Each run's start time and summary of arm A.
        metric: The metric name.
        min_runs: The fewest runs a series needs for a threshold.

    Returns:
        The row.
    """
    name, params, dims, unit, direction, assume = first
    runs.sort(key=operator.itemgetter(0))
    medians = [summary["median"] for _, summary in runs]
    center = median(medians)
    cvs = [summary["cv"] for _, summary in runs if summary["cv"] is not None]
    between = (
        MAD_TO_SIGMA * mad(medians, center) / abs(center)
        if len(medians) > 1 and center
        else None
    )
    steps = [abs(b / a - 1) for a, b in itertools.pairwise(medians) if a]
    cls, limit = _classify(assume, len(runs), between, min_runs)
    return NoiseRow(
        key=key,
        name=name,
        params=params,
        dims=dims,
        metric=metric,
        unit=unit,
        direction=direction,
        assume=assume,
        runs=len(runs),
        median=center,
        within_cv=median(cvs) if cvs else None,
        between_cv=between,
        max_step=max(steps) if steps else None,
        threshold=limit,
        cls=cls,
    )


def series(
    docs: Iterable[ResultDoc],
    *,
    kind: RunKind = "daily",
    min_runs: int = DEFAULT_MIN_RUNS,
) -> list[NoiseRow]:
    """Compute the noise of every series in stored results.

    Only documents of ``kind`` that were not interrupted count, and in them only
    entries that finished ``ok``, through arm A.

    Args:
        docs: The result documents.
        kind: The run kind to read.
        min_runs: The fewest runs a series needs for a threshold.

    Returns:
        One row per series and metric, sorted by instance name and metric.
    """
    groups: dict[tuple[SeriesKey, str], list[tuple[str, SummaryDoc]]] = {}
    firsts: dict[
        tuple[SeriesKey, str],
        tuple[str, dict[str, Any], dict[str, Any], str, Direction, Assume],
    ] = {}
    for doc in of_kind(docs, kind):
        started = doc["invocation"]["started_at"]
        for entry in doc["benchmarks"]:
            if entry["status"] != "ok":
                continue
            key = series_key(doc, entry)
            for metric, found in entry["metrics"].items():
                summary = found["summary"].get("A")
                if summary is None:
                    continue
                group = (key, metric)
                groups.setdefault(group, []).append((started, summary))
                firsts.setdefault(
                    group,
                    (
                        entry_name(entry),
                        entry["params"],
                        entry["dims"],
                        found["unit"],
                        found["direction"],
                        found["assume"],
                    ),
                )
    rows = [
        _row(key, firsts[key, metric], runs, metric, min_runs)
        for (key, metric), runs in groups.items()
    ]
    rows.sort(key=lambda row: (row.name, row.metric, repr(tuple(row.key))))
    return rows


def _cells(row: NoiseRow) -> list[str]:
    """Format a row for display.

    Args:
        row: The row.

    Returns:
        The cells, in the order of the table's columns, the name unquoted.
    """

    def pct(value: float | None) -> str:
        return "-" if value is None else format_pct(value, signed=False)

    return [
        row.name,
        row.metric,
        str(row.runs),
        format_value(row.median, row.unit, scale_for(row.unit, row.median)),
        pct(row.within_cv),
        pct(row.between_cv),
        pct(row.max_step),
        pct(row.threshold),
        row.cls,
        row.series,
    ]


def table_lines(rows: Sequence[NoiseRow]) -> list[Line]:
    """Lay out the noise table for :func:`reflex_bench.report.table.print_lines`.

    Args:
        rows: The rows.

    Returns:
        The header and one line per row.
    """
    lines: list[Line] = [[Text(column, style="bold") for column in _COLUMNS]]
    for row in rows:
        cells: list[Cell] = [*_cells(row)]
        lines.append(cells)
    return lines


def markdown(rows: Sequence[NoiseRow]) -> str:
    """Render the noise table as GitHub markdown.

    Args:
        rows: The rows.

    Returns:
        The table.
    """
    header = [column.capitalize() for column in _COLUMNS]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in rows:
        cells = _cells(row)
        cells[0] = f"`{cells[0]}`"
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def to_json(rows: Sequence[NoiseRow], files: Sequence[Path]) -> dict[str, Any]:
    """Build the JSON document of the noise table.

    Args:
        rows: The rows.
        files: The result files read.

    Returns:
        ``{"schema", "generated_from", "series"}``; values in SI base units,
        CVs, steps and thresholds as fractions.
    """
    return {
        "schema": SCHEMA_ID,
        "generated_from": [str(path) for path in files],
        "series": [
            {
                "name": row.name,
                "id": row.key.id,
                "params": row.params,
                "dims": row.dims,
                "profile_id": row.key.profile_id,
                "fixture_hash": row.key.fixture_hash,
                "version": row.key.version,
                "series": row.series,
                "metric": row.metric,
                "unit": row.unit,
                "direction": row.direction,
                "assume": row.assume,
                "runs": row.runs,
                "median": row.median,
                "within_cv": row.within_cv,
                "between_cv": row.between_cv,
                "max_step": row.max_step,
                "threshold": row.threshold,
                "class": row.cls,
            }
            for row in rows
        ],
    }
