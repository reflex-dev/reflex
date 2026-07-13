"""Tests for the performance report comparison script."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.compare_performance_results import (
    compare,
    environments_match,
    load_reports,
    main,
)

ENVIRONMENT = {
    "python": "3.14.0",
    "implementation": "CPython",
    "operating_system": "Linux",
    "machine": "x86_64",
}


def _report(
    directory: Path,
    filename: str,
    observations: list[float],
    metrics: dict[str, Any] | None = None,
    environment: dict[str, Any] | None = None,
) -> None:
    """Write a minimal schema-compatible performance report.

    Args:
        directory: Destination directory.
        filename: Report file name.
        observations: Latency observations in milliseconds.
        metrics: Optional extra metrics for the single result.
        environment: Optional environment override.
    """
    ordered = sorted(observations)
    summary = {
        "count": len(ordered),
        "p50_ms": ordered[len(ordered) // 2] if ordered else 0.0,
        "p95_ms": ordered[-1] if ordered else 0.0,
        "p99_ms": ordered[-1] if ordered else 0.0,
    }
    directory.joinpath(filename).write_text(
        json.dumps({
            "schema_version": 1,
            "suite": "demo",
            "environment": environment or ENVIRONMENT,
            "metadata": {},
            "results": [
                {
                    "name": "round_trip",
                    "parameters": {"clients": 1},
                    "observations_ms": observations,
                    "summary": summary,
                    "metrics": metrics or {},
                }
            ],
        })
    )


def test_load_reports_ignores_non_reports(tmp_path: Path):
    """Files without the report schema are skipped."""
    tmp_path.joinpath("junk.json").write_text('{"unrelated": true}')
    tmp_path.joinpath("broken.json").write_text("{")
    _report(tmp_path, "real.json", [1.0, 2.0])
    reports = load_reports(tmp_path)
    assert len(reports) == 1
    assert next(iter(reports)).startswith("demo|round_trip|")


def test_compare_flags_latency_regression(tmp_path: Path):
    """A doubled p50 above the floor fails; small drifts stay ok."""
    baseline_dir, current_dir = tmp_path / "base", tmp_path / "head"
    baseline_dir.mkdir()
    current_dir.mkdir()
    _report(baseline_dir, "demo.json", [10.0] * 10)
    _report(current_dir, "demo.json", [21.0] * 10)
    findings = compare(load_reports(baseline_dir), load_reports(current_dir))
    assert {finding.status for finding in findings} == {"fail"}

    _report(current_dir, "demo.json", [10.5] * 10)
    findings = compare(load_reports(baseline_dir), load_reports(current_dir))
    assert {finding.status for finding in findings} == {"ok"}


def test_compare_respects_absolute_floor(tmp_path: Path):
    """A large percentage change under the absolute floor stays ok."""
    baseline_dir, current_dir = tmp_path / "base", tmp_path / "head"
    baseline_dir.mkdir()
    current_dir.mkdir()
    _report(baseline_dir, "demo.json", [0.5] * 10)
    _report(current_dir, "demo.json", [1.5] * 10)
    findings = compare(load_reports(baseline_dir), load_reports(current_dir))
    assert {finding.status for finding in findings} == {"ok"}


def test_compare_flags_byte_metrics(tmp_path: Path):
    """Metrics named *_bytes are compared with the byte floor."""
    baseline_dir, current_dir = tmp_path / "base", tmp_path / "head"
    baseline_dir.mkdir()
    current_dir.mkdir()
    _report(baseline_dir, "demo.json", [], metrics={"wire_bytes": 100_000})
    _report(current_dir, "demo.json", [], metrics={"wire_bytes": 140_000})
    findings = compare(load_reports(baseline_dir), load_reports(current_dir))
    assert [finding.status for finding in findings] == ["warn"]
    assert findings[0].metric == "wire_bytes"


def test_compare_memory_metrics_use_larger_floor(tmp_path: Path):
    """Noisy process-memory metrics need a multi-megabyte absolute change."""
    baseline_dir, current_dir = tmp_path / "base", tmp_path / "head"
    baseline_dir.mkdir()
    current_dir.mkdir()
    _report(baseline_dir, "demo.json", [], metrics={"rss_growth_bytes": 1_000_000})
    _report(current_dir, "demo.json", [], metrics={"rss_growth_bytes": 2_000_000})
    findings = compare(load_reports(baseline_dir), load_reports(current_dir))
    assert [finding.status for finding in findings] == ["ok"]


def test_environment_mismatch_is_informational(tmp_path: Path, capsys):
    """A failing comparison across environments exits zero."""
    baseline_dir, current_dir = tmp_path / "base", tmp_path / "head"
    baseline_dir.mkdir()
    current_dir.mkdir()
    _report(baseline_dir, "demo.json", [10.0] * 10)
    _report(
        current_dir,
        "demo.json",
        [30.0] * 10,
        environment=ENVIRONMENT | {"python": "3.13.0"},
    )
    assert not environments_match(
        next(iter(load_reports(baseline_dir).values())),
        next(iter(load_reports(current_dir).values())),
    )
    assert main([str(baseline_dir), str(current_dir)]) == 0
    assert "informational" in capsys.readouterr().out


def test_main_exit_codes(tmp_path: Path):
    """Matching environments exit one on failure and zero when clean."""
    baseline_dir, current_dir = tmp_path / "base", tmp_path / "head"
    baseline_dir.mkdir()
    current_dir.mkdir()
    _report(baseline_dir, "demo.json", [10.0] * 10)
    _report(current_dir, "demo.json", [30.0] * 10)
    assert main([str(baseline_dir), str(current_dir)]) == 1

    _report(current_dir, "demo.json", [10.0] * 10)
    assert main([str(baseline_dir), str(current_dir)]) == 0

    assert main([str(tmp_path / "missing"), str(current_dir)]) == 0
