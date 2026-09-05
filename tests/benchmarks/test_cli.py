"""Wall-time benchmarks for fresh Reflex CLI processes."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pytest_codspeed import BenchmarkFixture


@pytest.fixture(scope="module")
def reflex_executable() -> str:
    """Resolve the Reflex console script installed in the active environment.

    Returns:
        The path to the Reflex console script.

    Raises:
        RuntimeError: If the console script is not installed.
    """
    executable = shutil.which("reflex")
    if executable is None:
        msg = "The reflex console script is not installed in the active environment."
        raise RuntimeError(msg)
    return executable


def _subprocess_env() -> dict[str, str]:
    """Build a deterministic environment for CLI subprocesses.

    Returns:
        Environment variables for a benchmark subprocess.
    """
    return {
        **os.environ,
        "PYTHONHASHSEED": "0",
        "REFLEX_CHECK_LATEST_VERSION": "false",
        "REFLEX_TELEMETRY_ENABLED": "false",
    }


def _run_command(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    *,
    require_stdout: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    """Run a benchmark command in a fresh process.

    Args:
        command: The executable and arguments to run.
        cwd: The isolated working directory for the process.
        env: Environment variables for the process.
        require_stdout: Whether the command must produce user-facing output.

    Returns:
        The completed subprocess.
    """
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        check=True,
        timeout=15,
    )
    if require_stdout and not result.stdout:
        msg = f"Command produced no output: {command!r}"
        raise AssertionError(msg)
    return result


def test_python_process_startup(
    benchmark: BenchmarkFixture,
    tmp_path: Path,
):
    """Track interpreter startup so CLI results have a stable control."""
    command = [sys.executable, "-c", "pass"]
    env = _subprocess_env()
    result = benchmark(lambda: _run_command(command, tmp_path, env))

    assert result.returncode == 0, result.stderr.decode(errors="replace")


def test_import_cli(
    benchmark: BenchmarkFixture,
    tmp_path: Path,
):
    """Benchmark importing the command tree in a fresh interpreter."""
    command = [sys.executable, "-c", "import reflex.reflex"]
    env = _subprocess_env()
    result = benchmark(lambda: _run_command(command, tmp_path, env))

    assert result.returncode == 0, result.stderr.decode(errors="replace")


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["--version"], id="version"),
        pytest.param(["--help"], id="help"),
        pytest.param(["run", "--help"], id="run_help"),
        pytest.param(["component", "--help"], id="component_help"),
        pytest.param(["cloud", "--help"], id="cloud_help"),
        pytest.param(["deploy", "--help"], id="deploy_help"),
    ],
)
def test_cli_startup(
    argv: list[str],
    reflex_executable: str,
    benchmark: BenchmarkFixture,
    tmp_path: Path,
):
    """Benchmark an informational command in a fresh CLI process.

    Args:
        argv: The command-line arguments to benchmark.
        reflex_executable: The installed Reflex console script.
        benchmark: The CodSpeed benchmark fixture.
        tmp_path: An isolated working directory.
    """
    command = [reflex_executable, *argv]
    env = _subprocess_env()
    result = benchmark(
        lambda: _run_command(command, tmp_path, env, require_stdout=True)
    )

    assert result.returncode == 0
    assert result.stdout
