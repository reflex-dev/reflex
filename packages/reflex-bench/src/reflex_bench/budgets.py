"""Budgets: the largest allowed values of benchmark metrics, kept in ``budgets.json``.

A budget caps one metric of one benchmark instance, in the metric's unit::

    {
      "schema": "reflex-bench-budgets/1",
      "budgets": {
        "size.export[app=playground]": {"initial_gzip": 330000, "chunks": 16}
      }
    }

``reflex-bench budgets check RESULT.json`` checks a result against them: exit 2
when a metric exceeds its budget, 1 when a budget cannot be checked (the
benchmark is missing from the result, did not finish ``ok`` or lacks the
metric), else 0. A metric without a budget is tracked, not gated. A budget is
raised by editing the file in the same pull request, so the review shows it.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import click
from rich.text import Text

from reflex_bench.report.format import CROSS, DOT, format_pct
from reflex_bench.report.table import Line, make_console, print_lines
from reflex_bench.schema import (
    BenchmarkDoc,
    ResultDoc,
    SchemaError,
    entry_name,
    timed_values,
)
from reflex_bench.schema import load as load_result

SCHEMA_ID = "reflex-bench-budgets/1"
# packages/reflex-bench/budgets.json: reflex-bench is never published, so it
# always runs from its source tree.
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "budgets.json"
_COLUMNS = ("benchmark", "metric", "value", "budget", "delta", "verdict")
_RIGHT_ALIGNED = (2, 3, 4)

# Instance name to metric name to budget.
Budgets = dict[str, dict[str, int]]


class BudgetsError(ValueError):
    """A budgets file is not valid."""


def load(path: Path) -> Budgets:
    """Read and validate a budgets file.

    Args:
        path: The JSON file.

    Returns:
        Instance name to metric name to budget, in file order.

    Raises:
        BudgetsError: When the file is not JSON, has another schema, or its
            budgets are not whole numbers of at least 0 keyed by instance and
            metric.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"{path} is not valid JSON: {exc}"
        raise BudgetsError(msg) from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA_ID:
        msg = f"{path}: schema must be {SCHEMA_ID!r}"
        raise BudgetsError(msg)
    budgets = doc.get("budgets")
    if not isinstance(budgets, dict) or any(
        not isinstance(limits, dict)
        or any(type(budget) is not int or budget < 0 for budget in limits.values())
        for limits in budgets.values()
    ):
        msg = f"{path}: budgets must map instance names to objects of whole-number metric budgets >= 0"
        raise BudgetsError(msg)
    return budgets


@dataclass(frozen=True)
class BudgetRow:
    """One budget checked against a result.

    Attributes:
        benchmark: The instance name, e.g. ``size.export[app=playground]``.
        metric: The metric name.
        budget: The largest allowed value, in the metric's unit.
        value: The largest timed sample of the metric; ``None`` when it could
            not be read.
        unit: The metric's unit, when the result has the metric.
        error: Why the value could not be read.
        detail: The benchmark's own error, when it did not finish ``ok``.
    """

    benchmark: str
    metric: str
    budget: int
    value: float | None = None
    unit: str | None = None
    error: str | None = None
    detail: str | None = None

    @property
    def exceeded(self) -> bool:
        """Whether the value is over the budget.

        Returns:
            True when a value was read and exceeds the budget.
        """
        return self.value is not None and self.value > self.budget


def _check_one(
    name: str, entry: BenchmarkDoc | None, metric: str, budget: int
) -> BudgetRow:
    """Check one budget.

    Args:
        name: The instance name.
        entry: The instance's entry in the result, if any.
        metric: The metric name.
        budget: The budget.

    Returns:
        The row, with the value or the reason it could not be read.
    """
    if entry is None:
        return BudgetRow(name, metric, budget, error="not in the result")
    if entry["status"] != "ok":
        return BudgetRow(
            name, metric, budget, error=entry["status"], detail=entry["error"]
        )
    found = entry["metrics"].get(metric)
    if found is None:
        return BudgetRow(name, metric, budget, error="metric not in the result")
    # An ok entry has at least one timed sample in every arm.
    values = [
        value for arm in found["samples"] for value in timed_values(entry, metric, arm)
    ]
    return BudgetRow(name, metric, budget, value=max(values), unit=found["unit"])


def check(doc: ResultDoc, budgets: Budgets) -> list[BudgetRow]:
    """Check a result against budgets.

    Args:
        doc: A result, normally of ``reflex-bench run``.
        budgets: The budgets, as :func:`load` returns them.

    Returns:
        One row per budget, in the budgets' order. The value is the largest timed
        sample of the metric; exact metrics have one.
    """
    entries = {entry_name(entry): entry for entry in doc["benchmarks"]}
    return [
        _check_one(name, entries.get(name), metric, budget)
        for name, limits in budgets.items()
        for metric, budget in limits.items()
    ]


def _number(value: float, signed: bool = False) -> str:
    """Format a value or a delta, keeping the fraction of a fractional one.

    Args:
        value: The value.
        signed: Whether to write the sign and thousands separators, as a delta.

    Returns:
        E.g. ``248193`` (a whole value, as budgets.json writes it) or
        ``+1,024.500``.
    """
    digits = "0" if float(value).is_integer() else "3"
    return format(value, f"{'+,' if signed else ''}.{digits}f")


def _delta(row: BudgetRow, value: float) -> str:
    """Format how far a value is from its budget.

    Args:
        row: The checked budget.
        value: Its value.

    Returns:
        E.g. ``-11,807 B (-4.5 %)``: negative is headroom.
    """
    delta = value - row.budget
    text = _number(delta, signed=True)
    if row.unit not in {None, "1"}:
        text += f" {row.unit}"
    return text + (f" ({format_pct(delta / row.budget)})" if row.budget else "")


def table_lines(rows: Sequence[BudgetRow]) -> list[Line]:
    """Lay out checked budgets for :func:`print_lines`.

    Args:
        rows: The checked budgets.

    Returns:
        The header and one row per budget: benchmark, metric, value (a whole
        value as budgets.json writes it, ready to paste), budget, delta in the
        metric's unit and in percent of the budget, and verdict. A benchmark
        that did not finish ``ok`` gets its error printed once, after its rows.
    """
    lines: list[Line] = [[Text(column, style="bold") for column in _COLUMNS]]
    detailed: set[str] = set()
    for row in rows:
        if row.value is None:
            cells = ["-", str(row.budget), "", f"error: {row.error}"]
        else:
            cells = [
                _number(row.value),
                str(row.budget),
                _delta(row, row.value),
                "over budget" if row.exceeded else "ok",
            ]
        style = "bold red" if row.value is None or row.exceeded else ""
        lines.append([row.benchmark, row.metric, *cells[:-1], Text(cells[-1], style)])
        if row.detail and row.benchmark not in detailed:
            detailed.add(row.benchmark)
            lines.append(
                Text(f"{CROSS} {row.benchmark}: {row.error}: {row.detail}", style)
            )
    return lines


@click.group("budgets")
def budgets_command() -> None:
    """Check results against the metric budgets of budgets.json."""


@budgets_command.command("check")
@click.argument("result", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--budgets",
    "budgets_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=DEFAULT_PATH,
    show_default="packages/reflex-bench/budgets.json",
    help="The budgets file.",
)
def check_command(result: Path, budgets_path: Path) -> int:
    """Check RESULT against the budgets; exit 2 when a metric exceeds its budget.

    Exit 1 when a budgeted benchmark is missing from RESULT, did not finish ok
    or lacks a budgeted metric. Metrics without a budget are not checked.

    Args:
        result: The result JSON file.
        budgets_path: The budgets file.

    Returns:
        The exit code.

    Raises:
        UsageError: When a file is not valid.
    """
    # cli imports this module to register the group, so import it late.
    from reflex_bench.cli import EXIT_ERROR, EXIT_OK, EXIT_REGRESSION, _relative, in_ci

    try:
        rows = check(load_result(result), load(budgets_path))
    except (SchemaError, BudgetsError) as exc:
        raise click.UsageError(str(exc)) from exc
    console = make_console(plain=in_ci())
    print_lines(console, table_lines(rows), right=_RIGHT_ALIGNED)
    over = sum(row.exceeded for row in rows)
    unchecked = sum(row.value is None for row in rows)
    console.print()
    console.print(
        Text(
            f"{len(rows) - over - unchecked} within budget {DOT} {over} over budget"
            f" {DOT} {unchecked} not checked"
        )
    )
    if over:
        console.print(
            Text(
                "to accept a new value, raise its budget in"
                f" {_relative(budgets_path)} in the same pull request"
            )
        )
    if unchecked:
        return EXIT_ERROR
    return EXIT_REGRESSION if over else EXIT_OK
