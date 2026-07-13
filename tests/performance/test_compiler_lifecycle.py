"""Developer lifecycle benchmarks for init, compile, edits, and export."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.benchmarks.support import BenchmarkResult, PerformanceReport
from tests.benchmarks.support.apps import lifecycle_app_source


def _run(command: list[str], cwd: Path, timeout: float = 300) -> float:
    """Run a lifecycle command and return elapsed milliseconds.

    Args:
        command: Command and arguments.
        cwd: Working directory.
        timeout: Command timeout.

    Returns:
        Elapsed wall time in milliseconds.
    """
    started = time.perf_counter_ns()
    subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=os.environ | {"REFLEX_TELEMETRY_ENABLED": "false"},
    )
    return (time.perf_counter_ns() - started) / 1_000_000


def _generated_metrics(root: Path) -> dict[str, int]:
    """Count generated frontend files and bytes.

    Args:
        root: Application root.

    Returns:
        Generated file, JavaScript module, and byte counts.
    """
    web = root / ".web"
    files = [path for path in web.rglob("*") if path.is_file()] if web.exists() else []
    javascript = [
        path for path in files if path.suffix in {".js", ".jsx", ".ts", ".tsx"}
    ]
    return {
        "generated_files": len(files),
        "javascript_modules": len(javascript),
        "generated_bytes": sum(path.stat().st_size for path in files),
        "javascript_bytes": sum(path.stat().st_size for path in javascript),
    }


@pytest.mark.performance
def test_compiler_lifecycle_report(
    tmp_path: Path,
    performance_output: Path,
    performance_scale: str,
):
    """Measure import, init, cold/warm compiles, edits, reload cycles, and export.

    Args:
        tmp_path: Temporary application parent.
        performance_output: Artifact directory.
        performance_scale: Selected scenario scale.
    """
    sizes = {
        "smoke": (10, 1, 2),
        "release": (1000, 25, 100),
    }
    rows, pages, reload_cycles = sizes[performance_scale]
    app_root = tmp_path / "lifecycle_app"
    app_root.mkdir()
    executable = sys.executable
    report = PerformanceReport(
        "compiler-lifecycle",
        metadata={"scale": performance_scale, "rows": rows, "pages": pages},
    )

    import_ms = _run([executable, "-c", "import reflex"], app_root)
    report.add(
        BenchmarkResult(
            "import_reflex",
            {},
            [import_ms],
            {},
            measurement_iterations=1,
        )
    )

    init_ms = _run(
        [
            executable,
            "-m",
            "reflex",
            "init",
            "--name",
            "lifecycle_app",
            "--template",
            "blank",
            "--no-agents",
        ],
        app_root,
    )
    app_source = app_root / "lifecycle_app" / "lifecycle_app.py"
    app_source.write_text(lifecycle_app_source(rows, pages), encoding="utf-8")
    report.add(BenchmarkResult("init", {}, [init_ms], {}, measurement_iterations=1))

    compile_command = [executable, "-m", "reflex", "compile", "--no-rich"]
    cold_ms = _run(compile_command, app_root)
    warm_ms = _run(compile_command, app_root)
    report.add(
        BenchmarkResult(
            "compile_cold",
            {"rows": rows, "pages": pages},
            [cold_ms],
            _generated_metrics(app_root),
        )
    )
    report.add(
        BenchmarkResult(
            "compile_warm_no_change",
            {"rows": rows, "pages": pages},
            [warm_ms],
            _generated_metrics(app_root),
        )
    )

    source = app_source.read_text()
    page_source = source.replace(
        "rx.heading(label)",
        'rx.heading(f"edited {label}")',
    )
    app_source.write_text(page_source, encoding="utf-8")
    page_edit_ms = _run(compile_command, app_root)
    report.add(BenchmarkResult("compile_page_edit", {}, [page_edit_ms], {}))

    shared_source = page_source.replace(
        "rx.text(index)",
        'rx.text(index, class_name="shared-row-label")',
    )
    app_source.write_text(shared_source, encoding="utf-8")
    shared_edit_ms = _run(compile_command, app_root)
    report.add(
        BenchmarkResult(
            "compile_shared_component_edit",
            {},
            [shared_edit_ms],
            {},
        )
    )

    source = shared_source.replace("count: int = 0", "count: int = 1")
    app_source.write_text(source, encoding="utf-8")
    state_edit_ms = _run(compile_command, app_root)
    report.add(BenchmarkResult("compile_state_edit", {}, [state_edit_ms], {}))

    reload_observations = []
    for cycle in range(reload_cycles):
        app_source.write_text(
            source + f"\n# reload cycle {cycle}\n",
            encoding="utf-8",
        )
        reload_observations.append(_run(compile_command, app_root))
    report.add(
        BenchmarkResult(
            "hot_reload_cycles",
            {"cycles": reload_cycles},
            reload_observations,
            _generated_metrics(app_root),
            measurement_iterations=reload_cycles,
        )
    )

    export_ms = _run(
        [
            executable,
            "-m",
            "reflex",
            "export",
            "--backend-only",
            "--no-zip",
        ],
        app_root,
    )
    report.add(BenchmarkResult("export_backend", {}, [export_ms], {}))
    report.write(performance_output / "compiler-lifecycle.json")

    assert report.results
    assert _generated_metrics(app_root)["generated_files"] > 0
