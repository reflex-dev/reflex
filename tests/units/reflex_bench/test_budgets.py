"""Tests for reflex_bench.budgets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from reflex_bench import budgets, cli
from reflex_bench.registry import Metric, discover
from reflex_bench.scheduler import plan
from reflex_bench.schema import ResultDoc, dump

from .factories import make_doc, make_entry

SIZE = Metric(unit="B", direction="lower", assume="exact")
COUNT = Metric(unit="1", direction="lower", assume="exact")
NAME = "size.export[app=playground]"
BUDGETS = {NAME: {"initial_gzip": 260_000, "chunks": 40}}


def _doc(status: str = "ok", error: str | None = None, warmup: int = 0) -> ResultDoc:
    entry = make_entry(
        "size.export",
        {
            "initial_gzip": (SIZE, [250_000]),
            "total_gzip": (SIZE, [900_000]),
            "chunks": (COUNT, [30]),
        },
        params={"app": "playground"},
        warmup=warmup,
        status=status,
        error=error,
    )
    return make_doc([entry])


def _files(
    tmp_path: Path, doc: ResultDoc, limits: dict[str, dict[str, int]]
) -> tuple[Path, Path]:
    result = tmp_path / "result.json"
    dump(doc, result)
    path = tmp_path / "budgets.json"
    path.write_text(json.dumps({"schema": budgets.SCHEMA_ID, "budgets": limits}))
    return result, path


def _check(tmp_path: Path, doc: ResultDoc, limits: dict[str, dict[str, int]]) -> Result:
    result, path = _files(tmp_path, doc, limits)
    return CliRunner().invoke(
        cli.cli, ["budgets", "check", str(result), "--budgets", str(path)]
    )


def test_within_budget_exits_0_and_shows_the_headroom(tmp_path: Path):
    result = _check(tmp_path, _doc(), BUDGETS)
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0].split() == [
        "benchmark",
        "metric",
        "value",
        "budget",
        "delta",
        "verdict",
    ]
    assert lines[1].split() == [
        NAME,
        "initial_gzip",
        "250000",
        "260000",
        "-10,000",
        "B",
        "(-3.8",
        "%)",
        "ok",
    ]
    assert lines[2].split() == [
        NAME,
        "chunks",
        "30",
        "40",
        "-10",
        "(-25",
        "%)",
        "ok",
    ]
    assert "2 within budget" in result.output


def test_a_metric_over_budget_exits_2_with_the_delta(tmp_path: Path):
    limits = {NAME: {"initial_gzip": 240_000, "chunks": 40}}
    result = _check(tmp_path, _doc(), limits)
    assert result.exit_code == 2, result.output
    row = next(line for line in result.output.splitlines() if "initial_gzip" in line)
    assert row.split()[2:] == [
        "250000",
        "240000",
        "+10,000",
        "B",
        "(+4.2",
        "%)",
        "over",
        "budget",
    ]
    assert "1 over budget" in result.output


@pytest.mark.parametrize(
    ("doc", "limits", "error"),
    [
        (_doc(), {"size.export[app=other]": {"chunks": 40}}, "not in the result"),
        (
            _doc(status="failed", error="RuntimeError: reflex export exited with 1"),
            BUDGETS,
            "failed: RuntimeError: reflex export exited with 1",
        ),
        (_doc(), {NAME: {"node_modules": 1}}, "metric not in the result"),
        (_doc(warmup=1), BUDGETS, "no timed samples"),
    ],
)
def test_a_budget_that_cannot_be_checked_exits_1(
    tmp_path: Path, doc: ResultDoc, limits: dict[str, dict[str, int]], error: str
):
    result = _check(tmp_path, doc, limits)
    assert result.exit_code == 1, result.output
    assert error in result.output


def test_an_unchecked_budget_wins_over_one_exceeded(tmp_path: Path):
    limits = {NAME: {"initial_gzip": 1, "node_modules": 1}}
    assert _check(tmp_path, _doc(), limits).exit_code == 1


def test_only_budgeted_metrics_are_checked():
    rows = budgets.check(_doc(), BUDGETS)
    assert [(row.benchmark, row.metric) for row in rows] == [
        (NAME, "initial_gzip"),
        (NAME, "chunks"),
    ]
    assert [(row.value, row.unit, row.exceeded) for row in rows] == [
        (250_000, "B", False),
        (30, "1", False),
    ]


def test_the_largest_timed_sample_is_checked():
    entry = make_entry(
        "size.export",
        {"chunks": (COUNT, [99, 30, 41])},
        params={"app": "playground"},
        warmup=1,
    )
    (row,) = budgets.check(make_doc([entry]), {NAME: {"chunks": 40}})
    assert (row.value, row.exceeded) == (41, True)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("not json", "is not valid JSON"),
        ('{"schema": "other/1", "budgets": {}}', "schema"),
        ('{"schema": "reflex-bench-budgets/1"}', "budgets"),
        ('{"schema": "reflex-bench-budgets/1", "budgets": {"x": 1}}', "x"),
        (
            '{"schema": "reflex-bench-budgets/1", "budgets": {"x": {"m": 1.5}}}',
            "x.m",
        ),
        ('{"schema": "reflex-bench-budgets/1", "budgets": {"x": {"m": -1}}}', "x.m"),
        ('{"schema": "reflex-bench-budgets/1", "budgets": {"x": {"m": true}}}', "x.m"),
    ],
)
def test_invalid_budget_files(tmp_path: Path, content: str, message: str):
    path = tmp_path / "budgets.json"
    path.write_text(content)
    with pytest.raises(budgets.BudgetsError, match=message):
        budgets.load(path)
    result = tmp_path / "result.json"
    dump(_doc(), result)
    invoked = CliRunner().invoke(
        cli.cli, ["budgets", "check", str(result), "--budgets", str(path)]
    )
    assert invoked.exit_code == 1
    assert message in invoked.output


def test_an_invalid_result_exits_1(tmp_path: Path):
    _, path = _files(tmp_path, _doc(), BUDGETS)
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    result = CliRunner().invoke(
        cli.cli, ["budgets", "check", str(bad), "--budgets", str(path)]
    )
    assert result.exit_code == 1
    assert "is not a valid reflex-bench/1 document" in result.output


def test_the_repo_budgets_name_declared_metrics():
    loaded = budgets.load(budgets.DEFAULT_PATH)
    assert loaded
    instances = {item.name: item.benchmark for item in plan(list(discover().values()))}
    for name, limits in loaded.items():
        assert name in instances
        assert limits.keys() <= instances[name].metrics.keys()
