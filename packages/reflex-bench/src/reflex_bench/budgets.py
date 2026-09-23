"""Budgets: the largest allowed values of benchmark metrics, kept in ``budgets.json``.

A budget caps one metric of one benchmark instance, in the metric's unit::

    {
      "schema": "reflex-bench-budgets/1",
      "budgets": {
        "size.export[app=playground]": {"initial_gzip": 260000, "chunks": 40}
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

from reflex_bench.report.format import DOT, format_pct
from reflex_bench.report.table import make_console
from reflex_bench.schema import (
    BenchmarkDoc,
    ResultDoc,
    SchemaError,
    entry_name,
    timed_values,
)
from reflex_bench.schema import load as load_result

SCHEMA_ID = "reflex-bench-budgets/1"
# reflex-bench is only installed from the workspace (editable), next to this file.
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "budgets.json"
_COLUMNS = ("benchmark", "metric", "value", "budget", "delta", "verdict")
_RIGHT_ALIGNED = frozenset({2, 3, 4})
_GAP = "   "

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
        BudgetsError: When the file is not JSON, has another schema, or a budget
            is not a whole number of at least 0.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"{path} is not valid JSON: {exc}"
        raise BudgetsError(msg) from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA_ID:
        schema = doc.get("schema") if isinstance(doc, dict) else None
        msg = f"{path}: schema must be {SCHEMA_ID!r}, got {schema!r}"
        raise BudgetsError(msg)
    budgets = doc.get("budgets")
    if not isinstance(budgets, dict):
        msg = f"{path}: budgets must be an object keyed by benchmark instance"
        raise BudgetsError(msg)
    problems: list[str] = []
    for name, limits in budgets.items():
        if not isinstance(limits, dict):
            problems.append(f"{name}: expected an object of metric budgets")
            continue
        problems.extend(
            f"{name}.{metric}: expected a whole number >= 0, got {budget!r}"
            for metric, budget in limits.items()
            if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0
        )
    if problems:
        msg = f"{path} is not a valid budgets file:\n  " + "\n  ".join(problems)
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
    """

    benchmark: str
    metric: str
    budget: int
    value: float | None = None
    unit: str | None = None
    error: str | None = None

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
        reason = entry["status"] + (f": {entry['error']}" if entry["error"] else "")
        return BudgetRow(name, metric, budget, error=reason)
    found = entry["metrics"].get(metric)
    if found is None:
        return BudgetRow(name, metric, budget, error="metric not in the result")
    values = [
        value for arm in found["samples"] for value in timed_values(entry, metric, arm)
    ]
    if not values:
        return BudgetRow(
            name, metric, budget, unit=found["unit"], error="no timed samples"
        )
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


def _number(value: float) -> str:
    """Format a value as budgets.json writes it.

    Args:
        value: The value.

    Returns:
        E.g. ``248193``, ready to paste.
    """
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _delta(row: BudgetRow, value: float) -> str:
    """Format how far a value is from its budget.

    Args:
        row: The checked budget.
        value: Its value.

    Returns:
        E.g. ``-11,807 B (-4.5 %)``: negative is headroom.
    """
    delta = value - row.budget
    text = f"{delta:+,.0f}" if float(delta).is_integer() else f"{delta:+g}"
    if row.unit not in {None, "1"}:
        text += f" {row.unit}"
    return text + (f" ({format_pct(delta / row.budget)})" if row.budget else "")


def format_table(rows: Sequence[BudgetRow]) -> list[Text]:
    """Lay out checked budgets as a table.

    Args:
        rows: The checked budgets.

    Returns:
        The header and one line per budget: benchmark, metric, value, budget,
        delta in the metric's unit and in percent of the budget, and verdict.
    """
    # Each row's cells and the style of its verdict.
    table: list[tuple[list[str], str]] = [(list(_COLUMNS), "")]
    for row in rows:
        if row.value is None:
            cells = ["-", _number(row.budget), "", f"error: {row.error}"]
        else:
            cells = [
                _number(row.value),
                _number(row.budget),
                _delta(row, row.value),
                "over budget" if row.exceeded else "ok",
            ]
        style = "bold red" if row.value is None or row.exceeded else ""
        table.append(([row.benchmark, row.metric, *cells], style))
    widths = [max(len(cells[i]) for cells, _ in table) for i in range(len(_COLUMNS))]
    last = len(_COLUMNS) - 1
    lines: list[Text] = []
    for index, (cells, style) in enumerate(table):
        line = Text(style="bold" if index == 0 else "")
        for i, cell in enumerate(cells):
            if i in _RIGHT_ALIGNED:
                cell = cell.rjust(widths[i])
            elif i < last:
                cell = cell.ljust(widths[i])
            line.append(f"{_GAP if i else ''}{cell}", style=style if i == last else "")
        lines.append(line)
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
    for line in format_table(rows):
        console.print(line)
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
