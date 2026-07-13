"""Developer lifecycle benchmarks for init, compile, edits, and export."""

from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import TextIO
from urllib.request import urlopen

import psutil
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


def _free_port() -> int:
    """Reserve and release an available local TCP port.

    Returns:
        Available port number for the development backend.
    """
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def _start_dev_backend(
    executable: str,
    app_root: Path,
    port: int,
) -> tuple[subprocess.Popen[str], TextIO, Path]:
    """Start a persistent reload-capable development backend.

    Args:
        executable: Python executable running Reflex.
        app_root: Generated application root.
        port: Backend port.

    Returns:
        Backend process, open log stream, and log path.
    """
    log_path = app_root / "hot-reload.log"
    log_stream = log_path.open("w+", encoding="utf-8")
    try:
        process = subprocess.Popen(
            [
                executable,
                "-m",
                "reflex",
                "run",
                "--backend-only",
                "--backend-port",
                str(port),
                "--loglevel",
                "error",
            ],
            cwd=app_root,
            env=os.environ | {"REFLEX_TELEMETRY_ENABLED": "false"},
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError:
        log_stream.close()
        raise
    return process, log_stream, log_path


def _wait_for_reload_version(
    process: subprocess.Popen[str],
    log_path: Path,
    port: int,
    expected: int,
    timeout: float = 120,
) -> None:
    """Wait until the live backend exposes an expected source version.

    Args:
        process: Development backend process.
        log_path: Backend log used for failure context.
        port: Backend port.
        expected: Source version expected after reload.
        timeout: Maximum wait in seconds.

    Raises:
        RuntimeError: If the backend exits before serving the version.
        TimeoutError: If the reload does not complete in time.
    """
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/reload-version"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log = log_path.read_text(encoding="utf-8")[-4000:]
            msg = f"Development backend exited during reload:\n{log}"
            raise RuntimeError(msg)
        try:
            with urlopen(url, timeout=0.5) as response:
                payload = json.load(response)
            if payload.get("version") == expected:
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.05)
    log = log_path.read_text(encoding="utf-8")[-4000:]
    msg = f"Timed out waiting for reload version {expected}:\n{log}"
    raise TimeoutError(msg)


def _stop_dev_backend(process: subprocess.Popen[str]) -> None:
    """Terminate a development backend and all reload workers.

    Args:
        process: Development backend process.
    """
    try:
        parent = psutil.Process(process.pid)
        processes = [parent, *parent.children(recursive=True)]
    except psutil.NoSuchProcess:
        return
    for running in reversed(processes):
        with contextlib.suppress(psutil.NoSuchProcess):
            running.terminate()
    _, alive = psutil.wait_procs(processes, timeout=10)
    for running in alive:
        with contextlib.suppress(psutil.NoSuchProcess):
            running.kill()


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
    backend_port = _free_port()
    backend, backend_log, backend_log_path = _start_dev_backend(
        executable,
        app_root,
        backend_port,
    )
    try:
        _wait_for_reload_version(
            backend,
            backend_log_path,
            backend_port,
            expected=0,
        )
        for cycle in range(1, reload_cycles + 1):
            cycle_source = source.replace(
                "RELOAD_VERSION = 0",
                f"RELOAD_VERSION = {cycle}",
            )
            started = time.perf_counter_ns()
            app_source.write_text(cycle_source, encoding="utf-8")
            _wait_for_reload_version(
                backend,
                backend_log_path,
                backend_port,
                expected=cycle,
            )
            reload_observations.append((time.perf_counter_ns() - started) / 1_000_000)
    finally:
        _stop_dev_backend(backend)
        backend_log.close()
    report.add(
        BenchmarkResult(
            "backend_hot_reload",
            {"cycles": reload_cycles, "watcher": "reflex run"},
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
